# Implementar simulador de cartera con trade hold

## Objetivo

Crear el simulador de cartera que aplique trade hold simplificado de 8 dias, comisiones, liquidez y posiciones simuladas.

## Contexto

El entorno PettingZoo y la recompensa MARL necesitan una dinamica de cartera fiable antes de entrenar politicas. El TFM debe validar decisiones sin ejecutar compras reales y medir impacto del capital inmovilizado.

## Alcance

- Modelar cartera y posiciones.
- Aplicar bloqueo simplificado de 8 dias.
- Calcular comisiones por plataforma.
- Exponer estado consultable por el agente Portfolio: capital disponible, capital bloqueado, posiciones abiertas y fechas de liberacion.
- Registrar posiciones abiertas/cerradas.
- Calcular metricas iniciales de rentabilidad, drawdown, exposicion y capital bloqueado.
- Preparar una API interna usable desde el entorno PettingZoo.

## Criterios de aceptacion

- Una decision de compra simulada crea posicion bloqueada.
- La posicion no puede venderse antes de fin de trade hold.
- El simulador puede responder cuanto capital hay disponible y cuanto queda bloqueado.
- Las metricas incluyen rentabilidad neta y capital bloqueado.
- Hay tests unitarios del ciclo de vida de posicion.

## Decisiones tecnicas

- Simulacion antes que operacion real.
- El simulador no debe depender de RLlib, PettingZoo ni modelos ML.

## Pasos realizados

- Creado `packages.simulation.portfolio` con `PortfolioSimulator`, `PortfolioPosition`, `PortfolioMetrics`, `MarketMark` y errores especificos de cartera.
- Implementado ciclo de compra: valida capital, convierte coste a EUR, descuenta capital disponible, crea posicion y calcula `unlock_at` con el trade hold configurado.
- Implementado ciclo de venta: impide vender antes del desbloqueo, aplica fee neto de la plataforma de venta, libera capital como cash disponible y registra profit/return realizado.
- Anadida validacion minima de liquidez mediante `available_quantity` en venta.
- Anadidas metricas consultables para Portfolio: capital disponible, capital bloqueado, invertido abierto, profit realizado/no realizado, equity, peak equity, drawdown y conteo de posiciones locked/open/closed.
- Exportado el simulador desde `packages.simulation`.
- Documentado en `packages/simulation/README.md`.

## Pruebas ejecutadas

- `python -m ruff check packages/simulation/portfolio.py packages/simulation/__init__.py tests/unit/test_portfolio_simulator.py`
- `python -m mypy packages/simulation/portfolio.py packages/simulation/__init__.py tests/unit/test_portfolio_simulator.py`
- `python -m pytest tests/unit/test_portfolio_simulator.py`

## Bloqueos o riesgos

- Las comisiones iniciales reutilizan `default_excel_economics_config`: Steam `0.87`, BUFF `0.975`, CNY/EUR configurable.
- El trade hold queda como `trade_hold_days` configurable, por defecto 8 dias segun el Excel operativo.
- Los limites finos de exposicion, liquidez minima por mercado y riesgo agregado se desarrollan en la tarea 017.
