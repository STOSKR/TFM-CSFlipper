# Definir dominio y contratos Pydantic

## Objetivo

Crear los modelos base del dominio y los contratos Pydantic V2 compartidos entre servicios y agentes.

## Contexto

El sistema necesita evitar payloads duplicados o improvisados entre adquisición, predicción, votación y decisión.

## Alcance

- Crear entidades/value objects iniciales en `packages/domain/`.
- Crear contratos en `packages/contracts/`.
- Definir enums compartidos para fuente de datos, voto, decisión y estado de evento.
- Añadir tests unitarios de validación.

## Criterios de aceptación

- Existen modelos Pydantic para eventos y mensajes principales.
- Los contratos incluyen `schema_version` y `correlation_id` cuando aplique.
- No hay contratos duplicados en `apps/`.
- Los tests unitarios pasan.

## Decisiones técnicas

- Pydantic V2.
- Dominio sin dependencia de SPADE ni Supabase.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Ajustar nombres finales con el modelo de datos.
