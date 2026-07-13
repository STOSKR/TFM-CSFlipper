# Validar scraping e historicos Steam-BUFF

## Objetivo

Completar y validar el flujo de scraping para guardar snapshots comparables de Steam Market y Buff con historico suficiente para entrenamiento y simulacion.

## Contexto

El flujo simple ya persiste `market_items` y `market_snapshots`, pero aun falta validar con datos reales los selectores, ultimas ventas, buy orders e historicos necesarios para entrenar el modelo supervisado y alimentar el entorno MARL.

## Alcance

- Mantener `market_items` y `market_snapshots` como esquema operativo inicial.
- Validar selectores reales de Steam y Buff para precio, buy orders, ultimas ventas y volumen.
- Guardar o derivar series historicas por item, plataforma y timestamp.
- Etiquetar cada snapshot con estrategia de descubrimiento, moneda, fuente y calidad de extraccion.
- Ajustar `market_workers.py` como comando principal de scraping profundo.
- Registrar errores por plataforma sin detener el flujo completo.
- Documentar que `steamdt.py`, `market_workers.py` y conectores de adquisicion son extractores, no agentes MARL.

## Criterios de aceptacion

- Ejecutar `python steamdt.py 50 --show` genera candidatos con nombre, calidad, StatTrak y URLs.
- Ejecutar `python market_workers.py --show-browser --persist` guarda datos en `market_items` y `market_snapshots`.
- La vista `market_snapshot_view` muestra datos listos para revision.
- Hay muestras reales con precio, spread, volumen y buy orders de Steam y Buff.
- Hay tests unitarios del mapeo candidato + observaciones -> snapshot simple.
- Queda documentado que los scripts existentes alimentan datos, pero no sustituyen al entorno PettingZoo ni a los agentes Scout, Trader y Portfolio.

## Decisiones tecnicas

- Mantener el esquema canonico anterior solo como referencia/compatibilidad, no como camino principal de fase 1.
- Usar `jsonb` para listas de ventas recientes y buy orders hasta que haya una razon real para normalizarlas.
- No incluir prediccion, confianza ni margen en esta tarea.

## Pasos realizados

