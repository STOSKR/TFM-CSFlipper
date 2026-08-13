# Flujo MARL de compra, espera y venta

## Objetivo

Esta prueba amplía el entorno cooperativo con una acción de venta simulada. El
objetivo es comprobar que una posición abierta puede conservarse durante el
periodo de bloqueo y cerrarse después con el precio observado de Steam.

La ruta evaluada es `BUFF listing -> Steam listing`. No se envían órdenes a
ninguna plataforma.

## Diseño del entorno

Las acciones son discretas y se reparten entre los tres roles:

| Rol | Acciones | Intervención en la venta |
| --- | --- | --- |
| Scout | Ignorar o marcar | No interviene. |
| Trader | Mantener, comprar una unidad o vender | Solicita la venta de la posición desbloqueada del artículo actual. |
| Portfolio | Rechazar o aprobar | Autoriza la operación de compra o de venta. |

La venta solo queda disponible cuando se cumplen todas las condiciones:

1. Hay una posición abierta del mismo artículo.
2. Han transcurrido ocho días desde la compra.
3. El paso contiene un precio bruto de salida en Steam.
4. La liquidez disponible permite cerrar la unidad.

Al cierre, el simulador aplica la comisión de Steam, actualiza el efectivo,
registra el beneficio y elimina el capital bloqueado. La recompensa compartida
incorpora el beneficio realizado, por lo que los tres agentes reciben el mismo
resultado de la operación.

## Prueba unitaria controlada

El caso usa una compra de 10,00 EUR en BUFF el 1 de enero de 2026 y una venta
el 9 de enero en Steam por 14,00 EUR brutos. Tras la comisión de Steam, el
valor neto de salida es 12,18 EUR.

| Evento | Fecha | Resultado |
| --- | --- | --- |
| Compra aprobada | 01-01-2026 | Se bloquean 10,00 EUR. |
| Intento durante el bloqueo | 02-01-2026 | La máscara de acción inhabilita vender. |
| Venta aprobada | 09-01-2026 | Se liberan 12,18 EUR y se registran 2,18 EUR de beneficio. |

La prueba automatizada comprueba el bloqueo, la habilitación de la venta, el
beneficio, el efectivo final y el identificador de la posición cerrada.

## Comparación funcional en el corte de marzo

Se ejecutaron tres reglas deterministas sobre las 95 observaciones de prueba
del corte temporal de marzo. El capital inicial fue 1.000 EUR. La finalidad es
verificar el ciclo de cartera completo, no comparar estrategias entrenadas ni
estimar rendimiento fuera de esta muestra.

| Regla | Compras | Ventas | Posiciones cerradas | Efectivo final | Beneficio realizado |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mantener | 0 | 0 | 0 | 1.000,00 EUR | 0,00 EUR |
| Comprar si el margen es positivo | 13 | 0 | 0 | 309,64 EUR | 0,00 EUR |
| Comprar, esperar y vender | 24 | 19 | 19 | 888,99 EUR | 195,59 EUR |

La segunda regla deja posiciones abiertas y, por ello, no materializa
beneficio. La tercera cierra 19 posiciones que ya han superado el bloqueo. Al
final conserva cinco posiciones abiertas con 306,60 EUR de capital bloqueado.
La cifra de beneficio solo describe este recorrido histórico y esta regla
determinista. No se presenta como resultado de aprendizaje por refuerzo.

## Reproducción

```powershell
python -m pytest tests/unit/test_market_marl_env.py `
  tests/unit/test_marl_pettingzoo_env.py `
  tests/unit/test_marl_rllib_training.py `
  tests/unit/test_run_marl_episode_cli.py `
  tests/unit/test_report_marl_sale_experiment.py -q

python -m apps.cli.report_marl_sale_experiment `
  --dataset-dir data/experiments/walkforward_20260810/march `
  --split test --limit 95 --cash 1000 `
  --output data/experiments/marl_sale_20260813/report.json
```

El segundo comando genera un resumen JSON compacto. Los datos derivados se
mantienen fuera de Git y el informe conserva los parámetros y resultados
necesarios para repetir la ejecución.

## Uso previsto en la memoria

Este resultado permite actualizar el capítulo de arquitectura con la acción
`vender`, y el capítulo de experimentación con una tabla de transición de
cartera. La formulación correcta es que se ha comprobado el ciclo de compra,
bloqueo y venta simulada. El entrenamiento PPO sobre este espacio de acciones
queda para la siguiente iteración.
