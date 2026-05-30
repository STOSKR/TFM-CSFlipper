# Prediction Package

Inferencia y scoring predictivo.

## Baseline

`MomentumBaselinePredictor` es un baseline determinista para probar el flujo completo antes de entrenar modelos avanzados. Usa:

- momentum a 3 y 7 observaciones.
- medias moviles corta/larga.
- volatilidad reciente.
- tendencia de volumen.

Limitacion principal: no aprende patrones; solo convierte senales estadisticas simples en `probability_up`, `expected_return` y `confidence`.
