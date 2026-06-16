# Prediction Package

Inferencia y scoring predictivo.

## Baseline

`MomentumBaselinePredictor` es un baseline determinista para probar el flujo completo antes de entrenar modelos avanzados. Usa:

- momentum a 3 y 7 observaciones.
- medias moviles corta/larga.
- volatilidad reciente.
- tendencia de volumen.

Limitacion principal: no aprende patrones; solo convierte senales estadisticas simples en `probability_up`, `expected_return` y `confidence`.

## Modelo supervisado versionado

`packages.prediction.supervised_inference` carga artefactos ya entrenados desde `models/`.

El artefacto promocionado actual es experimental:

`models/supervised_direction_v1/20260615_operational_default`

Incluye:

- `calibrated_model.joblib`, gestionado con Git LFS;
- `metadata.json`, contrato estable de inferencia;
- `training_report.json`, trazabilidad completa del experimento.

Este modelo predice `direction_up_probability` y debe usarse como feature para MARL, no como regla automatica de compra. El modelo final de trading se reentrenara cuando haya mas historico real de Steam/BUFF con beneficio neto.

`packages.prediction.supervised_service` envuelve el artefacto en una interfaz de servicio:

- recibe feature snapshots con el contrato exacto del artefacto;
- devuelve probabilidad, threshold, version del modelo, timestamp y features usadas;
- puede registrar resultados mediante un sink opcional;
- no entrena, recalibra ni decide compras.

La transformacion desde snapshots live completos a las 46 features del modelo actual sigue siendo una responsabilidad separada. Este servicio valida y ejecuta inferencia sobre features ya calculadas.
