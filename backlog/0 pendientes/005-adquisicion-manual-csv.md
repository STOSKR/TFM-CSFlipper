# Implementar adquisición manual por CSV/JSON

## Objetivo

Crear la primera vía simple de ingesta para cargar observaciones de mercado sin depender todavía de scraping ni OCR.

## Contexto

Antes de automatizar fuentes externas, conviene poder alimentar el sistema con datos controlados para probar persistencia, predicción y agentes.

## Alcance

- Definir formato CSV/JSON esperado.
- Crear parser y normalizador.
- Validar observaciones con contratos.
- Persistir `market_observations`.
- Crear evento `MarketObservationCaptured`.
- Añadir comando CLI de importación.

## Criterios de aceptación

- Se puede importar un archivo de ejemplo.
- Los datos inválidos se rechazan con errores claros.
- Cada observación válida genera evento outbox.
- Hay tests unitarios del parser.

## Decisiones técnicas

- Esta ingesta es automatización de adquisición, no agente SPADE.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Necesita contratos y persistencia base.
