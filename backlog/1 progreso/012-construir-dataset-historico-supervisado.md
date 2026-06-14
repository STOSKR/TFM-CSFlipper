# Construir dataset historico supervisado

## Objetivo

Implementar el pipeline de extraccion y procesamiento de datos historicos de precios, spreads, volumen y tendencias de Steam Market y Buff163 para entrenar el modelo supervisado.

## Contexto

El modelo supervisado predice la probabilidad calibrada de que el spread entre Steam y BUFF siga siendo rentable en un horizonte simplificado de 8 dias. Esa probabilidad sera despues una feature dentro de la observacion de los agentes MARL.

## Alcance

- Extraer historico desde `market_items`, `market_history_points` y fuentes historicas validadas.
- Alinear observaciones de Steam y Buff163 por item, timestamp, moneda y ventana temporal.
- Calcular features de precio, spread neto, volumen, liquidez, tendencia, volatilidad y comisiones.
- Construir la etiqueta supervisada: spread rentable a 8 dias segun formula versionada.
- Separar dataset de entrenamiento, validacion y test respetando orden temporal.
- Guardar dataset versionado con metadatos de generacion, rango temporal y filtros aplicados.
- Anadir tests de transformaciones criticas y casos de leakage temporal.

## Criterios de aceptacion

- Existe un comando reproducible para generar el dataset supervisado.
- Cada fila tiene features, target de 8 dias y claves de trazabilidad al item y puntos historicos fuente.
- No se usan datos posteriores al timestamp de decision para construir features.
- La etiqueta de rentabilidad neta usa comisiones y trade hold documentados.
- El dataset puede consumirse por experimentos sin depender de scraping en vivo.

## Decisiones tecnicas

- Separar generacion de dataset de entrenamiento de la inferencia productiva.
- Versionar formulas y parametros usados en la etiqueta.
- Priorizar datos tabulares antes de modelos secuenciales complejos.

## Pasos realizados

- Movida a progreso tras normalizar el esquema operativo a `market_items` +
  `market_history_points`.
- Revisado `data/direction_dataset_model_sample.parquet`: 1000 filas, 1 variante
  (`heavy_m249_aztec__FN_st0`), granularidad diaria, rango 2019-11-17 a 2022-08-12,
  con features tecnicas y target direccional ya precomputado.
- Confirmado que el parquet es un dataset direccional Steam/precio+ventas, no un historico
  bruto Steam-BUFF alineado.
- Creado `packages.datasets.historical_parquet` para inspeccionar el parquet, validar columnas
  obligatorias y transformarlo a snapshots persistibles con historico Steam.
- Creado CLI `python -m apps.cli.import_history_parquet` para inspeccionar/importar el parquet
  a `market_items` y `market_history_points`; por defecto funciona en dry-run y requiere
  `--persist` para escribir en BD.
- Creado CLI `python -m apps.cli.refresh_market_history` para leer `market_items` desde BD,
  reutilizar los workers de Steam/BUFF y actualizar estado actual + puntos historicos.
- Definida decision: ROI, net profit y break-even se recalcularan bajo demanda para web,
  recomendaciones o datasets; no se guardan como verdad persistida porque el precio cambia.
- Incorporado el parquet completo `data/direction_dataset_engineered.parquet`: 6.017.042 filas,
  52 columnas, 6 row groups y 2.980 variantes, con rango temporal hasta 2026-04-12.
- Adaptado el importador del parquet para iterar por batches/row groups y escribir historico
  por lotes, evitando cargar todo el dataset en memoria.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_historical_parquet.py tests/unit/test_refresh_market_history.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check packages/datasets/historical_parquet.py apps/cli/import_history_parquet.py apps/cli/refresh_market_history.py tests/unit/test_historical_parquet.py tests/unit/test_refresh_market_history.py`
- `python -m mypy packages/datasets/historical_parquet.py apps/cli/import_history_parquet.py apps/cli/refresh_market_history.py tests/unit/test_historical_parquet.py tests/unit/test_refresh_market_history.py`
- `python -m apps.cli.import_history_parquet --input data/direction_dataset_model_sample.parquet --currency EUR`
- `python -m apps.cli.import_history_parquet --input data/direction_dataset_engineered.parquet --currency EUR --limit-variants 3`

## Bloqueos o riesgos

- La calidad del dataset depende de disponer de historico real suficiente de ambas plataformas.
- El cambio de moneda o comisiones puede invalidar etiquetas si no queda versionado.
- El parquet completo trae historico Steam/precio+ventas y targets direccionales, pero no trae
  BUFF; para el modelo de spread neto habra que alinearlo despues con historico BUFF.
