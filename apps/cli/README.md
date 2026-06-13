# CLI App

Comandos manuales para desarrollo, diagnostico y tareas operativas.

## Flujo Completo SteamDT -> Workers

Guia completa de opciones: [../../docs/steamdt-scraping-options.md](../../docs/steamdt-scraping-options.md).

Ejecuta discovery en SteamDT y despues Steam/BUFF workers con el JSON recien generado:

```bash
python scrape_flow.py
```

Para ver navegadores y persistir snapshots:

```bash
python scrape_flow.py --show-browser --persist
```

Por defecto no persiste y no muestra navegadores.

## Flujo Streaming Local

Primera version del pipeline con cola interna. Consume un JSON de candidatos ya generado,
deduplica, procesa por batches y conserva `scrape_flow.py` como comando estable:

```bash
python -m apps.cli.stream_scrape_flow --persist
```

Para validar solo el cableado sin llamar a plataformas:

```bash
python -m apps.cli.stream_scrape_flow --no-steam --no-buff
```

## SteamDT Hanging

Descubre candidatos desde SteamDT Hanging sin guardar nada:

```bash
python steamdt.py
```

Equivalente largo:

```bash
python -m apps.cli.discover_steamdt_hanging --profile steam_sell_slow --limit 5 --dry-run
```

La salida por defecto es una tabla con item, precios, beneficio, ROI y volumen. Para salida JSON:

```bash
python -m apps.cli.discover_steamdt_hanging --profile steam_sell_slow --limit 5 --dry-run --format json
```

Descubre candidatos y consulta sus precios actuales en Steam Market sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile steam_sell_slow --limit 5 --fetch-steam-prices --dry-run
```

Persistir observaciones en Supabase requiere hacerlo de forma explicita:

```bash
python -m apps.cli.discover_steamdt_hanging --profile steam_sell_slow --limit 5 --fetch-steam-prices --persist
```

## Workers Por Plataforma

Despues del discovery, usa el JSON de candidatos para lanzar un worker de Steam Market y otro
de BUFF en paralelo:

```bash
python market_workers.py
```

Por defecto usa el ultimo `data/flow-runs/steamdt_candidates_*.json`.

Por defecto Steam y BUFF se scrapean con navegador Playwright. El resultado combinado se
guarda en `data/flow-runs/platform_observations_YYYYMMDD_HHMMSS.json` y los logs detallados
en `logs/market_workers_YYYYMMDD_HHMMSS.log`.

Para ver las interfaces mientras scrapea:

```bash
python market_workers.py --show-browser
```

Para hacer login manual en ambas plataformas:

```bash
python market_workers.py --show-browser --steam-login --buff-login
```

Para iniciar sesion en BUFF una vez:

```bash
python market_workers.py --show-browser --buff-login
```

Las cookies/localStorage de BUFF se guardan en
`data/browser-state/buff163_storage_state.json` y se reutilizan en ejecuciones posteriores.

Puedes desactivar una plataforma durante pruebas:

```bash
python market_workers.py --no-buff
python market_workers.py --no-steam
```

## OCR

Validar un texto OCR ya extraido sin guardar nada:

```bash
python -m apps.cli.import_ocr_observations tests/fixtures/ocr_observations.txt --dry-run
```

Procesar una captura con Tesseract requiere tener el binario de Tesseract instalado:

```bash
python -m apps.cli.import_ocr_observations path/to/capture.png --dry-run
```