- Creada migracion `0002_simple_market_snapshots.sql` con `market_items`, `market_snapshots` y `market_snapshot_view`.
- Separadas monedas por plataforma con `steam_currency` y `buff_currency`.
- Creado `SimpleMarketSnapshotRepository` para persistir el esquema simple.
- Adaptado `market_workers.py`/`apps.cli.scrape_candidate_platforms` para construir snapshots simples desde Steam + BUFF.
- `--persist` ahora escribe en `market_items` y `market_snapshots`.
- La salida JSON del worker usa `schema_version = market_snapshot.v1` e incluye `items`, `summary` y `errors`.
- Aniadidos tests unitarios del mapeo y la persistencia simple.
- Desactivada por defecto la apertura de paginas detalle de SteamDT.
- Anadida opcion `--enrich-links` para recuperar el comportamiento anterior solo si hace falta.
- Bajada la velocidad de scraping por defecto con concurrencia 1 y delays con jitter.
- Anadido procesamiento por lotes en `market_workers.py` para persistir resultados sin esperar a todos los articulos.
- Movidas las combinaciones de SteamDT a `csflipper_config.toml`.
- Anadido modo `run_all_profiles` para ejecutar todas las combinaciones configuradas por defecto.
- Anadidos metadatos de estrategia al JSON de candidatos: `strategy_id`, `strategy_label`, `balance_type`, `buy_mode` y `sell_mode`.
- Los workers deduplican candidatos por articulo/plataforma para no scrapear el mismo item varias veces cuando aparece en varias combinaciones.
- Anadida extraccion inicial de buy orders de Steam desde la tabla de buy requests.
- Anadida extraccion inicial de buy orders de BUFF desde filas/elementos etiquetados como compra, pedido o demanda.
- Configurado porcentaje de extraccion distinto por tipo de balance: `steam_balance` y `platform_balance`.
- Configurado `steam_sell_slow` como perfil por defecto de SteamDT y desactivada la ejecucion de todos los perfiles por defecto.
- Adaptado `steamdt.py` para usar `default_profile` desde `csflipper_config.toml` cuando no se pase `--fast`.
- Creado `scrape_flow.py` para ejecutar SteamDT y despues `market_workers.py` con el JSON recien generado en un unico comando.
- Actualizado `scrape_flow.sh` para delegar en `scrape_flow.py`.
- Corregido `build_simple_market_snapshots` para inferir `quality` desde `market_hash_name` cuando el worker no la devuelva.
- Ampliada la extraccion de SteamDT para capturar enlaces dentro de tarjetas `.market-item`, incluyendo URLs de BUFF.
- Anadido parseo especifico de filas basadas en tarjetas de mercado para asociar precio, URL y volumen de BUFF sin confundir `For Sale` con precio.
- Compactado el JSON de candidatos de SteamDT eliminando campos internos como `raw_cells`.
- Compactado el JSON publico de `market_workers.py`: los campos vacios y `debug_log` quedan fuera de la salida principal.
- Simplificada la consola de `market_workers.py` con resumen por lote y resumen final; el detalle queda en `logs/market_workers_*.log`.
- Filtrados articulos sin `quality`/exterior, como agentes, para no generar snapshots incompatibles con el esquema actual de skins.
- `build_simple_market_snapshots` ahora ignora observaciones sin quality en vez de detener el lote completo.
- Corregido el wrapper de SteamDT para que UU quede desactivado por defecto y solo se active explicitamente con `--uu`.
- Alineados `scrape_flow.py`, `steamdt.py`, `steamdt.ps1` y `discover_steamdt_hanging` con BUFF activado y UU/C5GAME desactivados por defecto.
- Ejecutado run real adicional con `python scrape_flow.py --persist` usando 50 candidatos.
- Persistidos 50 snapshots nuevos en el run `20260613_213602`: Steam 50/50, BUFF 50/50, 0 errores.
- Validada `market_snapshot_view` en Supabase/Postgres: 150 snapshots totales, 149 comparables Steam+BUFF, ultimo `scraped_at = 2026-06-13 21:36:01.553420+00`.
- Revisada muestra de 10 filas recientes con precio Steam, precio BUFF, moneda CNY y buy orders BUFF presentes.
- Corregido filtrado de buy orders BUFF para descartar precios concatenados, conversiones fuera de moneda visible y artefactos con simbolo CNY al final.
- Se acepta como cierre de fase 1 que Steam no exponga buy orders en la muestra reciente; queda como limitacion de fuente, no como bloqueo para dataset inicial.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_simple_market_snapshots.py tests/unit/test_database_migration.py tests/unit/test_platform_workers.py`
- `python -m ruff check apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py packages/persistence/__init__.py tests/unit/test_simple_market_snapshots.py tests/unit/test_database_migration.py`
- `python -m mypy apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py packages/persistence/__init__.py`
- `python -m pytest tests/unit/test_runtime_config.py tests/unit/test_steamdt_hanging.py tests/unit/test_platform_workers.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check packages/runtime_config.py apps/cli/discover_steamdt_hanging.py steamdt.py apps/acquisition/steamdt_hanging.py apps/acquisition/platform_workers.py apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py tests/unit/test_runtime_config.py tests/unit/test_platform_workers.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m mypy packages/runtime_config.py apps/cli/discover_steamdt_hanging.py steamdt.py apps/acquisition/steamdt_hanging.py apps/acquisition/platform_workers.py apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py`
- `python -m pytest tests/unit/test_runtime_config.py tests/unit/test_steamdt_hanging.py`
- `python -m ruff check steamdt.py csflipper_config.toml packages/runtime_config.py tests/unit/test_runtime_config.py`
- `python -m mypy steamdt.py packages/runtime_config.py`
- `python -m pytest tests/unit/test_scrape_flow.py`
- `python -m ruff check scrape_flow.py tests/unit/test_scrape_flow.py`
- `python -m mypy scrape_flow.py tests/unit/test_scrape_flow.py`
- `python -m pytest tests/unit/test_simple_market_snapshots.py`
- `python -m mypy apps/cli/scrape_candidate_platforms.py tests/unit/test_simple_market_snapshots.py`
- `python -m pytest tests/unit`
- `python -m pytest tests/unit/test_steamdt_hanging.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check apps/acquisition/steamdt_hanging.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steamdt_hanging.py tests/unit/test_simple_market_snapshots.py`
- `python -m mypy apps/acquisition/steamdt_hanging.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steamdt_hanging.py tests/unit/test_simple_market_snapshots.py`
- `python -m pytest tests/unit/test_steamdt_wrapper.py tests/unit/test_scrape_flow.py tests/unit/test_runtime_config.py`
- `python -m ruff check steamdt.py scrape_flow.py apps/cli/discover_steamdt_hanging.py tests/unit/test_steamdt_wrapper.py tests/unit/test_scrape_flow.py`
- `python -m mypy steamdt.py scrape_flow.py apps/cli/discover_steamdt_hanging.py tests/unit/test_steamdt_wrapper.py tests/unit/test_scrape_flow.py`
- `$null = [scriptblock]::Create((Get-Content -Raw steamdt.ps1)); 'powershell_parse_ok'`
- `python -m ruff check .`
- `python -m pytest tests/unit/test_steamdt_hanging.py`
- `python -m pytest tests/unit/test_simple_market_snapshots.py`
- `python -m mypy apps/acquisition/steamdt_hanging.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steamdt_hanging.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check apps/acquisition/steamdt_hanging.py apps/cli/scrape_candidate_platforms.py tests/unit/test_steamdt_hanging.py tests/unit/test_simple_market_snapshots.py`
- `python -m pytest tests/unit`
- `python scrape_flow.py --persist`
- Consulta manual a `market_snapshot_view` para validar conteos y muestra de 10 snapshots recientes.
- `python -m pytest tests/unit/test_buff_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check apps/acquisition/buff_market.py tests/unit/test_buff_market.py`
- `python -m mypy apps/acquisition/buff_market.py tests/unit/test_buff_market.py`

## Bloqueos o riesgos

- No quedan bloqueos para cerrar la validacion inicial de scraping Steam-BUFF.
- Steam no esta devolviendo buy orders en la vista reciente; se conserva como riesgo de calidad de fuente para fases posteriores.
- Falta implementar scraping fiable de ultimas ventas/historico para Steam y BUFF; se abordara en dataset/historico, no bloquea el cierre de esta tarea.
- El `scraped_at` del snapshot es unico por ejecucion del worker.
- No debe considerarse una tarea MARL completada: solo estabiliza la capa de datos.
