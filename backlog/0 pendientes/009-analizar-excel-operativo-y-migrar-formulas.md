# Analizar Excel operativo y migrar formulas

## Objetivo

Revisar el Excel actual que calcula oportunidades, rentabilidad y seguimiento de compras para migrar sus formulas utiles al sistema.

## Contexto

El Excel ya resuelve parte del flujo manual: calculos, formulas y seguimiento operativo. Antes de construir el dataset supervisado y la recompensa MARL, conviene entender que formulas funcionan, cuales fallan y que datos usa cada una.

## Alcance

- Inventariar hojas, columnas y formulas relevantes.
- Identificar inputs necesarios: precios, comisiones, historico, buy orders, fechas y cantidades.
- Separar formulas de rentabilidad, seguimiento de compras, exposicion y prediccion.
- Documentar formulas actuales y supuestos.
- Comparar formulas actuales con la estructura de `market_items`, `market_snapshots` y el esquema canonico.
- Proponer que formulas se migran tal cual, cuales se ajustan y cuales se descartan.
- Crear tests con ejemplos del Excel para validar los calculos migrados.

## Criterios de aceptacion

- Existe un documento o modulo con las formulas relevantes explicadas.
- Cada formula migrada tiene al menos un caso de prueba basado en el Excel.
- Queda claro que datos de Supabase necesita cada calculo.
- La formula de margen/rentabilidad queda versionada para poder usarla como etiqueta supervisada y como componente de recompensa.

## Decisiones tecnicas

- No mezclar formulas operativas con scraping.
- Mantener formulas de decision en un modulo propio, reutilizable por dataset, simulador, web y evaluacion.
- Usar el Excel como especificacion inicial, no como fuente permanente de verdad.

## Pasos realizados

- Recibido `Calculos steam buff.xlsm` en `material_a_integrar/009-analizar-excel-operativo-y-migrar-formulas/`.
- Inspeccionado el libro sin ejecutar macros.
- Inventariadas 9 hojas: `Trades`, `Pagos`, `Calculadora`, `Historial de compras`, `Calculadora (2)`, `Fees`, `Buy Orders`, `TradeUps` y `Calendario`.
- Identificadas tablas `Tabla2`, `Tabla3`, `Historial` y `Tabla35`.
- Extraidas formulas clave de conversion EUR/CNY, fees por plataforma, profit, rentabilidad porcentual, trade hold, capital bloqueado y matching compra/venta.
- Documentado el analisis inicial en `docs/excel-operativo-analysis.md`.
- Creado `packages/simulation/economics.py` con formulas puras de conversion, fees, valor efectivo, fecha de desbloqueo, profit y rentabilidad.
- Anadidos tests basados en ejemplos del Excel en `tests/unit/test_excel_economics.py`.

## Pruebas ejecutadas

- Inspeccion estatica del `.xlsm` como Office Open XML sin ejecutar macros.
- `python -m pytest tests/unit/test_excel_economics.py`
- `python -m pytest tests/unit`
- `python -m ruff check packages/simulation tests/unit/test_excel_economics.py`
- `python -m mypy packages/simulation tests/unit/test_excel_economics.py`
- `python -m ruff check .`

No completadas por estado previo del entorno/repositorio:

- `python -m pytest`: fallan 3 tests de integracion porque la base de datos configurada no tiene `assets` ni `outbox_events`.
- `python -m mypy packages apps tests`: fallan anotaciones/tipos existentes en tests no modificados.

## Bloqueos o riesgos

- Confirmar si `Fecha C + 8` debe replicarse o normalizarse al trade hold teorico de 7 dias.
- Confirmar el significado operativo de los factores `0.8`, `0.87`, `0.975`, `0.98` y `0.93`.
- Los tipos de cambio aparecen hardcodeados en varias formas (`8`, `8.1`, `8.25`, `D28`, `D35`) y deben versionarse por fecha.
- Algunas formulas dependen de datos manuales que todavia no existen en Supabase.
