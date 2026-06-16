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
- Anadidas features derivadas alineadas con la clave primaria operativa: `primary_item_key = item_key + calidad + stattrak`, ademas de claves combinadas por arma/desgaste, skin/desgaste, coleccion/rareza y rareza/desgaste.
- Anadidas features numericas candidatas para ablation: `price_eur`, edad logaritmica, liquidez baja, turnover EUR, ventas por EUR y versiones capadas de retornos, price-vs-MA y sales z-score para controlar outliers extremos.
- El trainer ahora permite ablations sin reconstruir dataset con `--exclude-features` y `--exclude-feature-suffixes`, y reporta resumen por `primary_item_key` en cada umbral.
- Smoke con identidad/derivadas en `model-runs/supervised_direction_recent_1y/identity_features_smoke_20260615`: ganador `random_forest_depth18`. Test ROC-AUC 0,6185, PR-AUC 0,5643, Brier 0,2369. En test, umbral 0,8 da precision 0,935 con 92 senales.
- Ablation quitando identidad/derivadas en `model-runs/supervised_direction_recent_1y/drop_identity_features_smoke_20260615`: reproduce el resultado anterior y mantiene mejor precision alta en test, umbral 0,8 precision 0,946 con 92 senales. Decision provisional: conservar las features nuevas para experimentos, pero no asumir que mejoran el modelo final hasta probar seleccion orientada a precision y mas ventanas temporales.
- Revisado el criterio de seleccion: seleccionar por ROC-AUC no alinea el entrenamiento con el objetivo operativo de alta precision. En validation, `random_forest_depth10` tenia mejor precision a umbral 0,8 que `random_forest_depth18`, aunque peor ROC-AUC.
- Anadido selector configurable `--selection-metric precision_at_threshold --selection-threshold 0.8 --min-selection-signals 50` para elegir candidatos por precision operativa con un minimo de senales en validation.
- Smoke con seleccion por precision en `model-runs/supervised_direction_recent_1y/precision_select_drop_identity_20260615`: ganador `random_forest_depth10`. Validation umbral 0,8: precision 0,892 con 83 senales. Test umbral 0,8: precision 0,961 con 77 senales. No se considera estadistica definitiva porque no hay suficientes senales por `primary_item_key` para afirmar precision por articulo.
- Cambiado el comportamiento por defecto del trainer: seleccion por `precision_at_threshold`, claves de identidad solo como grupos de evaluacion salvo `--include-group-identity-features`, `decision_threshold` escogido solo con validation calibrado y evaluacion por ventanas mensuales en validation/test.
- Simplificada la salida del CLI: imprime resumen operativo y mantiene la respuesta completa en `training_report.json`.
- Smoke con defaults operativos en `model-runs/supervised_direction_recent_1y/operational_default_20260615`: ganador `random_forest_depth18`. Umbral elegido con validation calibrado: 0,85 con 52 senales y precision 0,942. En test al mismo umbral: 53 senales y precision 0,962. Sigue sin ser definitivo porque no hay suficientes senales repetidas por articulo.
- Creado `packages.datasets.trading` y el CLI `python -m apps.cli.build_trading_dataset` para construir un dataset de trading real desde `market_history_points`, usando `price_eur`, fees de Steam/BUFF, horizonte configurable y splits temporales train/validation/test.
- El builder conserva columnas de trazabilidad (`item_id`, `representation_name`, nombre, calidad, StatTrak y dia observado), pero entrena solo con features numericas de mercado y economia: precios Steam/BUFF en EUR, liquidez, spreads, beneficios/retornos actuales y versiones logaritmicas.
- Comprobacion de datos reales de Supabase: ahora mismo hay historico de `steam/sell_price` y `buff163/buy_order_price`, pero no hay `buff163/sell_price`. Por eso el primer dataset real se ha construido con direccion `steam_to_buff_buy_order`; la direccion natural `buff_to_steam_sell` queda bloqueada hasta capturar precio de venta/listing de BUFF.
- Generado `data/datasets/trading_profit_v1` con `--query-start 2025-01-01 --trade-direction steam_to_buff_buy_order --future-tolerance-days 7`. Resultado: 2.331 ejemplos, 50 articulos, train 1.141 filas con tasa positiva 5,08%, validation 453 filas con tasa positiva 0,22% y test 737 filas con tasa positiva 0,14%.
- Smoke de entrenamiento en `model-runs/trading_profit_v1/operational_smoke_20260616`: ganador tecnico `random_forest_depth10`, pero no se considera util para decision operativa. Validation y test tienen solo 1 caso positivo cada uno; por eso ROC-AUC/PR-AUC pueden ser artificialmente altos y la seleccion no encuentra senales a umbrales operativos.
- Decision provisional: el pipeline real de trading ya existe, pero necesitamos mas senal antes de entrenar un modelo fiable. Prioridad de datos: capturar `buff163/sell_price` o listings comparables, aumentar historico con mas dias/articulos, y evaluar targets con margen minimo para no aprender oportunidades teoricas sin liquidez.

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
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_recent_1y --output-dir model-runs/supervised_direction_recent_1y/identity_features_smoke_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_recent_1y --output-dir model-runs/supervised_direction_recent_1y/drop_identity_features_smoke_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting --exclude-features primary_item_key weapon_wear_key skin_wear_key collection_rarity_key rarity_wear_key price_eur log_variant_age_days low_liquidity turnover_eur log_turnover_eur sales_per_price_eur --exclude-feature-suffixes _clipped`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_recent_1y --output-dir model-runs/supervised_direction_recent_1y/precision_select_drop_identity_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting --selection-metric precision_at_threshold --selection-threshold 0.8 --min-selection-signals 50 --exclude-features primary_item_key weapon_wear_key skin_wear_key collection_rarity_key rarity_wear_key price_eur log_variant_age_days low_liquidity turnover_eur log_turnover_eur sales_per_price_eur --exclude-feature-suffixes _clipped`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/supervised_direction_recent_1y --output-dir model-runs/supervised_direction_recent_1y/operational_default_20260615 --max-train-rows 50000 --max-validation-rows 20000 --max-test-rows 20000 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting --exclude-feature-suffixes _clipped`
- `python -m ruff check packages/datasets/trading.py apps/cli/build_trading_dataset.py tests/unit/test_trading_dataset.py`
- `python -m mypy packages/datasets/trading.py apps/cli/build_trading_dataset.py tests/unit/test_trading_dataset.py`
- `python -m pytest tests/unit/test_trading_dataset.py`
- `python -m apps.cli.build_trading_dataset --output data/datasets/trading_profit_v1 --query-start 2025-01-01 --trade-direction steam_to_buff_buy_order --future-tolerance-days 7`
- `python -m apps.cli.train_supervised_model --dataset-dir data/datasets/trading_profit_v1 --output-dir model-runs/trading_profit_v1/operational_smoke_20260616 --max-train-rows 0 --max-validation-rows 0 --max-test-rows 0 --cv-splits 3 --models dummy logistic random_forest hist_gradient_boosting --selection-threshold 0.8 --min-selection-signals 1`
- `python -m pytest tests/unit`

## Bloqueos o riesgos

- La calibracion isotonica necesita suficientes muestras por periodo para no sobreajustar.
- Si el dataset es pequeno o sesgado, el mejor modelo puede ser simple.
- La senal univariante es moderada; los modelos no lineales pueden ayudar, pero hay que validar calibracion y estabilidad temporal, no solo AUC.
- Algunas categoricas son semantica o practicamente duplicadas (`weapon` y `weapon_key`); conviene decidir una representacion unica durante el preprocesado.
- El primer modelo entrenado predice direccion (`is_up`) sobre el dataset historico actual, no todavia rentabilidad real del spread Steam/BUFF a 8 dias. Hay que regenerar un dataset desde `market_items` y `market_history_points` con los precios normalizados antes de declarar este modelo como final de trading.
- Las metricas de precision alta tienen pocas senales y no bastan para afirmar rendimiento "con cualquier articulo"; hay que validar por ventanas temporales multiples y exigir minimo de senales por grupo antes de usar una cifra como evidencia fuerte.
- El siguiente salto real debe ser un dataset de trading desde Supabase con Steam/BUFF, fees y target de beneficio neto futuro; sin eso el modelo solo predice direccion, no oportunidad de compra rentable.
- El primer dataset real revela desbalance extremo en validation/test para `steam_to_buff_buy_order`; no usar sus metricas como evidencia de precision por articulo.
- Sin `buff163/sell_price` no podemos modelar bien la compra en BUFF y venta futura en Steam, que es la direccion mas alineada con el arbitraje operativo original.
