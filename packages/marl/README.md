# MARL Package

Primer andamiaje del entorno multiagente.

`packages.marl.market_env` define un entorno paralelo minimo para Scout, Trader y Portfolio:

- `reset()` devuelve observaciones locales por agente;
- `step(actions)` acepta acciones simultaneas;
- `AGENT_SPECS` declara rol, campos locales, acciones y si el agente ejecuta operaciones;
- `action_masks()` expone acciones validas para el candidato actual;
- solo se ejecuta una compra si Scout marca, Trader compra y Portfolio aprueba;
- la compra usa `PortfolioSimulator`;
- la validacion usa `evaluate_portfolio_risk`;
- la recompensa compartida inicial usa el retorno inmediato del ejemplo.

Todavia no es el wrapper final PettingZoo/RLlib. La intencion es estabilizar primero los
contratos de observacion, accion, simulador y riesgo antes de anadir la dependencia formal y el
entrenamiento.

## Episodios

`load_market_episode_steps()` carga pasos desde un parquet directo o desde un directorio de
dataset con `train.parquet`, `validation.parquet` o `test.parquet`.

Ejemplo:

```python
from packages.marl import MarketMARLEnvironment, load_market_episode_steps

steps = load_market_episode_steps("data/datasets/trading_profit_v1", split="train", limit=100)
env = MarketMARLEnvironment(steps)
```
