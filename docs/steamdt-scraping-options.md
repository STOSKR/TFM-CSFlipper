# Opciones de Scraping SteamDT

Este archivo sirve como menu para elegir como ejecutar el discovery de articulos desde SteamDT Hanging.

Comando base:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run
```

## Comprobacion Rapida

Usa esto para comprobar que el sistema funciona sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run
```

Salida esperada: tabla en consola con `Item`, `Buy`, `Sell`, `Profit`, `ROI` y `Vol`.

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
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_fast --limit 10 --dry-run
```

## Cantidad de Items

`--limit` indica cuantos candidatos quieres imprimir.

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 20 --dry-run
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
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 15 --min-price 10 --max-price 300 --min-volume 20 --currency EUR --dry-run
```

## Plataformas

Por defecto se usa BUFF y se desactivan C5GAME y UU.

| Opcion | Descripcion |
| --- | --- |
| `--platform-buff` | Activa BUFF. |
| `--no-platform-buff` | Desactiva BUFF. |
| `--platform-c5game` | Activa C5GAME. |
| `--no-platform-c5game` | Desactiva C5GAME. |
| `--platform-uu` | Activa UU. |
| `--no-platform-uu` | Desactiva UU. |

Ejemplo con BUFF y C5GAME:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 10 --platform-buff --platform-c5game --no-platform-uu --dry-run
```

## Ver el Navegador

Si quieres comprobar visualmente que Playwright esta pulsando los botones correctos:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run --show-browser
```

## Formato de Salida

Tabla por defecto:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run --format table
```

JSON por linea:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run --format json
```

Guardar candidatos en archivo:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 20 --dry-run --output data/steamdt-candidates.json
```

## Encadenar con Steam Market

Primero descubre candidatos en SteamDT y luego consulta precio actual en Steam Market.

Sin guardar:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --dry-run
```

Guardando observaciones en Supabase:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --persist
```

Importante: no uses `--persist` hasta que hayas comprobado antes el resultado con `--dry-run`.

## Plantillas Para Elegir

Conservador:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit TU_NUMERO --min-price TU_MIN --max-price TU_MAX --min-volume TU_VOLUMEN --dry-run
```

Rapido:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_fast --limit TU_NUMERO --min-price TU_MIN --max-price TU_MAX --min-volume TU_VOLUMEN --dry-run
```

Con navegador visible:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit TU_NUMERO --dry-run --show-browser
```

Con persistencia:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit TU_NUMERO --fetch-steam-prices --persist
```

## Recomendacion Inicial

Empieza con:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --min-price 10 --max-price 300 --min-volume 10 --dry-run --show-browser
```

Si ves que SteamDT aplica bien los filtros, quita `--show-browser` y sube `--limit`.
