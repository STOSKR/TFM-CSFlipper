# Validación recuperada, 10 de agosto de 2026

Este registro repite las comprobaciones que se habían ejecutado antes de la pérdida del directorio de trabajo. Los artefactos pesados de datos y modelos se regeneran bajo `data/experiments/`, que permanece fuera de Git. Las métricas y comandos de este documento permiten repetirlos.

## Pruebas automatizadas

Comando ejecutado con la configuración local de base de datos:

```powershell
python -m pytest -q
```

Resultado: **276 passed in 26.85s**.

- 273 pruebas unitarias cubren economía, OCR, adquisición, scraping, datasets, simulador, MARL y servidor web.
- 3 integraciones comprueban el esquema de mercado vigente en PostgreSQL.
- Las integraciones se ejecutan dentro de una transacción externa que se revierte al terminar.

Las pruebas de integración verifican:

1. Inserción de un snapshot y dos puntos históricos.
2. Actualización de la cotización de un mismo artículo sin crear una segunda variante.
3. Persistencia de una señal de oportunidad enlazada con el artículo.

## Corte temporal de marzo

Configuración común:

```text
Inicio de datos:       2025-12-01
Dirección:             BUFF listing -> Steam listing
Horizonte:             8 días
Purga entre bloques:   8 días
Retorno mínimo:        10 %
Calibración:           sigmoide
Selección:             precisión a 0.85, mínimo 3 señales
```

El dataset contiene 19 artículos. La división resultante fue:

| Bloque | Filas | Intervalo | Tasa positiva |
|---|---:|---|---:|
| Entrenamiento | 171 | 03 dic. 2025 a 20 ene. 2026 | 92,98 % |
| Validación | 76 | 02 feb. a 20 feb. 2026 | 98,68 % |
| Prueba | 95 | 04 mar. a 28 mar. 2026 | 89,47 % |

| Configuración | Candidato seleccionado | ROC-AUC | Brier | Precisión a 0,85 | Señales |
|---|---|---:|---:|---:|---:|
| Logística con histórico | `logistic_l2_c3_0` | 0,641 | 0,075 | 0,929 | 85 |
| Logística sin histórico | `logistic_l2_c0_3` | 0,760 | 0,072 | 0,970 | 67 |
| Random forest | `random_forest_depth10` | 0,742 | 0,074 | 0,942 | 86 |
| Todos los candidatos | `hist_gradient_boosting_lr0_1` | 0,649 | 0,082 | 0,915 | 82 |

La versión sin retardos, cambios, retornos y ventanas móviles supera a la logística con histórico en este corte. No se interpreta como una conclusión general, ya que la muestra es pequeña y está dominada por casos positivos.

## Corte temporal de mayo

El mismo protocolo genera 361 filas de entrenamiento, 76 de validación y 95 de prueba. Validación y prueba tienen 100 % de etiquetas positivas. No se entrena ni se compara un clasificador en este corte porque ROC-AUC no está definido con una sola clase.

## Regeneración

```powershell
python -m apps.cli.build_trading_dataset `
  --output data/experiments/walkforward_20260810/march `
  --trade-direction buff_to_steam_sell `
  --horizon-days 8 --purge-gap-days 8 `
  --min-profit-eur 0 --min-return 0.1 `
  --start-date 2025-12-01 `
  --validation-start 2026-02-01 `
  --test-start 2026-03-01 --test-end 2026-04-01 `
  --query-start 2025-12-01

python -m apps.cli.train_supervised_model `
  --dataset-dir data/experiments/walkforward_20260810/march `
  --output-dir data/experiments/walkforward_20260810/march_static `
  --models logistic --cv-splits 2 --calibration-method sigmoid `
  --selection-metric precision_at_threshold `
  --selection-threshold 0.85 --min-selection-signals 3 `
  --exclude-feature-suffixes _lag_1d _change_1d _return_1d `
    _lag_3d _change_3d _return_3d _lag_7d _change_7d _return_7d `
    _rolling_mean_7d _rolling_std_7d

python -m apps.cli.render_march_experiment_figure
```

La figura final se escribe en `TFM/figures/experimentacion/01_modelos_marzo.png` y se utiliza en la memoria.
