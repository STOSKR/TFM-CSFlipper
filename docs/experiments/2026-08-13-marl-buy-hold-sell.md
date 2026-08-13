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

## Resultado funcional

El informe no compara reglas de inversión. Una regla que vende puede reutilizar
el efectivo y abrir más posiciones que otra que lo mantiene bloqueado, por lo
que sus compras no parten de las mismas condiciones. Esa comparación sería
engañosa.

En su lugar, el resultado reproducible describe un único ciclo controlado:

| Capital inicial | Compra | Desbloqueo | Venta neta | Beneficio | Capital final |
| ---: | ---: | --- | ---: | ---: | ---: |
| 100,00 EUR | 10,00 EUR | 09-01-2026 | 12,18 EUR | 2,18 EUR | 102,18 EUR |

La tabla demuestra que la posición no se puede cerrar antes de la fecha de
desbloqueo y que, al vender, se aplican la comisión de Steam y el abono del
importe neto a la cartera. No mide la calidad de una estrategia ni la
rentabilidad de PPO.

## Recorrido de cartera con 1.000 EUR

Además de la prueba mínima, se ha recorrido el corte de marzo con 1.000 EUR y
una regla determinista: comprar si el margen neto observado es positivo y las
restricciones lo permiten, o vender la posición del mismo artículo cuando ya
está desbloqueada. Es un único recorrido para comprobar que el entorno maneja
varias posiciones y reutiliza efectivo. No es una comparación de estrategias.

| Capital inicial | Observaciones | Compras | Ventas | Máximo simultáneo | Posiciones abiertas al final |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1.000,00 EUR | 95 | 24 | 19 | 11 | 5 |

El número de compras no se fija de antemano. Portfolio limita cada posición al
20 % del valor de cartera, mantiene al menos un 10 % de efectivo y evita que
el capital bloqueado supere el 60 %. Cuando una posición se cierra, su importe
neto vuelve a estar disponible para las oportunidades posteriores. Por ello
se producen varias compras aunque el capital inicial sea finito.

El corte contiene oportunidades ya preseleccionadas y está muy sesgado hacia
márgenes positivos. Los valores económicos de este recorrido solo validan la
mecánica de inventario, bloqueo, venta y restricciones. No se interpretan como
beneficio esperado ni como rendimiento de una política PPO.

## Reproducción

```powershell
python -m pytest tests/unit/test_market_marl_env.py `
  tests/unit/test_marl_pettingzoo_env.py `
  tests/unit/test_marl_rllib_training.py `
  tests/unit/test_run_marl_episode_cli.py `
  tests/unit/test_report_marl_sale_experiment.py -q

python -m apps.cli.report_marl_sale_experiment `
  --cash 100 `
  --output data/experiments/marl_sale_20260813/report.json

python -m apps.cli.report_marl_sale_experiment `
  --dataset-dir data/experiments/walkforward_20260810/march `
  --split test --limit 95 --cash 1000 `
  --output data/experiments/marl_sale_20260813/portfolio_report.json
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
