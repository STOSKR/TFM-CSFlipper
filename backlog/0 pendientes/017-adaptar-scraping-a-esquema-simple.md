# Adaptar scraping al esquema simple

## Objetivo

Modificar el flujo de scraping para guardar directamente en `market_items` y `market_snapshots`, eliminando la dependencia operativa del esquema canonico anterior para esta primera fase.

## Contexto

El proyecto empieza sin datos existentes, asi que conviene evitar complejidad innecesaria. La nueva estructura simple prioriza articulo, calidad, StatTrak, URLs, momento de scraping, precios, ultimas ventas y buy orders por plataforma.

## Alcance

- Crear repositorio de persistencia para `market_items` y `market_snapshots`.
- Hacer upsert de `market_items` con `name`, `quality`, `stattrak`, `steam_url` y `buff_url`.
- Unificar las observaciones de Steam y BUFF de un mismo articulo en una fila de `market_snapshots`.
- Guardar `scraped_at`, `currency`, `steam_price`, `buff_price`, `steam_recent_sales`, `steam_buy_orders`, `buff_recent_sales` y `buff_buy_orders`.
- Simplificar la salida JSON del flujo para que coincida con la estructura de BD.
- Ajustar `market_workers.py` para que sea el comando principal de scraping profundo.
- Ejecutar SteamDT con varias combinaciones configurables de balance, compra y venta.
- Etiquetar cada candidato con la combinacion usada para poder interpretar el precio y el flujo posterior.

## Criterios de aceptacion

- Ejecutar `python steamdt.py 50 --show` genera candidatos con nombre, calidad, StatTrak y URLs.
- Ejecutar `python market_workers.py --show-browser --persist` guarda datos en `market_items` y `market_snapshots`.
- No se insertan datos en tablas antiguas durante el flujo simple.
- La vista `market_snapshot_view` muestra los datos listos para revision.
- Hay tests unitarios del mapeo candidato + observaciones -> snapshot simple.

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
- El streaming real SteamDT -> workers mientras la tabla aun se esta leyendo queda para una tarea especifica.
