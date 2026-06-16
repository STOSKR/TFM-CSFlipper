# CSFlipper Web

MVP local estatico de la consola operativa.

Exportar datos reales desde Supabase:

```powershell
python -m apps.cli.export_web_dashboard
```

Arrancar:

```text
python -m http.server 8000 -d apps/web
```

Despues abre:

```text
http://localhost:8000/?data=dashboard.json
```

Si abres `http://localhost:8000` sin parametro `data`, la web usa datos de fallback honestos
para mostrar la estructura sin fingir recomendaciones reales.
