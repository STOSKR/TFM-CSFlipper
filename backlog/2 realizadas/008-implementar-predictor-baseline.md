# Implementar predictor baseline

## Objetivo

Crear un primer predictor simple para generar senales antes de implementar LSTM o modelos avanzados.

## Contexto

Un baseline permite probar el flujo completo adquisicion -> prediccion -> votacion -> decision sin esperar al entrenamiento ML avanzado.

## Alcance

- Calcular features iniciales sobre historico.
- Implementar modelo simple basado en momentum/media movil/reglas estadisticas.
- Anadir prefiltro de candidatos para priorizar que articulos merecen scraping profundo o evaluacion completa.
- Generar `probability_up`, `expected_return` y `confidence`.
- Persistir predicciones.
- Anadir tests unitarios.

## Criterios de aceptacion

- El predictor funciona con historico minimo.
- La salida usa contratos compartidos.
- El predictor puede evaluar una lista de candidatos normalizados antes de la votacion.
- Los resultados son deterministas en tests.
- Queda documentada la limitacion del baseline.

## Decisiones tecnicas

- Baseline antes de LSTM.
- La inferencia vive en `packages/prediction/`.
- La persistencia de predicciones usa `PredictionIngestionRepository` y emite `PredictionCompleted`.

## Pasos realizados

- Implementado `MomentumBaselinePredictor`.
- Implementadas features de momentum, medias moviles, volatilidad y tendencia de volumen.
- Implementado prefiltro `prioritize_candidates`.
- La salida genera `Prediction` de dominio y `PredictionCompletedMessage`.
- Implementada persistencia de predicciones y evento outbox.
- Documentada la limitacion del baseline en `packages/prediction/README.md`.

## Pruebas ejecutadas

- `python -m pytest`
- `python -m ruff check .`
- `python -m mypy packages apps tests`

## Bloqueos o riesgos

- El baseline no aprende patrones; solo transforma senales estadisticas simples.
- Requiere historico suficiente para que momentum y volatilidad tengan significado.
