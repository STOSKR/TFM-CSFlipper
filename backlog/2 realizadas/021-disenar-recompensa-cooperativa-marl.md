# Diseñar recompensa cooperativa MARL

## Objetivo

Diseñar la funcion de recompensa compartida cooperativa para el entorno MARL.

## Contexto

Scout, Trader y Portfolio deben optimizar un objetivo comun. La recompensa debe capturar beneficio realizado sin incentivar sobreexposicion, inactividad artificial o carteras excesivamente volatiles.

## Alcance

- Incluir profit realizado neto de comisiones.
- Penalizar sobreexposicion segun restricciones de Portfolio.
- Penalizar inactividad prolongada cuando existan oportunidades accionables.
- Penalizar volatilidad de cartera y drawdown.
- Definir normalizacion y escalado de terminos.
- Registrar desglose de recompensa en `info` para analisis.
- Anadir tests de casos controlados: beneficio, perdida, inactividad, sobreexposicion y volatilidad.

## Criterios de aceptacion

- La recompensa compartida se calcula igual para los tres agentes, salvo que se documente una excepcion.
- Cada componente de recompensa es trazable y configurable.
- Una politica que sobreexpone cartera recibe penalizacion aunque tenga beneficio bruto.
- La funcion no usa informacion futura no disponible en el timestep.

## Decisiones tecnicas

- Empezar con recompensa interpretable y auditable antes de hacer reward shaping avanzado.
- Reutilizar metricas del simulador y reglas de riesgo.

## Pasos realizados

- Movida a progreso tras revisar el entorno MARL y detectar que la recompensa seguia siendo provisional.
- Creado `packages.marl.rewards` con `CooperativeRewardConfig`,
  `CooperativeRewardBreakdown` y `calculate_cooperative_reward()`.
- La recompensa compartida incluye profit realizado neto normalizado, retorno del candidato comprado,
  penalizacion por inactividad ante oportunidad accionable, penalizacion por violaciones de riesgo,
  drawdown, capital bloqueado y volatilidad opcional.
- Conectada la recompensa al `MarketMARLEnvironment`; Scout, Trader y Portfolio reciben el mismo
  reward por timestep.
- Anadido `reward_breakdown` en `info` para auditar cada componente durante entrenamiento.
- Anadido soporte opcional de `volatility` en `MarketEpisodeStep` y `RiskCandidate`.
- Documentado el contrato de recompensa en `packages/marl/README.md`.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_market_marl_env.py tests/unit/test_marl_rewards.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m ruff check packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_rewards.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`
- `python -m mypy packages/marl tests/unit/test_market_marl_env.py tests/unit/test_marl_rewards.py tests/unit/test_marl_episode_loader.py tests/unit/test_marl_rllib_adapter.py`

## Bloqueos o riesgos

- Una mala escala de recompensas puede hacer inestable MAPPO.
- Los pesos actuales son conservadores y deberan validarse empiricamente en `022`/`023`.
