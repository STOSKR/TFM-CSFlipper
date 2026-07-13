# Opciones de Scraping SteamDT

Este archivo sirve como menu para elegir como ejecutar el discovery de articulos desde SteamDT Hanging.

Comando corto recomendado para flujo completo:

```bash
python scrape_flow.py
```

Este comando ejecuta SteamDT, guarda el JSON de candidatos y lanza automaticamente
`market_workers.py` con ese archivo.

Para ver navegadores y persistir snapshots:

```bash
python scrape_flow.py --show-browser --persist
```

Comando corto solo para discovery SteamDT:

```bash
python steamdt.py
```

Por defecto usa:

- perfil `steam_sell_slow`.
- el limite configurado en `csflipper_config.toml`.
- BUFF activado.
- UU desactivado.
- C5GAME desactivado.
- salida en tabla.
- `--dry-run`, sin persistir en base de datos.
- guarda candidatos en `data/flow-runs/steamdt_candidates_YYYYMMDD_HHMMSS.json`.
- carga y guarda cookies/localStorage en `data/browser-state/steamdt_storage_state.json`.

En PowerShell tambien puedes usar:

```powershell
.\steamdt.ps1 -Limit 5
```

Comando largo equivalente:

```bash
python -m apps.cli.discover_steamdt_hanging --profile steam_sell_slow --limit 5 --dry-run
```

## Comprobacion Rapida

Usa esto para comprobar que el sistema completo funciona sin guardar nada:

```bash
python scrape_flow.py
```

Usa esto si solo quieres comprobar SteamDT:

```bash
python steamdt.py
```

Salida esperada: tabla en consola con `Item`, `Buy`, `Sell`, `Profit`, `ROI` y `Vol`, mas
la ruta `steamdt_candidates_file=...` del JSON guardado.

## Perfiles

`--profile` define que botones/modos se seleccionan en SteamDT.

| Perfil | Que hace | Uso recomendado |
| --- | --- | --- |
| `platform_arbitrage_safe` | Compra via Steam Buy Order y vende a precio minimo de plataforma. | Primera opcion para buscar arbitraje mas conservador. |
| `platform_arbitrage_fast` | Compra al menor precio de Steam y vende a la mayor orden de compra de plataforma. | Mas rapido, pero puede ser menos conservador. |
| `steam_sell_slow` | Usa balance Steam y venta a precio minimo Steam. | Analisis centrado en Steam. |
| `steam_sell_fast` | Usa balance Steam y venta a highest buy order. | Analisis Steam mas rapido. |

Ejemplo:

```bash
python steamdt.py 10 --fast
```

## Cantidad de Items

`--limit` indica cuantos candidatos quieres imprimir.

```bash
python steamdt.py 20
```

## Filtros de Precio y Volumen

| Opcion | Ejemplo | Descripcion |
| --- | --- | --- |
| `--min-price 50` | precio minimo 50 | Rellena el primer filtro de rango de precio. |
| `--max-price 500` | precio maximo 500 | Rellena el segundo filtro de rango de precio. |
| `--min-volume 12` | volumen minimo 12 | Rellena el filtro de ventas/volumen 24h. |
| `--currency EUR` | moneda EUR | Cambia la moneda en SteamDT. |

Ejemplo:

```bash
python steamdt.py 15 --min 10 --max 300 --vol 20
```

## Plataformas

Por defecto se usa BUFF. UU y C5GAME quedan desactivados.

| Opcion | Descripcion |
| --- | --- |
| `--uu` | Activa UU desde el wrapper corto `steamdt.py`. |
| `--platform-buff` | Activa BUFF. |
| `--no-platform-buff` | Desactiva BUFF. |
| `--platform-c5game` | Activa C5GAME. |
| `--no-platform-c5game` | Desactiva C5GAME. |
| `--platform-uu` | Activa UU. |
| `--no-platform-uu` | Desactiva UU. |

Ejemplo con BUFF y C5GAME:

