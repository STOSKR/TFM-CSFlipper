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

## Ejecutar Comandos Desde La Web

Arranca el servidor local:

```powershell
python -m apps.cli.web_dashboard_server
```

Abre `http://localhost:8000/#scraper`. En la vista **Scraper** puedes usar:

- **Ejecutar scraping completo**: discovery, workers Steam/BUFF concurrentes, refresh de articulos con mas de 8 horas, persistencia y scoring.
- **Refrescar historico**: actualiza articulos guardados que lleven mas de 8 horas sin comprobarse.

El frontend no ejecuta texto libre: llama a `/api/commands/run` con un ID de una allowlist local.
Mientras un comando esta ejecutandose, los botones quedan deshabilitados. Al terminar un comando
correctamente, la web vuelve a pedir `/api/dashboard` para mostrar los datos vivos de la base de
datos.

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
