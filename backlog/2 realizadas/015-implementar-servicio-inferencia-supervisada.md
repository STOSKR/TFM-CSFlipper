# Implementar servicio de inferencia supervisada

## Objetivo

Crear el servicio que consume snapshots o features recientes, invoca el modelo supervisado calibrado y devuelve probabilidades listas para ser usadas por los agentes MARL.

## Contexto

La tarea antigua de Agente Analista SPADE se adapta a la arquitectura MARL. Ya no debe implementarse como agente que envia reportes al Broker, sino como servicio puro de inferencia que los pipelines y entornos pueden llamar.

## Alcance

- Crear una interfaz de inferencia en `packages/prediction/`.
- Transformar snapshots recientes en el mismo contrato de features usado en entrenamiento.
- Invocar el artefacto serializado en modo inferencia.
- Devolver probabilidad calibrada, version del modelo, timestamp y features snapshot.
- Persistir predicciones cuando el flujo lo requiera.
- Emitir eventos o registros de trazabilidad sin acoplarse a SPADE.
- Mantener `MomentumBaselinePredictor` como fallback experimental o fixture, no como predictor principal.

## Criterios de aceptacion

- El servicio no entrena ni recalibra modelos.
- La salida es determinista para un artefacto y una entrada dados.
- La probabilidad puede incorporarse directamente al espacio de observacion MARL.
- Hay tests unitarios del contrato de entrada/salida.
- Queda documentado que no existe todavia un agente MARL por el simple hecho de tener este servicio.

## Decisiones tecnicas

- La inferencia vive en `packages/prediction/`.
- Los agentes Scout, Trader y Portfolio consumiran la probabilidad como feature, no como decision final.
- SPADE/Broker/FIPA quedan fuera del camino principal de esta arquitectura.

## Pasos realizados

- Creado `packages.prediction.supervised_service` como fachada inference-only sobre `SupervisedModelArtifact`.
- Anadido `SupervisedInferenceService.load()` con ruta por defecto al artefacto versionado `models/supervised_direction_v1/20260615_operational_default`.
- Anadidos contratos de salida `SupervisedInferenceResult` y `SupervisedBatchInferenceResult` con modelo, probabilidad, threshold, senal, target, timestamps, correlacion y snapshot de features usado.
- Anadido `SupervisedPredictionSink` opcional para persistir o emitir predicciones sin acoplar el servicio a Supabase, SPADE ni outbox.
- Exportado el servicio desde `packages.prediction`.
- Documentado el servicio en `packages/prediction/README.md`.
- Validado el servicio con el artefacto real y una fila de `data/datasets/supervised_direction_recent_1y/test.parquet`.

## Pruebas ejecutadas

- `python -m ruff check packages/prediction/supervised_service.py packages/prediction/__init__.py tests/unit/test_supervised_service.py`
- `python -m mypy packages/prediction/supervised_service.py packages/prediction/__init__.py tests/unit/test_supervised_service.py`
- `python -m pytest tests/unit/test_supervised_service.py`
- Prueba real: `SupervisedInferenceService.load().score_frame(...)` sobre una fila del dataset versionado local.

## Bloqueos o riesgos

- El servicio consume feature snapshots ya calculados con el contrato exacto del modelo. La transformacion desde snapshots live completos a las 46 features actuales sigue siendo una responsabilidad separada del pipeline de features online.
- El artefacto actual predice direccion (`is_up`), no beneficio neto real Steam/BUFF. Debe usarse como feature experimental para MARL, no como regla automatica de compra.
