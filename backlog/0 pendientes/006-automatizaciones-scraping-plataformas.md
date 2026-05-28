# Implementar automatizaciones de scraping por plataforma

## Objetivo

Crear conectores de adquisición para plataformas de mercado de CS2, empezando por una fuente concreta.

## Contexto

Steam, Skinport, Buff u otras fuentes pueden requerir API, scraping o procesamiento de datos exportados. Estos procesos no serán agentes SPADE inicialmente.

## Alcance

- Elegir primera plataforma objetivo.
- Definir interfaz común de conector.
- Implementar obtención asíncrona con `httpx` cuando aplique.
- Normalizar salida a observaciones de mercado.
- Persistir observaciones y eventos.
- Añadir límites, timeouts y manejo de errores.

## Criterios de aceptación

- Hay un conector funcional para una plataforma o fuente inicial.
- La salida usa el mismo contrato que CSV/OCR.
- El scraping no duplica lógica de normalización.
- Hay tests con fixtures o respuestas simuladas.

## Decisiones técnicas

- Automatización programable, no agente inicial.
- Los conectores viven fuera de la lógica de decisión.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Revisar términos de uso y disponibilidad de cada fuente.
- Algunas plataformas pueden requerir datos manuales o OCR en vez de scraping directo.
