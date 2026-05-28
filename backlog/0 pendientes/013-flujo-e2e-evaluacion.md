# Crear flujo e2e y evaluación inicial

## Objetivo

Conectar el flujo completo desde ingesta hasta decisión simulada y métricas de evaluación.

## Contexto

Cuando los bloques principales existan, el proyecto necesita una prueba demostrable de extremo a extremo para el TFM.

## Alcance

- Preparar dataset pequeño de prueba.
- Ejecutar adquisición.
- Generar predicción.
- Convocar votación.
- Registrar decisión.
- Pasar por simulador.
- Generar métricas y reporte básico.

## Criterios de aceptación

- Existe una prueba e2e reproducible.
- El flujo genera trazabilidad con `correlation_id`.
- El reporte muestra decisiones, votos y métricas.
- Queda documentado cómo ejecutarlo.

## Decisiones técnicas

- Primero flujo reproducible pequeño; después escalado.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Depende de casi todas las tareas anteriores.
