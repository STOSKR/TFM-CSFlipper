# Experimentar modelo supervisado calibrado

## Objetivo

Entrenar, comparar y seleccionar el modelo supervisado de clasificacion tabular que mejor prediga la rentabilidad del spread a 7 dias con probabilidades calibradas.

## Contexto

El `MomentumBaselinePredictor` existente es util para pruebas tempranas, pero no sustituye a la fase experimental. El modelo final debe seleccionarse comparando algoritmos y calibrando probabilidades antes de usarse como feature MARL.

## Alcance

- Entrenar y comparar algoritmos tabulares como gradient boosting, random forest, regresion logistica u otros candidatos razonables.
- Usar `TimeSeriesSplit` para evitar data leakage temporal.
- Evaluar metricas de clasificacion, ranking y calibracion: precision, recall, F1, ROC-AUC, PR-AUC, Brier score y curvas de calibracion.
- Seleccionar el modelo ganador con criterios explicitos de rendimiento y calibracion.
- Aplicar calibracion isotónica con `CalibratedClassifierCV` al modelo seleccionado.
- Registrar resultados, parametros, versiones de dataset y artefactos.
- Comparar contra `MomentumBaselinePredictor` como baseline, sin asumirlo valido por estar implementado.

## Criterios de aceptacion

- Hay un script o notebook reproducible de experimentacion.
- Los splits respetan el orden temporal y quedan documentados.
- El modelo seleccionado tiene probabilidades calibradas para el target de spread rentable a 7 dias.
- Existe un reporte con metricas comparables entre modelos y baseline.
- Queda justificado por que se elige el modelo ganador.

## Decisiones tecnicas

- El objetivo principal no es solo accuracy, sino utilidad de probabilidades calibradas para la observacion MARL.
- La calibracion es obligatoria independientemente del algoritmo elegido.
- El baseline determinista permanece como referencia experimental, no como modelo final productivo.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- La calibracion isotónica necesita suficientes muestras por periodo para no sobreajustar.
- Si el dataset es pequeno o sesgado, el mejor modelo puede ser simple.

