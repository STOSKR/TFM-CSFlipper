# Experimentar modelo supervisado calibrado

## Objetivo

Entrenar, comparar y seleccionar el modelo supervisado de clasificacion tabular que mejor prediga la rentabilidad del spread a 8 dias con probabilidades calibradas.

## Contexto

El `MomentumBaselinePredictor` existente es util para pruebas tempranas, pero no sustituye a la fase experimental. El modelo final debe seleccionarse comparando algoritmos y calibrando probabilidades antes de usarse como feature MARL.

## Alcance

- Explorar features antes de entrenar para detectar ruido, leakage, drift, redundancia y cardinalidad excesiva.
- Definir un plan de feature engineering y preprocesado reproducible.
- Entrenar y comparar algoritmos tabulares como gradient boosting, random forest, regresion logistica u otros candidatos razonables.
- Usar `TimeSeriesSplit` para evitar data leakage temporal.
- Evaluar metricas de clasificacion, ranking y calibracion: precision, recall, F1, ROC-AUC, PR-AUC, Brier score y curvas de calibracion.
- Seleccionar el modelo ganador con criterios explicitos de rendimiento y calibracion.
- Aplicar calibracion isotonica con `CalibratedClassifierCV` al modelo seleccionado.
- Registrar resultados, parametros, versiones de dataset y artefactos.
- Comparar contra `MomentumBaselinePredictor` como baseline, sin asumirlo valido por estar implementado.

## Criterios de aceptacion

- Hay un script o notebook reproducible de experimentacion.
- Los splits respetan el orden temporal y quedan documentados.
- Existe un reporte previo de exploracion de features y decisiones de feature engineering.
- El modelo seleccionado tiene probabilidades calibradas para el target de spread rentable a 8 dias.
- Existe un reporte con metricas comparables entre modelos y baseline.
- Queda justificado por que se elige el modelo ganador.

## Decisiones tecnicas

- El objetivo principal no es solo accuracy, sino utilidad de probabilidades calibradas para la observacion MARL.
- La calibracion es obligatoria independientemente del algoritmo elegido.
- El baseline determinista permanece como referencia experimental, no como modelo final productivo.
- La exploracion de caracteristicas se ejecuta antes del entrenamiento para no optimizar modelos sobre features inestables o contaminadas.

## Pasos realizados

- Movida a progreso tras cerrar `supervised_direction_v1`.
- Antes de entrenar modelos se anade una fase explicita de exploracion de caracteristicas y feature engineering para evitar entrenar sobre ruido, leakage o features inestables.
- Creado `packages.datasets.feature_exploration` y el CLI `python -m apps.cli.explore_supervised_features`.
- Generado `data/datasets/supervised_direction_v1/feature_exploration.json` con muestreo distribuido por split, AUC univariante, correlaciones, drift train/validation/test, cardinalidad categorica, pares numericos redundantes y recomendaciones.
- Resultado inicial: no aparecen sospechosos fuertes de leakage tras excluir `is_safe`; la senal individual mas clara viene de features de momentum/reversion como `price_vs_ma_7d`, `price_vs_ma_14d`, `ret_1d`, `ret_3d`, `ret_7d` y `rsi_14d`.
- `skin_key` queda marcada como categorica de alta cardinalidad; debe tratarse con frequency encoding o target encoding cruzado, no con one-hot directo.
- `sales_z_30d`, `month` y `variant_age_days` quedan marcadas como features con drift y deben probarse con ablation antes de usarse en un modelo productivo.
- Plan de feature engineering para el entrenamiento: comparar todas las features no-leakage contra un set reducido, probar interacciones momentum/RSI/volatilidad, codificar categoricas de baja cardinalidad con one-hot y tratar alta cardinalidad solo dentro de folds temporales.

## Pruebas ejecutadas

- `python -m ruff check packages/datasets/feature_exploration.py apps/cli/explore_supervised_features.py tests/unit/test_feature_exploration.py`
- `python -m mypy packages/datasets/feature_exploration.py apps/cli/explore_supervised_features.py tests/unit/test_feature_exploration.py`
- `python -m pytest tests/unit/test_feature_exploration.py`
- `python -m apps.cli.explore_supervised_features --dataset-dir data/datasets/supervised_direction_v1 --sample-rows-per-split 200000`

## Bloqueos o riesgos

- La calibracion isotonica necesita suficientes muestras por periodo para no sobreajustar.
- Si el dataset es pequeno o sesgado, el mejor modelo puede ser simple.
- La senal univariante es moderada; los modelos no lineales pueden ayudar, pero hay que validar calibracion y estabilidad temporal, no solo AUC.
- Algunas categoricas son semantica o practicamente duplicadas (`weapon` y `weapon_key`); conviene decidir una representacion unica durante el preprocesado.
