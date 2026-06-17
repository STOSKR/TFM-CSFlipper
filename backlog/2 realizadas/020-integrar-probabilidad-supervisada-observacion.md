# Integrar probabilidad supervisada en observacion

## Objetivo

Incorporar el output de probabilidad calibrada del modelo supervisado como feature adicional dentro del espacio de observacion de Scout, Trader y Portfolio.

## Contexto

El modelo supervisado no toma la decision final. Su probabilidad de que el spread sea rentable a 8 dias actua como senal informativa para las politicas MARL.

## Alcance

- Calcular o cargar `spread_profitable_probability_8d` para cada timestep/item.
- Incorporar la feature en la observacion de Scout, Trader y Portfolio.
- Incluir version del modelo y manejo de probabilidades ausentes.
- Evitar leakage: en entrenamiento solo usar predicciones disponibles en el timestamp simulado.
- Permitir ejecutar episodios con la feature activada o desactivada para ablation study.
- Anadir tests de observacion con y sin feature supervisada.

## Criterios de aceptacion

- Los tres agentes reciben la probabilidad calibrada en su observacion cuando esta activada.
- El entorno puede desactivar la feature mediante configuracion.
- Las observaciones mantienen shape estable aunque falte prediccion.
- La ablation con/sin feature puede configurarse sin cambiar codigo de agentes.

## Decisiones tecnicas

- La probabilidad supervisada es feature, no regla de compra.
- El modelo supervisado se ejecuta offline para entrenamiento y en modo inferencia para produccion.

## Pasos realizados

- Anadida `supervised_probability` a las observaciones de Scout, Trader y Portfolio.
- Anadido flag `supervised_probability_available` para mantener shape estable cuando falte
  prediccion.
- Anadido `include_supervised_probability` al entorno para ejecutar ablations sin cambiar codigo
  de agentes.
- Anadido `supervised_model_version` al contrato de `MarketEpisodeStep` y al `info` de cada agente.
- Anadido `--no-supervised-probability` al smoke CLI local.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_market_marl_env.py tests/unit/test_marl_episode_loader.py tests/unit/test_run_marl_episode_cli.py`
- `python -m ruff check packages/marl/market_env.py apps/cli/run_marl_episode.py tests/unit/test_market_marl_env.py tests/unit/test_run_marl_episode_cli.py`
- `python -m mypy packages/marl/market_env.py apps/cli/run_marl_episode.py tests/unit/test_market_marl_env.py tests/unit/test_run_marl_episode_cli.py`
- `python -m apps.cli.run_marl_episode --limit 1`
- `python -m apps.cli.run_marl_episode --limit 1 --no-supervised-probability`

## Bloqueos o riesgos

- Si se precalculan predicciones sobre todo el historico, hay que garantizar que cada fold/modelo respeta temporalidad.
- La version actual solo consume probabilidades ya presentes en el candidato; no ejecuta inferencia
  supervisada online dentro del entorno.
