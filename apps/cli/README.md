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

## Refresco Semanal De Historial

Refresca todos los articulos ya guardados en `market_items` que tengan URL de Steam o BUFF:

```bash
python -m apps.cli.refresh_market_history --persist
```

El comando carga los objetos desde la base de datos, lanza los workers de Steam/BUFF y persiste
los snapshots resultantes. Antes de scrapear BUFF consulta `market_history_points`: si todos
los articulos ya tienen historial, pide solo los dias necesarios desde el articulo mas atrasado
con un dia de solape; si algun articulo no tiene historial previo, pide la ventana completa de
365 dias.

Postgres deduplica los puntos historicos por `(item_id, platform_id, observed_at, metric_name)`,
asi que el comando puede reintentar ventanas anteriores sin perder backfill.

Para refrescar solo articulos que no se hayan actualizado en la ultima hora:

```bash
python -m apps.cli.refresh_market_history --persist --stale-minutes 60
```

Para una ejecucion de prueba sin persistir:

```bash
python -m apps.cli.refresh_market_history --dry-run
```

Por defecto la salida es compacta. Para ver los logs internos del scraper:

```bash
python -m apps.cli.refresh_market_history --persist --verbose
```

Para forzar manualmente la ventana historica de BUFF:

```bash
python -m apps.cli.refresh_market_history --persist --buff-history-days 30
```

## Scraping Automatico Local

Ejecuta `scrape_flow.py --persist` y despues refresca los articulos guardados que no se hayan
actualizado en la ultima hora. Repite el ciclo cada 60 minutos:

```bash
python -m apps.cli.auto_scrape_loop
```

Para probar una sola vuelta:

```bash
python -m apps.cli.auto_scrape_loop --once
```

Para ajustar el intervalo y el umbral stale:

```bash
python -m apps.cli.auto_scrape_loop --interval-minutes 60 --stale-minutes 60
```

## Scraping En Render Con Cron Externo

El backend HTTP minimo para Render arranca con:

```bash
python -m apps.cli.scrape_job_server
```

Render debe usar el `Procfile` del repo o ese comando como start command. Variables minimas:

```text
DATABASE_URL=...
SCRAPE_JOB_TOKEN=un-token-largo
SCRAPE_STALE_MINUTES=480
SCRAPE_PERSIST=true
```

Build command recomendado en Render:

```bash
bash render-build.sh
```

El script comprueba al final que el binario de Chromium existe. Si falla, redeploy con
`Clear build cache & deploy` y revisa que Render este usando Python 3.11.

Endpoints:

```text
GET /health
GET /jobs/scrape/status?token=...
POST /jobs/scrape?token=...
```

`/jobs/scrape` lanza en background:

```bash
python -m apps.cli.auto_scrape_loop --once --stale-minutes 480 --persist
```

Para cron-job.org, usa la URL de Render:

```text
https://TU-SERVICIO.onrender.com/jobs/scrape?token=TU_TOKEN
```

Configura ejecucion cada 8 horas, por ejemplo `0 */8 * * *`. No hace falta ping de keep-alive:
Render puede arrancar en frio cuando llegue el cron.

## Export Web Dashboard

Genera el JSON local que consume `apps/web`:

```bash
python -m apps.cli.export_web_dashboard
```

El archivo se escribe por defecto en `apps/web/data/dashboard.json`, ignorado por git porque
contiene estado exportado desde la base de datos.

## Entrenamiento MARL RLlib

Ejecuta un smoke PPO multiagente con Ray/RLlib:

```bash
python -m apps.cli.train_marl_rllib --dataset-dir data/datasets/trading_profit_v1 --split train --limit 8 --iterations 1
```

El comando requiere instalar el extra `marl` o las dependencias equivalentes: Ray/RLlib,
PettingZoo, Gymnasium y PyTorch. El smoke guarda un checkpoint temporal y reporta metricas
operativas basicas; el critico centralizado MAPPO queda pendiente.

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
