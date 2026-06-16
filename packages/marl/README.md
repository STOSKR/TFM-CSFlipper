# MARL Package

Primer andamiaje del entorno multiagente.

`packages.marl.market_env` define un entorno paralelo minimo para Scout, Trader y Portfolio:

- `reset()` devuelve observaciones locales por agente;
- `step(actions)` acepta acciones simultaneas;
- solo se ejecuta una compra si Scout marca, Trader compra y Portfolio aprueba;
- la compra usa `PortfolioSimulator`;
- la validacion usa `evaluate_portfolio_risk`;
- la recompensa compartida inicial usa el retorno inmediato del ejemplo.

Todavia no es el wrapper final PettingZoo/RLlib. La intencion es estabilizar primero los
contratos de observacion, accion, simulador y riesgo antes de anadir la dependencia formal y el
entrenamiento.
