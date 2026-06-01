# Opciones de Scraping SteamDT

Este archivo sirve como menu para elegir como ejecutar el discovery de articulos desde SteamDT Hanging.

Comando corto recomendado:

```bash
python steamdt.py
```

Por defecto usa:

- perfil `platform_arbitrage_safe`.
- `--limit 5`.
- BUFF activado.
- UU activado.
- C5GAME desactivado.
- salida en tabla.
- `--dry-run`, sin guardar nada.

En PowerShell tambien puedes usar:

```powershell
.\steamdt.ps1 -Limit 5
```

Comando largo equivalente:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run
```

## Comprobacion Rapida

Usa esto para comprobar que el sistema funciona sin guardar nada:

```bash
python steamdt.py
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

Por defecto se usa BUFF y UU. C5GAME queda desactivado.

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
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 20 --dry-run --output data/steamdt-candidates.json
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
