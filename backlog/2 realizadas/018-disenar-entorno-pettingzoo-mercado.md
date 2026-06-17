# Diseñar entorno PettingZoo de mercado

## Objetivo

Diseñar e implementar el entorno de simulacion de mercado en PettingZoo con datos historicos reales de Steam Market y Buff163.

## Contexto

El sistema MARL cooperativo necesita un entorno reproducible que avance por ventanas historicas, aplique acciones simuladas y devuelva observaciones, recompensas y estados compatibles con RLlib.

## Alcance

- Implementar un entorno PettingZoo multiagente para Scout, Trader y Portfolio.
- Cargar episodios desde datasets historicos versionados.
- Avanzar la simulacion por timestamp o ventana temporal.
- Conectar el simulador de cartera, trade hold, comisiones y liquidez.
- Definir `reset`, `step`, terminaciones, truncaciones e info por agente.
- Preparar wrapper o adaptador compatible con RLlib.
- Anadir tests de episodio pequeno y reproducible.

## Criterios de aceptacion

- El entorno ejecuta un episodio completo con datos historicos de prueba.
- Las observaciones y acciones cumplen espacios declarados.
- El estado de cartera evoluciona de forma consistente con acciones y trade hold.
- El entorno puede registrarse o envolverse para entrenamiento en RLlib.
- No hay dependencia de scraping en vivo durante entrenamiento.

## Decisiones tecnicas

- PettingZoo define la interfaz de entorno; RLlib se integra despues.
- Los datos reales se cargan desde artefactos o consultas versionadas, no desde conectores live.

## Pasos realizados

- Iniciada la tarea tras cerrar las restricciones de riesgo de Portfolio (`017`).
- Creado `packages.marl.market_env` con un entorno paralelo minimo para Scout,
  Trader y Portfolio.
- Definidos agentes fijos `scout`, `trader` y `portfolio`, acciones simultaneas
  simples y observaciones locales iniciales.
- El entorno reutiliza `PortfolioSimulator` para ejecutar compras simuladas.
- El entorno reutiliza `evaluate_portfolio_risk` para bloquear compras que violan
  limites de riesgo.
- Anadido `MarketEpisodeStep.from_mapping()` para construir episodios pequenos
  desde filas/datasets.
- Anadido `packages.marl.episodes.load_market_episode_steps()` para cargar episodios
  desde un parquet directo o desde splits `train/validation/test` de un dataset versionado.
- Documentado el paquete en `packages/marl/README.md`.
- Anadido `packages.marl.rllib_adapter` con `market_env_creator()` y `register_market_env()`,
  para exponer una fabrica registrable por RLlib/Ray Tune sin anadir Ray como dependencia obligatoria.
- Anadidos tests del adaptador RLlib con registro simulado y construccion de entorno desde pasos
  historicos en memoria.
- Revisada la trazabilidad de `step()`: el `info` devuelto describe el item procesado en esa
  transicion, no el siguiente item observado.

## Pruebas ejecutadas

- `python -m ruff check packages/marl tests/unit/test_market_marl_env.py`
- `python -m mypy packages/marl tests/unit/test_market_marl_env.py`
- `python -m pytest tests/unit/test_market_marl_env.py`
- `python -m pytest tests/unit/test_marl_episode_loader.py`
- `python -m ruff check packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m mypy packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m pytest tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m pytest tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m ruff check packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m mypy packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`

## Bloqueos o riesgos

- Hay que decidir granularidad temporal y como manejar huecos de datos entre plataformas.
- La integracion con Ray/PettingZoo real se validara al configurar MAPPO en `022`.
- La recompensa compartida es provisional; debe cerrarse en la tarea `021`.
