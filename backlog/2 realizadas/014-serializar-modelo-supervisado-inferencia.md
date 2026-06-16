# Serializar modelo supervisado para inferencia

## Objetivo

Serializar el modelo supervisado seleccionado y calibrado para que opere exclusivamente en modo inferencia dentro del pipeline productivo.

## Contexto

El entrenamiento y la experimentacion no deben ejecutarse dentro del flujo productivo. La inferencia debe cargar un artefacto versionado y producir probabilidades calibradas de rentabilidad del spread.

## Alcance

- Definir formato de artefacto del modelo, preprocesadores y metadatos.
- Guardar version de dataset, features esperadas, horizonte, fecha de entrenamiento y metricas principales.
- Implementar loader de inferencia en `packages/prediction/`.
- Validar esquema de entrada y orden de features antes de llamar al modelo.
- Bloquear rutas de reentrenamiento dentro del modulo de inferencia.
- Anadir tests de carga, compatibilidad de features y salida probabilistica.

## Criterios de aceptacion

- El artefacto puede cargarse sin acceder al dataset de entrenamiento.
- La inferencia devuelve probabilidad calibrada para `spread_profitable_8d`.
- El loader falla con error claro si faltan features o cambia el esquema.
- Hay tests con un artefacto pequeno o fixture controlado.
- La documentacion separa entrenamiento, calibracion e inferencia.

## Decisiones tecnicas

- La serializacion debe incluir preprocesado y calibrador, no solo el estimador base.
- La version del modelo debe quedar trazable en cada prediccion.

## Pasos realizados

- Configurado Git LFS para versionar artefactos `models/**/*.joblib` sin meter binarios grandes directamente en Git.
- Promocionado el modelo experimental seleccionado desde `model-runs/supervised_direction_recent_1y/operational_default_20260615` a `models/supervised_direction_v1/20260615_operational_default`.
- Anadidos al artefacto versionado:
  - `calibrated_model.joblib`, modelo calibrado completo con preprocesado;
  - `metadata.json`, contrato estable de inferencia con features, threshold, metrica y limitaciones;
  - `training_report.json`, reporte completo de trazabilidad del experimento.
- Creado `packages.prediction.supervised_inference` con loader inference-only, validacion de esquema de features, prediccion por fila o dataframe y errores claros.
- Exportado el loader desde `packages.prediction`.
- Documentado el artefacto en `packages/prediction/README.md`.
- Validado el artefacto real contra una fila de `data/datasets/supervised_direction_recent_1y/test.parquet`.

## Pruebas ejecutadas

- `python -m ruff check packages/prediction/supervised_inference.py packages/prediction/__init__.py tests/unit/test_supervised_inference.py`
- `python -m mypy packages/prediction/supervised_inference.py packages/prediction/__init__.py tests/unit/test_supervised_inference.py`
- `python -m pytest tests/unit/test_supervised_inference.py`
- Carga real: `SupervisedModelArtifact.load(Path('models/supervised_direction_v1/20260615_operational_default'))`

## Bloqueos o riesgos

- Este artefacto es experimental: predice direccion (`is_up`) y se usara como feature MARL, no como regla automatica de compra.
- El modelo final de trading debe sustituirlo cuando tengamos dataset real Steam/BUFF con historico suficiente de beneficio neto.
- Cambios en nombres o unidades de features romperan inferencia, como debe ser; el loader valida el contrato y falla con error claro.
