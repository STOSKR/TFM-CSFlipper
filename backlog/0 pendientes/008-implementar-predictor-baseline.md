# Implementar predictor baseline

## Objetivo

Crear un primer predictor simple para generar señales antes de implementar LSTM o modelos avanzados.

## Contexto

Un baseline permite probar el flujo completo adquisición -> predicción -> votación -> decisión sin esperar al entrenamiento ML avanzado.

## Alcance

- Calcular features iniciales sobre histórico.
- Implementar modelo simple basado en momentum/media móvil/reglas estadísticas.
- Añadir prefiltro de candidatos para priorizar qué artículos merecen scraping profundo o evaluación completa.
- Generar `probability_up`, `expected_return` y `confidence`.
- Persistir predicciones.
- Añadir tests unitarios.

## Criterios de aceptación

- El predictor funciona con histórico mínimo.
- La salida usa contratos compartidos.
- El predictor puede evaluar una lista de candidatos normalizados antes de la votación.
- Los resultados son deterministas en tests.
- Queda documentada la limitación del baseline.

## Decisiones técnicas

- Baseline antes de LSTM.
- La inferencia vive en `packages/prediction/`.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Requiere datos históricos suficientes.
