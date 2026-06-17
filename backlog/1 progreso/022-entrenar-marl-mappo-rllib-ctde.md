# Entrenar MARL con MAPPO en RLlib

## Objetivo

Entrenar el sistema MARL con MAPPO via RLlib bajo el paradigma CTDE: critico centralizado durante entrenamiento y ejecucion descentralizada por actor local en inferencia.

## Contexto

El entrenamiento debe usar el entorno PettingZoo, tres politicas cooperativas y estado global para el critico centralizado. La inferencia no debe depender del estado global completo.

## Alcance

- Registrar el entorno PettingZoo para RLlib.
- Configurar MAPPO o PPO multiagente con parametros compatibles con CTDE.
- Definir politicas para Scout, Trader y Portfolio.
- Incorporar estado global al critico centralizado durante entrenamiento.
- Guardar checkpoints, configuracion, seeds y metricas.
- Preparar script reproducible de entrenamiento.
- Anadir smoke test de entrenamiento corto.

## Criterios de aceptacion

- Un entrenamiento corto ejecuta sin errores con datos historicos de prueba.
- Los checkpoints permiten restaurar politicas.
- La inferencia usa actores locales y observaciones individuales.
- Las metricas incluyen recompensa, profit, exposicion, drawdown, operaciones y capital bloqueado.
- Queda documentada la configuracion CTDE usada.

## Decisiones tecnicas

- MAPPO es el algoritmo objetivo.
- RLlib gestiona entrenamiento multiagente; PettingZoo define entorno.
- Los modelos supervisados no se reentrenan durante entrenamiento MARL.

## Pasos realizados

- Instalado stack MARL en el entorno local: `ray 2.55.1`, `gymnasium 1.2.2`,
  `pettingzoo 1.26.1` y `torch 2.12.0`.
- Anadido extra opcional `marl` en `pyproject.toml` con Ray/RLlib, PettingZoo,
  Gymnasium y PyTorch.
- Anadido `PettingZooMarketEnv`, wrapper `ParallelEnv` con observaciones vectoriales
  por agente y espacios Gymnasium.
- Anadido `RLLibMarketEnv`, wrapper `MultiAgentEnv` para RLlib.
- Anadido `python -m apps.cli.train_marl_rllib` para ejecutar un smoke PPO multiagente
  con tres politicas (`scout`, `trader`, `portfolio`).
- El smoke guarda checkpoint y devuelve metricas operativas: reward medio, trades,
  posiciones, cash, beneficio realizado, drawdown, capital bloqueado y posiciones abiertas.
- Definido contrato CTDE de estado central en `MarketMARLEnvironment.central_state_fields`
  y `central_state()`, separado de las observaciones locales de los actores.
- Expuesto el estado central en PettingZoo mediante `state()`/`state_space()` y en RLlib
  mediante `central_state()`/`central_state_space()` mas `infos["__common__"]`.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py tests/unit/test_marl_rllib_adapter.py tests/unit/test_market_marl_env.py tests/unit/test_run_marl_episode_cli.py`
- `python -m ruff check packages/marl/pettingzoo_env.py packages/marl/rllib_training.py apps/cli/train_marl_rllib.py tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py`
- `python -m mypy packages/marl/pettingzoo_env.py packages/marl/rllib_training.py apps/cli/train_marl_rllib.py tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py`
- `python -m apps.cli.train_marl_rllib --limit 8 --iterations 1`
- `python -m apps.cli.train_marl_rllib --dataset-dir data/datasets/trading_profit_v1 --split train --limit 8 --iterations 1`
- `python -m pytest tests/unit/test_market_marl_env.py tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py tests/unit/test_run_marl_episode_cli.py`
- `python -m ruff check packages/marl/market_env.py packages/marl/pettingzoo_env.py packages/marl/rllib_training.py tests/unit/test_market_marl_env.py tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py`
- `python -m mypy packages/marl/market_env.py packages/marl/pettingzoo_env.py packages/marl/rllib_training.py tests/unit/test_market_marl_env.py tests/unit/test_marl_pettingzoo_env.py tests/unit/test_marl_rllib_training.py`
- `python -m apps.cli.train_marl_rllib --dataset-dir data/datasets/trading_profit_v1 --split train --limit 8 --iterations 1`

## Bloqueos o riesgos

- RLlib puede requerir wrappers especificos para PettingZoo y versiones compatibles.
- MAPPO con critico centralizado puede requerir personalizar modelo o view requirements.
- Lo implementado ahora es PPO multiagente con recompensa compartida y estado central expuesto.
  Ejecuta entrenamiento y checkpoint, pero no debe venderse como MAPPO CTDE completo hasta
  conectar el critico centralizado al value function.
- RLlib emite avisos de deprecacion para `compute_single_action` en evaluacion; no bloquea
  el smoke, pero conviene migrar a RLModule antes de escalar.
