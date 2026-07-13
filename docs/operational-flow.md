# Flujo Operativo Objetivo

Este documento aclara el flujo de trabajo esperado para adquisición, predicción,
decisión MARL y simulación de cartera.

## Principio Base

El sistema no ejecuta compras reales. Todo termina en decisiones simuladas, posiciones
simuladas, métricas y trazabilidad.

Los scrapers, OCR runners, workers, importadores CSV/API y SteamDT son agentes extractores de adquisición. Su salida alimenta datasets, inferencia supervisada y observaciones del entorno, pero no forma parte del núcleo MARL entrenado con MAPPO.

## Flujo

```text
1. Agentes extractores / Acquisition Runner
   -> scraping o capturas para OCR
   -> cookies/sesión
   -> clicks con delays aleatorios
   -> workers paralelos controlados
   -> lista de candidatos

1.5 Dataset / Feature Builder
   -> normalización mínima de candidatos
   -> historico Steam-BUFF alineado
   -> features de spread, volumen, tendencia y liquidez
   -> etiqueta de spread rentable a 8 dias

2. Persistencia e historico
   -> upsert de assets/plataformas si hace falta
   -> inserción append-only de snapshots/observaciones nuevas
   -> trazabilidad de fuente, timestamp, moneda y calidad de dato

3. Modelo supervisado calibrado
   -> lectura de histórico y candidatos
   -> features
   -> probabilidad calibrada de spread rentable a 8 dias
   -> persistencia de predicciones versionadas

3.b Modelo Steam de salida para flips
   -> entrenamiento con historico Steam
   -> probabilidad de salida segura a 8 dias
   -> retorno Steam esperado
   -> BUFF solo como precio vivo de entrada, no como target de entrenamiento

4. Entorno MARL
   -> PettingZoo carga episodio historico
   -> observaciones locales con probabilidad supervisada
   -> Scout detecta oportunidades
   -> Trader decide accion y tamaño
   -> Portfolio controla riesgo y exposicion

5. Decisión Simulada
   -> acciones descentralizadas de politicas entrenadas
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

Antes de scrapear en profundidad todos los artículos, la capa de adquisición puede generar una lista de candidatos a partir de catálogo, listings, búsquedas o snapshots rápidos.

Esa lista debe pasar por un predictor ligero o por el modelo entrenado cuando exista suficiente
histórico. El objetivo es priorizar qué artículos merecen scraping profundo, predicción completa
o simulación.

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
- `predictions`: salida del modelo supervisado calibrado.
- `agent_actions`: acciones emitidas por Scout, Trader y Portfolio cuando exista la tabla.
- `investment_decisions`: decisión simulada final o accion consolidada.
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

El modelo supervisado genera una probabilidad calibrada, no una orden. Esa predicción debe incluir:

- probabilidad de spread rentable a 8 dias;
- version del modelo;
- horizonte temporal;
- snapshot de features;
- `correlation_id`.

En la linea corregida BUFF -> Steam, el aprendizaje temporal se apoya en Steam. BUFF no se
predice ni se usa como fuente masiva de entrenamiento: se consulta de forma puntual para obtener
precio de entrada. La recomendacion combina margen vivo BUFF -> Steam, comisiones, trade hold,
probabilidad de salida segura y retorno esperado. Si falta BUFF, el candidato se observa como
`missing_entry_price`.

Las politicas MARL usan esa probabilidad como feature de observacion. El agente Portfolio añade o aprende sobre restricciones de cartera simulada:

- capital disponible;
- capital bloqueado;
- posiciones abiertas;
- fechas de liberación por trade hold;
- exposición máxima por activo/plataforma;
- liquidez mínima.

La decisión final siempre se registra como simulada.
