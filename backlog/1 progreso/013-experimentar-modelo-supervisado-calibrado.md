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
- Creado `packages.datasets.supervised_coverage` y el CLI `python -m apps.cli.analyze_supervised_coverage` para comprobar cobertura por split antes de entrenar.
- Resultado de cobertura de `supervised_direction_v1`: train 5.139.028 filas y 2.587 variantes, validation 688.860 filas y 2.790 variantes, test 189.154 filas y 2.674 variantes. Hay 2.265 variantes presentes en los tres splits, 393 variantes de validation no vistas en train y 393 variantes de test no vistas en train.
- Decision sobre split: el split temporal actual es correcto para evitar leakage; las variantes no vistas se mantienen porque simulan objetos nuevos o historiales recientes. Hay que reportar metricas globales y, mas adelante, metricas separadas para variantes vistas/no vistas.
- Creado `packages.prediction.supervised_training` y el CLI `python -m apps.cli.train_supervised_model` con busqueda reproducible de hiperparametros inicial: dummy, regresion logistica L2, random forest e histogram gradient boosting, con `TimeSeriesSplit` y calibracion posterior.
- Primer smoke de entrenamiento en `model-runs/supervised_direction_v1/smoke_20260615` usando muestra de train/validation/test: ganador `random_forest_depth10`. Validation ROC-AUC 0,6334, PR-AUC 0,5192, Brier 0,2222. Test ROC-AUC 0,6493, PR-AUC 0,5549, Brier 0,2229.
- Los artefactos intermedios de entrenamiento quedan en `model-runs/`, carpeta ignorada por git. El modelo final se versionara solo cuando se seleccione explicitamente.
- Para el dataset actual el precio usado sigue siendo `price_cents` de Steam; cuando generemos el dataset desde Supabase con `price_eur`/`price_cny`, el entrenamiento debe usar preferentemente `price_eur` para el modelo base y conservar `price_cny` como feature alternativa/ablation si aporta senal del mercado BUFF.
- Anadido soporte de ventana reciente al builder con `--start-date`, para poder entrenar solo con datos contemporaneos y evitar que mercados antiguos dominen el ajuste.
- Generado `data/datasets/supervised_direction_recent_1y` con datos desde 2025-04-12, validation desde 2026-01-01 y test desde 2026-03-01. Split: train 522.132 filas, validation 115.508, test 73.646. Cobertura: 2.530 variantes en los tres splits y solo 10 variantes no vistas en train para validation/test.
- Smoke reciente en `model-runs/supervised_direction_recent_1y/smoke_20260615`: ganador `random_forest_depth18`. Validation ROC-AUC 0,6540, PR-AUC 0,5365, Brier 0,2178. Test ROC-AUC 0,6163, PR-AUC 0,5645, Brier 0,2368.
- Anadida curva de umbrales al reporte de entrenamiento para optimizar precision frente a numero de senales. En el smoke reciente, test a umbral 0,5 da precision 0,713 con 1.360 senales; a umbral 0,8 da precision 0,946 con 92 senales; a umbral 0,9 da precision 1,0 con 16 senales, demasiado pocas para confiar aun sin validacion adicional.

## Pruebas ejecutadas

- `python -m ruff check packages/datasets/feature_exploration.py apps/cli/explore_supervised_features.py tests/unit/test_feature_exploration.py`
- `python -m mypy packages/datasets/feature_exploration.py apps/cli/explore_supervised_features.py tests/unit/test_feature_exploration.py`
- `python -m pytest tests/unit/test_feature_exploration.py`
- `python -m apps.cli.explore_supervised_features --dataset-dir data/datasets/supervised_direction_v1 --sample-rows-per-split 200000`
- `python -m apps.cli.analyze_supervised_coverage --dataset-dir data/datasets/supervised_direction_v1 --output model-runs/supervised_direction_v1/coverage_report.json`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_v1 --output-dir model-runs/supervised_direction_v1/smoke_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting`
- `python -m ruff check packages/datasets/supervised_coverage.py apps/cli/analyze_supervised_coverage.py packages/prediction/supervised_training.py apps/cli/train_supervised_model.py tests/unit/test_supervised_coverage.py`
- `python -m mypy packages/datasets/supervised_coverage.py apps/cli/analyze_supervised_coverage.py packages/prediction/supervised_training.py apps/cli/train_supervised_model.py tests/unit/test_supervised_coverage.py`
- `python -m pytest tests/unit`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_v1 --output-dir model-runs/supervised_direction_v1/check_20260615 --max-train-rows 3000 --max-validation-rows 1200 --max-test-rows 1200 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting`
- `python -m apps.cli.build_supervised_dataset --input data/direction_dataset_engineered.parquet --output data/datasets/supervised_direction_recent_1y --start-date 2025-04-12 --validation-start 2026-01-01 --test-start 2026-03-01`
- `python -m apps.cli.analyze_supervised_coverage --dataset-dir data/datasets/supervised_direction_recent_1y --output model-runs/supervised_direction_recent_1y/coverage_report.json`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_recent_1y --output-dir model-runs/supervised_direction_recent_1y/smoke_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting`

## Bloqueos o riesgos

- La calibracion isotonica necesita suficientes muestras por periodo para no sobreajustar.
- Si el dataset es pequeno o sesgado, el mejor modelo puede ser simple.
- La senal univariante es moderada; los modelos no lineales pueden ayudar, pero hay que validar calibracion y estabilidad temporal, no solo AUC.
- Algunas categoricas son semantica o practicamente duplicadas (`weapon` y `weapon_key`); conviene decidir una representacion unica durante el preprocesado.
- El primer modelo entrenado predice direccion (`is_up`) sobre el dataset historico actual, no todavia rentabilidad real del spread Steam/BUFF a 8 dias. Hay que regenerar un dataset desde `market_items` y `market_history_points` con los precios normalizados antes de declarar este modelo como final de trading.
