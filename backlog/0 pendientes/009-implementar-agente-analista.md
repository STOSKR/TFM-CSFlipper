# Implementar Agente Analista

## Objetivo

Crear el agente SPADE que consume eventos de mercado, invoca predicción y emite reportes estructurados.

## Contexto

El Analista conecta la persistencia histórica con el flujo multiagente de decisión.

## Alcance

- Crear agente base en `apps/agents/`.
- Leer eventos `MarketObservationCaptured` o `PredictionRequested`.
- Invocar servicios de `packages/prediction/`.
- Guardar predicciones.
- Enviar `PredictionCompleted` al Broker.

## Criterios de aceptación

- El agente coordina sin contener lógica ML.
- Valida contratos Pydantic.
- Maneja errores sin romper el proceso.
- Hay tests unitarios de comportamiento donde sea razonable.

## Decisiones técnicas

- SPADE solo coordina.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Depende de contratos, persistencia y predictor baseline.
