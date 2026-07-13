# Crear pipeline streaming de scraping

## Objetivo

Convertir el flujo actual en un pipeline incremental donde los articulos descubiertos en SteamDT puedan pasar a los workers de Steam y BUFF sin esperar a terminar toda la fase de descubrimiento.

## Contexto

El flujo actual ya evita abrir paginas detalle de SteamDT, trabaja con batches en `market_workers.py`, persiste cada lote y deduplica articulos repetidos por varias combinaciones de SteamDT. Aun asi, sigue habiendo dos comandos: primero se extrae una lista de candidatos y despues se scrapean plataformas. Para escalar mejor y reducir tiempos muertos, conviene conectar ambas fases con una cola interna.

## Alcance

- Extraer candidatos desde la tabla principal de SteamDT en modo incremental.
- Enviar cada candidato valido a una cola de trabajo.
- Ejecutar workers de Steam y BUFF consumiendo esa cola con concurrencia limitada.
- Persistir cada snapshot cuando se completen los datos disponibles de un articulo.
- Mantener backpressure para no saturar Steam, BUFF ni SteamDT.
- Permitir cancelar y conservar lo ya persistido.
- Generar trazabilidad por candidato para reconstruir datasets historicos despues.

## Criterios de aceptacion

- El pipeline empieza a scrapear Steam/BUFF antes de finalizar toda la lectura de SteamDT.
- La concurrencia y delays se configuran desde CLI.
- Cada articulo completado se persiste en `market_snapshots`.
- Los errores por plataforma no detienen el resto del pipeline.
- Hay logs por candidato, lote y plataforma.
- El pipeline puede ejecutarse como extractor de datos, sin contener logica de decision ni politica MARL.

## Decisiones tecnicas

- Usar `asyncio.Queue` como primera version local.
- Mantener batches pequenos y delays con jitter.
- No introducir agentes/RL en esta fase; eso vendra despues de estabilizar datos.

## Pasos realizados

- Movida a progreso tras cerrar la validacion inicial de scraping Steam-BUFF (`010`).
- Punto de partida confirmado: `python scrape_flow.py --persist` queda como comando operativo estable mientras se implementa el pipeline streaming.
- Implementado nucleo `apps.acquisition.streaming_pipeline` con `asyncio.Queue`, backpressure configurable, deduplicacion de candidatos, procesamiento por batches y persistencia incremental por batch.
- Anadido CLI `python -m apps.cli.stream_scrape_flow` para ejecutar el pipeline streaming sobre el JSON de candidatos actual sin romper `scrape_flow.py`.
- El CLI streaming reutiliza `scrape_candidate_platforms`, `build_simple_market_snapshots` y la persistencia simple existente.
- Anadido smoke mode operativo con `--no-steam --no-buff` para validar cola, batching y salida sin llamar a plataformas.
- Cubiertos los casos de productor simulado, errores parciales, deduplicacion y cancelacion conservando snapshots ya persistidos.
- Adaptado el scraper Steam Browser a la nueva UI del Market: activa StatTrak/Souvenir cuando aplica, selecciona la calidad buscada y extrae los ultimos puntos del grafico Recharts de `Median Sale Prices`.
- `steam_recent_sales` se rellena desde el grafico con `source = steam_recharts`, `price`, `time_label`, `range` y `point_index`.
- `build_simple_market_snapshots` ya propaga `recent_sales` de Steam/BUFF desde `raw_payload` al snapshot persistible.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_streaming_pipeline.py tests/unit/test_buff_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check apps/acquisition/streaming_pipeline.py apps/cli/stream_scrape_flow.py apps/cli/scrape_candidate_platforms.py apps/acquisition/buff_market.py tests/unit/test_streaming_pipeline.py tests/unit/test_buff_market.py`
- `python -m mypy apps/acquisition/streaming_pipeline.py apps/cli/stream_scrape_flow.py apps/cli/scrape_candidate_platforms.py apps/acquisition/buff_market.py tests/unit/test_streaming_pipeline.py tests/unit/test_buff_market.py`
- `python -m apps.cli.stream_scrape_flow --no-steam --no-buff --batch-size 10 --queue-size 2 --output %TEMP%/csflipper_stream_smoke.json --log-file %TEMP%/csflipper_stream_smoke.log`
- `python -m pytest tests/unit`
- `python -m ruff check .`
- `python -m mypy .` no completa por modulos duplicados preexistentes en `material_a_integrar/`.
- `python -m mypy apps packages tests` no completa por deuda previa en tests antiguos (`test_runtime_config.py`, `test_platform_workers.py`); los modulos y tests tocados si pasan mypy focalizado.
- `python -m pytest tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m mypy apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- Smoke real sin persistencia: `python -m apps.cli.stream_scrape_flow --candidates %TEMP%/csflipper_steam_one_candidate.json --no-buff --batch-size 1 --queue-size 1 --steam-min-delay 0 --steam-max-delay 0 --output %TEMP%/csflipper_steam_history_smoke.json --log-file %TEMP%/csflipper_steam_history_smoke.log`

## Bloqueos o riesgos

- SteamDT puede virtualizar la tabla y no exponer todas las filas de golpe.
- Hay que medir si el cuello de botella real esta en SteamDT, Steam, BUFF o persistencia.
- El CLI streaming actual consume candidatos desde JSON; falta conectar un productor SteamDT realmente incremental para cumplir la aceptacion completa de empezar workers antes de terminar discovery.
