# Cribado de la recompensa híbrida MARL

## Objetivo

Seleccionar mediante validación el peso de la recompensa común, `g`, antes de
realizar los entrenamientos largos y de consultar el conjunto de prueba.

## Condiciones congeladas

- Conjunto versionado: `data/datasets/trading_profit_v1`.
- Separación temporal: entrenamiento, validación y prueba definidos por el
  conjunto versionado.
- Capital inicial: 1.000 EUR.
- Longitud de episodio: 14 días.
- Entrenamiento de cribado: 4 iteraciones y 3 episodios por iteración.
- Recompensa de cartera: peso de ROI `a=0,60`, penalización de espera
  adicional `b=0,01` y penalización de restricciones `c=0,80`.
- Banda flexible de inversión: objetivo 50 % con tolerancia de 5 puntos
  porcentuales.
- Los experimentos de cribado se ejecutan con `--skip-test`. Por tanto, sus
  resultados no inspeccionan el conjunto de prueba.

## Cribado inicial

Se mantiene la semilla 7 y se modifica únicamente el peso común `g`.

| Configuración | Mejor iteración | Rentabilidad de validación |
|---|---:|---:|
| `g=0,50` | 2 | 14,81 % |
| `g=0,70` | 2 | 14,60 % |
| `g=0,90` | 2 | **18,16 %** |

La configuración `g=0,90` se selecciona de forma provisional para comprobar
su estabilidad con otras semillas.

## Réplicas de la configuración seleccionada

| Semilla | Mejor iteración | Rentabilidad de validación |
|---:|---:|---:|
| 7 | 2 | 18,16 % |
| 19 | 3 | 16,76 % |
| 31 | 3 | 17,91 % |

La rentabilidad media de validación es 17,61 % y la desviación estándar muestral
es 0,75 puntos porcentuales. Estos resultados son un cribado breve. No deben
presentarse como evaluación final ni utilizarse para afirmar rentabilidad fuera
del histórico empleado.

## Fase de confirmación planificada

1. Entrenar `g=0,90` con las semillas 7, 19 y 31 durante 50 iteraciones y 8
   episodios por iteración.
2. Seleccionar el mejor checkpoint de cada réplica solo mediante validación.
3. Evaluar una vez cada checkpoint seleccionado en la prueba temporal
   independiente.
4. Informar media y desviación estándar de la rentabilidad de cartera, ROI de
   operaciones cerradas, porcentaje de operaciones rentables, operaciones
   rechazadas y días adicionales de mantenimiento.
5. Comparar el modelo confirmado con las referencias no MARL en una fase
   separada, sin modificar la configuración seleccionada.
