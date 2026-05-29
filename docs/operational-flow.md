# Flujo Operativo Objetivo

Este documento aclara el flujo de trabajo esperado para adquisición, predicción,
votación multiagente y simulación de cartera.

## Principio Base

El sistema no ejecuta compras reales. Todo termina en decisiones simuladas, posiciones
simuladas, métricas y trazabilidad.

Los scrapers, OCR runners y workers son automatizaciones de adquisición. Los agentes SPADE
coordinan análisis, votación y decisión.

## Flujo

```text
1. Scheduler / Acquisition Runner
   -> scraping o capturas para OCR
   -> cookies/sesión
   -> clicks con delays aleatorios
   -> workers paralelos controlados
   -> lista de candidatos

1.5 Candidate Prefilter
   -> normalización mínima de candidatos
   -> llamada al predictor/modelo entrenado
   -> selección de candidatos con oportunidad razonable

2. Persistencia
   -> upsert de assets/plataformas si hace falta
   -> inserción append-only de market_observations nuevas
   -> outbox: MarketObservationCaptured / PredictionRequested

3. Predicción
   -> lectura de histórico y candidatos
   -> features
   -> probability_up, expected_return, confidence
   -> persistencia de predictions
   -> evento PredictionCompleted

4. Votación Multiagente
   -> Broker/Jefe recibe PredictionCompleted
   -> convoca agentes de perfiles de riesgo
   -> participa Risk/Portfolio Manager con capital disponible, exposición y trade hold
   -> votos estructurados

5. Decisión Simulada
   -> consenso
   -> investment_decisions
   -> simulador abre/rechaza/mantiene observación
   -> métricas de cartera y evaluación
```

## Adquisición

La adquisición periódica debe contemplar:

- almacenamiento seguro de cookies y sesiones;
- refresco o recaptura manual cuando la sesión expire;
- simulación de clicks y navegación humana cuando la fuente lo requiera;
- delays aleatorios configurables;
- límites de concurrencia;
- dos a cuatro workers/bots paralelos cuando sea seguro;
- reintentos con backoff;
- registro de errores y dumps de respuestas anómalas;
- deduplicación de observaciones ya guardadas;
- trazabilidad con `correlation_id`.

La concurrencia debe ser configurable por plataforma. No todas las fuentes toleran el mismo
ritmo ni los mismos patrones de navegación.

## Prefiltro de Candidatos

Antes de scrapear en profundidad todos los artículos, la capa de adquisición puede generar una
lista de candidatos a partir de catálogo, listings, búsquedas o snapshots rápidos.

Esa lista debe pasar por un predictor ligero o por el modelo entrenado cuando exista suficiente
histórico. El objetivo es priorizar qué artículos merecen scraping profundo, predicción completa
o votación.

La salida del prefiltro no compra ni decide. Solo prioriza.

## Almacenamiento Recomendado

El histórico debe ser append-only: si una observación es nueva, se inserta una fila nueva.
No se debe sobrescribir el histórico salvo correcciones explícitas y auditadas.

Patrón recomendado:

- `assets`: identidad estable del artículo.
- `platforms`: mercado/fuente.
- `market_observations`: observaciones normalizadas de precio, volumen, liquidez, spread,
  moneda, variante, fuente y momento observado.
- `outbox_events`: evento asociado a cada inserción relevante.
- `predictions`: salida del predictor para un activo/plataforma/horizonte.
- `votes`: votos por perfil.
- `investment_decisions`: decisión simulada final.
- `simulated_positions`: posiciones simuladas y bloqueo por trade hold.

Para evitar duplicados, usar una clave natural o fingerprint basado en:

- `asset_id`;
- `platform_id`;
- `observed_at`;
- variante o metadatos relevantes (`wear`, `stattrak`, float si aplica);
- `source_type`;
- `source_reference` o identificador de extracción.

El `raw_payload` debe conservar la respuesta original relevante para auditoría, pero la lógica
del sistema debe trabajar con campos normalizados.

## Modelo y Agentes

El modelo entrenado genera una predicción, no una orden. Esa predicción debe incluir:

- probabilidad de subida;
- retorno esperado;
- confianza;
- horizonte temporal;
- snapshot de features;
- `correlation_id`.

El Broker/Jefe convoca votación con esa predicción. Los perfiles de riesgo votan según reglas
propias y el Risk/Portfolio Manager añade restricciones de cartera simulada:

- capital disponible;
- capital bloqueado;
- posiciones abiertas;
- fechas de liberación por trade hold;
- exposición máxima por activo/plataforma;
- liquidez mínima.

La decisión final siempre se registra como simulada.
