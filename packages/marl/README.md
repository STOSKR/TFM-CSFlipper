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
- `market_env_creator()` y `register_market_env()` preparan una fabrica registrable desde RLlib.

Todavia no anade Ray/PettingZoo como dependencia obligatoria. La integracion formal de entrenamiento
queda para la tarea MAPPO/RLlib.

## Episodios

`load_market_episode_steps()` carga pasos desde un parquet directo o desde un directorio de
dataset con `train.parquet`, `validation.parquet` o `test.parquet`.

Ejemplo:

```python
from packages.marl import MarketMARLEnvironment, load_market_episode_steps

steps = load_market_episode_steps("data/datasets/trading_profit_v1", split="train", limit=100)
env = MarketMARLEnvironment(steps)
```

## RLlib

`register_market_env()` recibe la funcion `register_env` de RLlib/Ray Tune por parametro:

```python
from ray.tune.registry import register_env

from packages.marl import load_market_episode_steps, register_market_env

steps = load_market_episode_steps("data/datasets/trading_profit_v1", split="train", limit=100)
register_market_env("csflipper-market", register_env, steps)
```
