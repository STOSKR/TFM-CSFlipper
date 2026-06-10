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
