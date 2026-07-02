# CSFlipper Web

MVP local estatico de la consola operativa.

Arrancar con datos reales desde Supabase/Postgres:

```powershell
python -m apps.cli.web_dashboard_server
```

Despues abre:

```text
http://localhost:8000
```

La web llama a `/api/dashboard`, que consulta la base de datos y construye el payload en vivo.

Exportar una copia JSON local sigue estando disponible para snapshots congelados:

```powershell
python -m apps.cli.export_web_dashboard
```

Para abrir esa copia:

```text
http://localhost:8000/?data=dashboard.json
```

Si `/api/dashboard` falla, la web usa datos de fallback honestos para mostrar la estructura sin
fingir recomendaciones reales.
