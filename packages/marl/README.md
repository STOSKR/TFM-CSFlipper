# MARL Package

Primer andamiaje del entorno multiagente.

`packages.marl.market_env` define un entorno paralelo minimo para Scout, Trader y Portfolio:

- `reset()` devuelve observaciones locales por agente;
- `step(actions)` acepta acciones simultaneas;
- `AGENT_SPECS` declara rol, campos locales, acciones y si el agente ejecuta operaciones;
- `action_masks()` expone acciones validas para el candidato actual;
- solo se ejecuta una compra si Scout marca, Trader compra y Portfolio aprueba;
- la compra usa `PortfolioSimulator` y respeta `buy_platform` del candidato;
- la validacion usa `evaluate_portfolio_risk`;
- la recompensa compartida usa `calculate_cooperative_reward()` y deja desglose en `info`;
- `market_env_creator()` y `register_market_env()` preparan una fabrica registrable desde RLlib.

Todavia no anade Ray/PettingZoo como dependencia obligatoria. La integracion formal de entrenamiento
queda para la tarea MAPPO/RLlib.

## Episodios

`load_market_episode_steps()` carga pasos desde un parquet directo o desde un directorio de
dataset con `train.parquet`, `validation.parquet` o `test.parquet`.

Cada paso representa una oportunidad concreta de entrada/salida. `buy_platform` y `sell_platform`
son opcionales y por compatibilidad asumen `STEAM`; cuando el candidato venga de BUFF debe usar
`BUFF`. `buy_price_type` y `sell_price_type` distinguen `listing` de `buy_order`, porque no es lo
mismo comprar/vender al precio normal que contra una orden.

La ruta es parte del candidato, no una accion aprendida todavia. Trader decide `hold` o `buy_one`
sobre esa ruta preconstruida. El `info` de cada agente expone `route_label`, `route_selection` y
`cashflow`, con valor neto de salida, plataforma donde queda el saldo y valor efectivo si se modela
cash-out.

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

## Recompensa

`calculate_cooperative_reward()` devuelve una recompensa comun para Scout, Trader y Portfolio.
La version actual es interpretable y configurable:

- beneficio realizado neto normalizado;
- retorno inmediato del candidato comprado como senal provisional;
- penalizacion por oportunidad accionable ignorada;
- penalizacion por intentar compras que violan riesgo;
- penalizacion por drawdown, capital bloqueado y volatilidad si esta disponible.

El entorno copia el desglose en `info["reward_breakdown"]` para poder auditar entrenamientos.

## Prueba local

Sin RLlib ni entrenamiento se puede ejecutar un episodio smoke con una politica fija:

```powershell
python -m apps.cli.run_marl_episode
```

Tambien puede cargar un dataset parquet versionado:

```powershell
python -m apps.cli.run_marl_episode --dataset-dir data/datasets/trading_profit_v1 --split train --limit 5
```

Esto solo valida el entorno, observaciones, acciones, recompensa y simulador de cartera. No entrena
una politica MARL.
