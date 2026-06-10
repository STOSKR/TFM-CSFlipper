# Implementar servicio de inferencia supervisada

## Objetivo

Crear el servicio que consume snapshots o features recientes, invoca el modelo supervisado calibrado y devuelve probabilidades listas para ser usadas por los agentes MARL.

## Contexto

La tarea antigua de Agente Analista SPADE se adapta a la arquitectura MARL. Ya no debe implementarse como agente que envia reportes al Broker, sino como servicio puro de inferencia que los pipelines y entornos pueden llamar.

## Alcance

- Crear una interfaz de inferencia en `packages/prediction/`.
- Transformar snapshots recientes en el mismo contrato de features usado en entrenamiento.
- Invocar el artefacto serializado en modo inferencia.
- Devolver probabilidad calibrada, version del modelo, timestamp y features snapshot.
- Persistir predicciones cuando el flujo lo requiera.
- Emitir eventos o registros de trazabilidad sin acoplarse a SPADE.
- Mantener `MomentumBaselinePredictor` como fallback experimental o fixture, no como predictor principal.

## Criterios de aceptacion

- El servicio no entrena ni recalibra modelos.
- La salida es determinista para un artefacto y una entrada dados.
- La probabilidad puede incorporarse directamente al espacio de observacion MARL.
- Hay tests unitarios del contrato de entrada/salida.
- Queda documentado que no existe todavia un agente MARL por el simple hecho de tener este servicio.

## Decisiones tecnicas

- La inferencia vive en `packages/prediction/`.
- Los agentes Scout, Trader y Portfolio consumiran la probabilidad como feature, no como decision final.
- SPADE/Broker/FIPA quedan fuera del camino principal de esta arquitectura.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Depende del artefacto supervisado calibrado y de la estabilidad del contrato de features.

