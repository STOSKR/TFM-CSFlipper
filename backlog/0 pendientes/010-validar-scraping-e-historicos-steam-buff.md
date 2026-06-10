# Validar scraping e historicos Steam-BUFF

## Objetivo

Completar y validar el flujo de scraping para guardar snapshots comparables de Steam Market y Buff163 con historico suficiente para entrenamiento y simulacion.

## Contexto

El flujo simple ya persiste `market_items` y `market_snapshots`, pero aun falta validar con datos reales los selectores, ultimas ventas, buy orders e historicos necesarios para entrenar el modelo supervisado y alimentar el entorno MARL.

## Alcance

- Mantener `market_items` y `market_snapshots` como esquema operativo inicial.
- Validar selectores reales de Steam y Buff163 para precio, buy orders, ultimas ventas y volumen.
- Guardar o derivar series historicas por item, plataforma y timestamp.
- Etiquetar cada snapshot con estrategia de descubrimiento, moneda, fuente y calidad de extraccion.
- Ajustar `market_workers.py` como comando principal de scraping profundo.
- Registrar errores por plataforma sin detener el flujo completo.
- Documentar que `steamdt.py`, `market_workers.py` y conectores de adquisicion son extractores, no agentes MARL.

## Criterios de aceptacion

- Ejecutar `python steamdt.py 50 --show` genera candidatos con nombre, calidad, StatTrak y URLs.
- Ejecutar `python market_workers.py --show-browser --persist` guarda datos en `market_items` y `market_snapshots`.
- La vista `market_snapshot_view` muestra datos listos para revision.
- Hay muestras reales con precio, spread, volumen y buy orders de Steam y Buff163.
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

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_simple_market_snapshots.py tests/unit/test_database_migration.py tests/unit/test_platform_workers.py`
- `python -m ruff check apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py packages/persistence/__init__.py tests/unit/test_simple_market_snapshots.py tests/unit/test_database_migration.py`
- `python -m mypy apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py packages/persistence/__init__.py`
- `python -m pytest tests/unit/test_runtime_config.py tests/unit/test_steamdt_hanging.py tests/unit/test_platform_workers.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m ruff check packages/runtime_config.py apps/cli/discover_steamdt_hanging.py steamdt.py apps/acquisition/steamdt_hanging.py apps/acquisition/platform_workers.py apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py tests/unit/test_runtime_config.py tests/unit/test_platform_workers.py tests/unit/test_steam_browser_market.py tests/unit/test_simple_market_snapshots.py`
- `python -m mypy packages/runtime_config.py apps/cli/discover_steamdt_hanging.py steamdt.py apps/acquisition/steamdt_hanging.py apps/acquisition/platform_workers.py apps/acquisition/steam_browser_market.py apps/cli/scrape_candidate_platforms.py packages/persistence/simple_market.py`

## Bloqueos o riesgos

- Falta validar con datos reales los selectores de buy orders de Steam y BUFF.
- Falta implementar scraping fiable de ultimas ventas/historico para Steam y BUFF.
- El `scraped_at` del snapshot es unico por ejecucion del worker.
- No debe considerarse una tarea MARL completada: solo estabiliza la capa de datos.

