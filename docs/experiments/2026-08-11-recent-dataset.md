# Diagnóstico del corte reciente, 11 de agosto de 2026

## Propósito

Comprobar si la base de datos conectada contiene suficiente variedad temporal en
la ruta BUFF a Steam para repetir el entrenamiento supervisado y la evaluación
de políticas MARL.

## Configuración común

- Inicio de datos: 1 de diciembre de 2025.
- Horizonte: ocho días.
- Tolerancia de futuro: siete días.
- Purga: ocho días.
- Validación: desde 1 de junio de 2026.
- Prueba: del 1 de julio al 1 de agosto de 2026.
- Margen mínimo: 10 %.
- Ruta: BUFF listing → Steam listing.

## Resultado

| Entrenamiento | Validación | Prueba | Conclusión |
| ---: | ---: | ---: | --- |
| 551, 95,6 % positivos | 76, 100 % positivos | 84, 98,8 % positivos | No existe una clase negativa suficiente. |

La ruta usa 19 artículos. No se entrena un clasificador ni una política MARL
comparativa con este corte. Una métrica de clasificación calculada sobre una sola
clase sería engañosa.

## Comandos

```powershell
python -m apps.cli.build_trading_dataset `
  --output data/experiments/recent_probe_20260811/buff_to_steam `
  --trade-direction buff_to_steam_sell `
  --horizon-days 8 --future-tolerance-days 7 --purge-gap-days 8 `
  --min-profit-eur 0 --min-return 0.1 `
  --start-date 2025-12-01 --validation-start 2026-06-01 `
  --test-start 2026-07-01 --test-end 2026-08-01 `
  --query-start 2025-12-01

## Siguiente evidencia necesaria

1. Capturas recurrentes de más artículos y de ambos lados del mercado.
2. Oportunidades descartadas junto a oportunidades de margen positivo.
3. Episodios que cierren posiciones y registren su resultado neto.
