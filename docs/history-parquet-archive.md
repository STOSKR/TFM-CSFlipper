# Archivo histórico Parquet

El histórico de precios se conserva en dos ubicaciones cuando se ejecuta el
refresco local:

1. `data/history/market_history_v1`, como archivo principal Parquet comprimido.
2. `OneDrive/CSFlipper-history/market_history_v1`, como segunda copia con la
   misma suma SHA-256 por fichero. Se selecciona automáticamente si OneDrive
   está configurado. También puede definirse `HISTORY_ARCHIVE_BACKUP_DIR`.

Los ficheros se particionan por año y mes y usan un identificador derivado de
su contenido. Por ello una misma captura no se duplica al repetir el comando.
Los directorios `data/` siguen fuera de Git: no sustituyen a la segunda copia.

## Copia inicial del histórico remoto

Antes de eliminar puntos de Supabase, se debe crear y comprobar la copia
completa existente:

```powershell
python -m apps.cli.export_market_history_archive
```

El comando solo lee Supabase y escribe los dos archivos Parquet. Al finalizar
debe informar del mismo número de partes locales y de respaldo. No borra ni
modifica datos remotos.

## Capturas futuras

`refresh_market_history` guarda Parquet automáticamente antes de persistir los
datos actuales. Para cambiar el destino:

```powershell
python -m apps.cli.refresh_market_history --persist `
  --archive-dir data/history/market_history_v1 `
  --archive-backup-dir "C:\ruta\sincronizada\CSFlipper-history"
```

## Uso para datasets

El constructor de datasets acepta tanto un archivo Parquet único como el
directorio particionado del archivo histórico:

```powershell
python -m apps.cli.build_trading_dataset `
  --input-parquet data/history/market_history_v1 `
  --output data/datasets/trading_profit_v1
```

Mientras la copia inicial y su respaldo no se hayan verificado, Supabase sigue
siendo una segunda fuente de datos y no se debe aplicar ninguna retención.
