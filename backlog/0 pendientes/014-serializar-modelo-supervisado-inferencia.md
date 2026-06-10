# Serializar modelo supervisado para inferencia

## Objetivo

Serializar el modelo supervisado seleccionado y calibrado para que opere exclusivamente en modo inferencia dentro del pipeline productivo.

## Contexto

El entrenamiento y la experimentacion no deben ejecutarse dentro del flujo productivo. La inferencia debe cargar un artefacto versionado y producir probabilidades calibradas de rentabilidad del spread.

## Alcance

- Definir formato de artefacto del modelo, preprocesadores y metadatos.
- Guardar version de dataset, features esperadas, horizonte, fecha de entrenamiento y metricas principales.
- Implementar loader de inferencia en `packages/prediction/`.
- Validar esquema de entrada y orden de features antes de llamar al modelo.
- Bloquear rutas de reentrenamiento dentro del modulo de inferencia.
- Anadir tests de carga, compatibilidad de features y salida probabilistica.

## Criterios de aceptacion

- El artefacto puede cargarse sin acceder al dataset de entrenamiento.
- La inferencia devuelve probabilidad calibrada para `spread_profitable_8d`.
- El loader falla con error claro si faltan features o cambia el esquema.
- Hay tests con un artefacto pequeno o fixture controlado.
- La documentacion separa entrenamiento, calibracion e inferencia.

## Decisiones tecnicas

- La serializacion debe incluir preprocesado y calibrador, no solo el estimador base.
- La version del modelo debe quedar trazable en cada prediccion.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Cambios en nombres o unidades de features pueden romper inferencia si no se valida el contrato.
