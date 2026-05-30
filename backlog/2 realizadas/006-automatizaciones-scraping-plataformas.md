# Implementar automatizaciones de scraping por plataforma

## Objetivo

Crear conectores de adquisicion para plataformas de mercado de CS2, empezando por una fuente concreta.

## Contexto

Steam, Skinport, Buff u otras fuentes pueden requerir API, scraping o procesamiento de datos exportados. Estos procesos no seran agentes SPADE inicialmente.

## Alcance

- Elegir primera plataforma objetivo.
- Definir interfaz comun de conector.
- Implementar obtencion asincrona con `httpx` cuando aplique.
- Gestionar cookies/sesiones cuando la plataforma lo requiera.
- Simular navegacion/clicks con delays aleatorios cuando haga falta Playwright.
- Permitir concurrencia controlada con 2-4 workers/bots configurables.
- Incorporar rate limits, backoff, dumps de anomalias y trazabilidad.
- Generar lista de candidatos para prefiltro del predictor antes del scraping profundo.
- Normalizar salida a observaciones de mercado.
- Persistir observaciones y eventos.
- Anadir limites, timeouts y manejo de errores.

## Criterios de aceptacion

- Hay un conector funcional para una plataforma o fuente inicial.
- La salida usa el mismo contrato que CSV/OCR.
- El scraping no duplica logica de normalizacion.
- La concurrencia, delays y cookies estan configurados fuera de la logica de dominio.
- La lista de candidatos puede enviarse al predictor para priorizacion.
- Hay tests con fixtures o respuestas simuladas.

## Decisiones tecnicas

- Primera fuente: Steam Market `priceoverview`.
- Usar `httpx.AsyncClient`, no `requests`, para no bloquear el event loop.
- No usar cookies ni Playwright en esta primera version: el endpoint `priceoverview` funciona como snapshot publico y reduce riesgo operativo.
- Delays, retries, backoff, timeout y concurrencia viven en `SteamMarketConnectorConfig`.
- La salida se normaliza a `MarketObservationContract` con `source_type=scraping`.
- La persistencia usa `MarketObservationIngestionRepository`, igual que CSV/JSON.

## Pasos realizados

- Movida la tarea al carril activo del backlog fisico (`backlog/1 progreso/`).
- Revisado material de `material_a_integrar/006-automatizaciones-scraping-plataformas/`, especialmente parsing de precio/volumen y retry/backoff de `cs-scraper`.
- Implementado `apps/acquisition/steam_market.py` con candidato, configuracion, conector async y normalizacion.
- Implementado CLI `python -m apps.cli.scrape_steam_market`.
- Aniadido modo `--dry-run` para consultar y mostrar la observacion sin persistir.
- Implementada persistencia real al ejecutar el CLI sin `--dry-run`.
- Aniadidos tests unitarios con `httpx.MockTransport` para payload correcto, retry en 429 y payload fallido.
- Ejecutado smoke test real contra Steam Market.
- Persistida una observacion real de `AK-47 | Slate (Field-Tested)` en Supabase y creado evento `MarketObservationCaptured`.

## Pruebas ejecutadas

- `python -m apps.cli.scrape_steam_market "AK-47 | Slate (Field-Tested)" --dry-run`: OK, devuelve observacion normalizada.
- `python -m apps.cli.scrape_steam_market "AK-47 | Slate (Field-Tested)"`: OK (`imported_observations=1`).
- Verificacion remota en Supabase: OK (`steam_observations=1`, `outbox_events=1`).
- `python -m pytest`: OK (`21 passed`).
- `python -m ruff check .`: OK.
- `python -m mypy packages apps tests`: OK.

## Bloqueos o riesgos

- El endpoint de Steam puede cambiar, limitar peticiones o devolver formatos localizados.
- Para scraping profundo historico con `pricehistory` probablemente se necesitaran cookies/sesion y politicas de rate limit mas conservadoras.
- Esta version no usa Playwright ni clicks simulados porque no son necesarios para `priceoverview`.
