# Simulation Package

Simulador de mercado CS2.

Consulta [../../docs/simulation-model.md](../../docs/simulation-model.md).

## Formulas economicas

`packages.simulation.economics` contiene las primeras formulas migradas del Excel operativo:

- conversion EUR/CNY;
- fees netos por plataforma;
- valor efectivo de saldo Steam;
- fecha de desbloqueo por trade hold;
- profit realizado y rentabilidad.

La configuracion `default_excel_economics_config()` replica los supuestos confirmados del Excel:

- `Fecha C + 8` como simplificacion de compra + 7 dias + desbloqueo a la siguiente ventana de las 09:00.
- Steam cobra `0.87` sobre venta.
- Sacar saldo de Steam a banco aplica perdida conservadora del 20%, con escenarios de referencia 10%, 15% y 20%.
- BUFF aplica fee neto `0.975`.

CSFloat y Skinport quedan fuera del dominio principal del TFM por ahora.

## Simulador de cartera

`packages.simulation.portfolio` contiene el simulador determinista que usara el entorno MARL:

- compras con descuento de capital disponible;
- posiciones bloqueadas hasta `unlock_date`;
- ventas solo cuando termina el trade hold;
- comisiones por plataforma reutilizando `MarketEconomicsConfig`;
- validacion minima de liquidez mediante cantidad disponible;
- metricas de capital disponible, capital bloqueado, profit realizado, profit no realizado, equity y drawdown.

El simulador no depende de PettingZoo, RLlib ni modelos ML. El entorno multiagente lo usara como motor de contabilidad.

## Restricciones de riesgo

`packages.simulation.risk` contiene reglas deterministas configurables para el futuro agente
Portfolio:

- limite por posicion;
- limite agregado por articulo;
- limite agregado por plataforma;
- limite de capital bloqueado por trade hold;
- caja minima disponible;
- liquidez minima y volatilidad maxima opcional para candidatos.

La salida de `evaluate_portfolio_risk()` incluye violaciones, avisos y un mapa numerico
`observation` preparado para convertirse en features del espacio de observacion MARL. Estas
reglas no sustituyen a la politica aprendida: controlan el entorno y exponen senales de riesgo.
