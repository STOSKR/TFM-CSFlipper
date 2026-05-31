# CLI App

Comandos manuales para desarrollo, diagnostico y tareas operativas.

## SteamDT Hanging

Descubre candidatos desde SteamDT Hanging sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run
```

La salida por defecto es una tabla con item, precios, beneficio, ROI y volumen. Para salida JSON:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run --format json
```

Descubre candidatos y consulta sus precios actuales en Steam Market sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --dry-run
```

Persistir observaciones en Supabase requiere hacerlo de forma explicita:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --persist
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
