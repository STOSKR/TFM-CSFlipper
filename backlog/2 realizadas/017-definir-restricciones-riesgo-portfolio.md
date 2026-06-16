# Definir restricciones de riesgo para Portfolio

## Objetivo

Definir las reglas y limites de riesgo que usara el agente Portfolio para gestionar exposicion global, capital bloqueado y liquidez.

## Contexto

La tarea antigua de perfiles de riesgo y votacion se transforma en restricciones de entorno y senales para el agente Portfolio. Ya no se implementan votantes Conservador, Moderado o Arriesgado como agentes separados.

## Alcance

- Definir limites configurables de exposicion por item, plataforma, rareza o grupo.
- Definir limites de capital bloqueado por trade hold.
- Definir umbrales de liquidez minima y volatilidad maxima.
- Exponer estas restricciones al simulador y al espacio de observacion del agente Portfolio.
- Generar metricas de violacion o cercania al limite.
- Anadir tests unitarios de reglas de riesgo.

## Criterios de aceptacion

- Las restricciones son configurables fuera del codigo de agentes.
- Portfolio puede observar capital disponible, capital bloqueado, exposicion y riesgo agregado.
- Las penalizaciones de recompensa pueden reutilizar estas metricas.
- No queda logica de perfiles duplicada dentro de agentes.

## Decisiones tecnicas

- Reglas deterministas iniciales para controlar el entorno.
- La politica MARL aprende acciones sobre estas senales, no reemplaza la validacion basica de riesgo.

## Pasos realizados

- Implementado `packages.simulation.risk` con reglas deterministas para Portfolio:
  limite por posicion, articulo, plataforma, capital bloqueado, caja minima,
  liquidez minima y volatilidad maxima opcional.
- Anadidos contratos ligeros `PortfolioRiskConfig`, `RiskCandidate`,
  `RiskLimitMetric` y `PortfolioRiskSnapshot`.
- `evaluate_portfolio_risk()` devuelve violaciones, avisos y un mapa numerico
  `observation` preparado para convertirse en features del entorno MARL.
- Integrado `PortfolioRiskConfig` en `packages.runtime_config` y en
  `csflipper_config.toml` mediante la seccion `[risk]`.
- Exportada la capa de riesgo desde `packages.simulation`.
- Documentada la capa de riesgo en `packages/simulation/README.md`.

## Pruebas ejecutadas

- `python -m ruff check packages/simulation/risk.py packages/simulation/__init__.py packages/runtime_config.py tests/unit/test_portfolio_risk.py tests/unit/test_runtime_config.py`
- `python -m mypy packages/simulation/risk.py packages/simulation/__init__.py packages/runtime_config.py tests/unit/test_portfolio_risk.py tests/unit/test_runtime_config.py`
- `python -m pytest tests/unit/test_portfolio_risk.py tests/unit/test_runtime_config.py tests/unit/test_portfolio_simulator.py`

## Bloqueos o riesgos

- Ajustar thresholds con datos reales.
- Los limites iniciales son conservadores y editables; no deben tratarse como
  calibracion final hasta validarlos con simulaciones historicas.
