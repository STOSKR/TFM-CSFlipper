# CLI App

Comandos manuales para desarrollo, diagnostico y tareas operativas.

## SteamDT Hanging

Descubre candidatos desde SteamDT Hanging sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --dry-run
```

Descubre candidatos y consulta sus precios actuales en Steam Market sin guardar nada:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --dry-run
```

Persistir observaciones en Supabase requiere hacerlo de forma explicita:

```bash
python -m apps.cli.discover_steamdt_hanging --profile platform_arbitrage_safe --limit 5 --fetch-steam-prices --persist
```
