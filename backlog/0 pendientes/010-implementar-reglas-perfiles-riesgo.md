# Implementar reglas de perfiles de riesgo

## Objetivo

Crear la lógica compartida para votos de perfiles Conservador, Moderado, Arriesgado, Liquidez, Tendencia, Arbitrajista y Risk Manager.

## Contexto

Los agentes votantes no deben duplicar reglas. Deben invocar servicios de `packages/decision/`.

## Alcance

- Definir interfaz de evaluador de perfil.
- Implementar reglas iniciales por perfil.
- Generar votos estructurados.
- Añadir configuración de thresholds.
- Añadir tests unitarios por perfil.

## Criterios de aceptación

- Cada perfil produce `buy`, `reject`, `observe` o `abstain`.
- Las razones del voto son trazables.
- No hay lógica duplicada en agentes.
- Los tests cubren casos positivos y negativos.

## Decisiones técnicas

- Reglas deterministas iniciales.
- Evolución futura hacia aprendizaje por refuerzo cuando el simulador madure.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Ajustar thresholds con datos reales.
