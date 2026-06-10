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

La configuracion `default_excel_economics_config()` replica los supuestos observados en el Excel, incluido `Fecha C + 8`. Si el TFM normaliza el trade hold a 7 dias, debe pasarse `trade_hold_days=7` de forma explicita.