```bash
python steamdt.py 10 --c5
```

## Ver el Navegador

Si quieres comprobar visualmente que Playwright esta pulsando los botones correctos:

```bash
python steamdt.py 5 --show
```

## Formato de Salida

Tabla por defecto:

```bash
python steamdt.py 5
```

JSON por linea:

```bash
python steamdt.py 5 --json
```

Guardar candidatos en archivo:

```bash
python steamdt.py 20 --output data/steamdt-candidates.json
```

No guardar candidatos:

```bash
python steamdt.py 20 --no-output
```

## Cookies y Login

El scraper guarda estado de navegador compatible con Playwright en:

```text
data/browser-state/steamdt_storage_state.json
```

Para iniciar sesion una vez, abre el navegador visible y deja tiempo para hacer login manual:

```bash
python steamdt.py 20 --show --login
```

Por defecto espera 120 segundos. Puedes cambiarlo:

```bash
python steamdt.py 20 --show --login --login-wait 240
```

Las siguientes ejecuciones reutilizan esas cookies:

```bash
python steamdt.py 20
```

Si quieres usar otro archivo de sesion:

```bash
python steamdt.py 20 --session-state data/browser-state/mi_sesion.json
```

Si quieres ejecutar sin cargar ni guardar cookies:

```bash
python steamdt.py 20 --no-session-state
```

## Scraping Profundo Por Plataforma

SteamDT se usa como discovery. Despues, el JSON guardado alimenta dos workers en paralelo:

- worker `steam`: abre Steam Market con Playwright por defecto.
- worker `buff`: abre el enlace `buff_url` de cada candidato con Playwright.

Ejemplo completo:

```bash
python scrape_flow.py 20 --show-browser
```

`market_workers.py` usa automaticamente el ultimo
`data/flow-runs/steamdt_candidates_*.json`. Si quieres forzar un archivo concreto:

```bash
python market_workers.py --candidates data/flow-runs/steamdt_candidates_YYYYMMDD_HHMMSS.json
```

El segundo comando guarda observaciones normalizadas y errores por plataforma en:

```text
data/flow-runs/platform_observations_YYYYMMDD_HHMMSS.json
```

Tambien guarda logs detallados en:

```text
logs/market_workers_YYYYMMDD_HHMMSS.log
```

Para ver las interfaces de Steam y BUFF durante el scraping:

```bash
python scrape_flow.py --show-browser
```

Si alguna pagina necesita login manual:

```bash
python scrape_flow.py --show-browser --steam-login --buff-login
```

Para hacer login en BUFF una vez:

```bash
python market_workers.py --show-browser --buff-login
```

La sesion BUFF queda en:

```text
data/browser-state/buff_storage_state.json
```

Si quieres comparar contra el conector HTTP antiguo de Steam:

```bash
python market_workers.py --steam-api
```

## Encadenar con Steam Market

Primero descubre candidatos en SteamDT y luego consulta precio actual en Steam Market.

Sin guardar:

```bash
python steamdt.py 5 --steam
```

Guardando observaciones en Supabase:

```bash
python steamdt.py 5 --steam --persist
```

Importante: no uses `--persist` hasta que hayas comprobado antes el resultado con `--dry-run`.

## Plantillas Para Elegir

Conservador:

```bash
python steamdt.py TU_NUMERO --min TU_MIN --max TU_MAX --vol TU_VOLUMEN
```

Rapido:

```bash
python steamdt.py TU_NUMERO --fast --min TU_MIN --max TU_MAX --vol TU_VOLUMEN
```

Con navegador visible:

```bash
python steamdt.py TU_NUMERO --show
```

Con persistencia:

```bash
python steamdt.py TU_NUMERO --steam --persist
```

## Recomendacion Inicial

Empieza con:

```bash
python steamdt.py 5 --min 10 --max 300 --vol 10 --show
```

Si ves que SteamDT aplica bien los filtros, quita `--show-browser` y sube `--limit`.
