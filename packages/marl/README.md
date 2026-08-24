# MARL

El paquete contiene el entorno de cartera, las recompensas y el entrenamiento
CTDE de CSFlipper. Scout, Trader y Portfolio reciben observaciones locales. Un
modelo evaluador central recibe el estado compartido únicamente durante el
entrenamiento.

## Datos y episodios

`load_market_episode_steps()` carga un corte temporal de un conjunto Parquet.
`MarketEpisodeSource` extrae ventanas de días contiguos. Nunca mezcla los
cortes `train`, `validation` y `test`.

Cada paso representa un candidato de compra y una posible venta posterior. El
simulador registra las posiciones, aplica las comisiones y respeta los ocho
días de bloqueo de intercambio antes de permitir una venta.

## Recompensas

`calculate_cooperative_reward()` calcula una recompensa común solamente cuando
se puede comprobar un resultado:

- ROI neto al cerrar una posición, limitado al intervalo `[-1, 1]`.
- Penalización por cada día posterior al bloqueo de intercambio habitual.
- Penalización proporcional a los límites incumplidos en una compra propuesta.

La recompensa híbrida combina por defecto el 70 % de la señal común con el
30 % de una señal individual:

- Scout recibe una penalización adicional si ignora una oportunidad que acaba
  siendo rentable con saldo suficiente, o si marca una posición que se cierra
  con ROI negativo.
- Trader se penaliza si no propone una compra viable, propone una compra no
  válida o termina el día por debajo del objetivo flexible pese a disponer de
  candidatos suficientes.
- Portfolio se penaliza si aprueba una compra que incumple límites.

El entorno deja ambos desgloses en `info` para auditar una ejecución.

## Entrenamiento CTDE

Primero se crea el conjunto con cortes temporales:

```powershell
python -m apps.cli.build_trading_dataset `
  --input-parquet data/history/market_history_v1 `
  --output data/datasets/trading_profit_v1 `
  --horizon-days 8 --future-tolerance-days 7 --purge-gap-days 15 `
  --validation-start 2026-01-01 --test-start 2026-03-01
```

Después se entrena y se guarda el mejor checkpoint según validación:

```powershell
python -m apps.cli.train_marl_ctde `
  --dataset-dir data/datasets/trading_profit_v1 `
  --output-dir model-runs/marl_ctde/primera_sesion `
  --iterations 50 --episodes-per-iteration 8 --episode-days 14
```

El comando admite `--shared-weight`, `--roi-weight`,
`--extra-hold-day-penalty`, `--constraint-violation-penalty`,
`--target-investment-fraction` y `--target-investment-tolerance` para repetir
la validación con configuraciones distintas. El checkpoint guarda los tres
actores locales y el evaluador central. `load_ctde_policy()` permite cargar los
actores para una recomendación posterior sin necesitar el estado central.

`apps.cli.run_marl_episode` se conserva solo como comprobación manual del
simulador. No entrena ninguna política.
