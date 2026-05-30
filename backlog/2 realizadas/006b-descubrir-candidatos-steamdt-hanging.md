# Descubrir candidatos desde SteamDT Hanging

## Objetivo

Automatizar la primera fase real del scraping: abrir SteamDT Hanging, configurar filtros de arbitraje, extraer una lista de articulos candidatos y, opcionalmente, consultar sus precios en Steam Market.

## Contexto

La tarea `006` implemento el conector de precio final contra Steam Market. El flujo correcto empieza antes: SteamDT Hanging sirve como pagina de discovery/prefiltro para encontrar articulos interesantes antes de scrapear precios concretos.

## Alcance

- Crear un conector SteamDT Hanging con Playwright.
- Configurar filtros de balance, modo de compra/venta, precio, volumen y plataformas.
- Extraer filas de la tabla de resultados.
- Normalizar candidatos con nombre, calidad, StatTrak, URLs BUFF/Steam, precio, volumen y ROI cuando aparezcan.
- Permitir modo dry-run.
- Permitir encadenar candidatos con el conector Steam Market existente.
- Anadir tests con filas simuladas.

## Criterios de aceptacion

- Existe CLI para descubrir candidatos desde SteamDT Hanging.
- Los filtros principales son configurables.
- El parser de filas descarta stickers, charms, patches y elementos sin `|`.
- La salida puede alimentar el conector Steam Market.
- Hay tests unitarios sin depender de la web real.

## Decisiones tecnicas

- Usar Playwright solo para la fase SteamDT porque requiere botones/filtros y tabla renderizada por JS.
- Mantener el parser de filas separado de Playwright para testear sin navegador.
- No guardar automaticamente candidatos como decisiones ni compras; solo observaciones si se activa el encadenado con Steam Market.

## Pasos realizados

- Implementado `apps.acquisition.steamdt_hanging` con discovery Playwright y parser puro.
- El flujo cierra modales de SteamDT, cambia moneda a EUR, selecciona perfil/modos, rellena filtros y ejecuta la busqueda.
- Normaliza nombres desde la URL inglesa de Steam cuando la fila visible esta localizada en chino.
- Extrae URLs de SteamDT, BUFF y Steam, precios, moneda, beneficio, ratios y volumen.
- Implementado CLI `python -m apps.cli.discover_steamdt_hanging` con perfiles:
  - `steam_sell_slow`
  - `steam_sell_fast`
  - `platform_arbitrage_safe`
  - `platform_arbitrage_fast`
- El CLI permite `--dry-run`, salida a archivo, encadenado con Steam Market y persistencia solo con `--persist`.
- Corregido el parser de Steam Market para precios europeos tipo `90,-- EUR`.
- Documentados comandos de prueba en `apps/cli/README.md`.

## Pruebas ejecutadas

- `python -m pytest`
- `python -m ruff check .`
- `python -m mypy packages apps tests`
- `python -m playwright install chromium`
- `python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 2 --dry-run`
- `python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 1 --fetch-steam-prices --dry-run`

## Bloqueos o riesgos

- SteamDT puede cambiar selectores o requerir interaccion manual/captcha.
- Si el navegador de Playwright no esta instalado, hay que ejecutar `python -m playwright install chromium`.
- SteamDT aplica parte de la logica de filtros en cliente; si cambia la UI, los selectores chinos/ingleses deberan actualizarse.
