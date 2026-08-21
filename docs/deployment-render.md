# Despliegue en Render

El archivo `render.yaml` define dos servicios: un panel web de solo lectura y
una tarea diaria que actualiza Steam a las 05:30 UTC. Ambos usan la misma base
de datos Supabase mediante la variable secreta `DATABASE_URL`.

## Crear los servicios

1. Regulariza la cuota de la organización en Render.
2. En Render, crea un **Blueprint** desde la rama `main` de este repositorio.
3. Asigna `DATABASE_URL` a los dos servicios. No la copies al repositorio.
4. Comprueba `https://<servicio>/healthz` y abre el panel.
5. Ejecuta una vez manualmente el cron `csflipper-daily-steam-refresh` y revisa
   los logs antes de esperar a la siguiente ejecución programada.

## BUFF

El cron no activa BUFF. BUFF necesita una sesión de navegador y puede requerir
resolver un CAPTCHA; los cron jobs de Render no conservan disco entre
ejecuciones. Mientras no exista un mecanismo autorizado para renovar esa
sesión, la actualización de BUFF debe ejecutarse localmente desde el panel o
con `python -m apps.cli.refresh_market_history --buff --persist`.

## Seguridad

`WEB_COMMANDS_ENABLED=false` deja el panel desplegado en modo solo lectura.
Los endpoints que lanzan scraping quedan deshabilitados; la tarea diaria se
ejecuta directamente como cron y no queda expuesta por HTTP.
