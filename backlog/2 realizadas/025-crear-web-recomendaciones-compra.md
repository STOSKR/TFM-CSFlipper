# Crear web de recomendaciones de compra

## Objetivo

Crear una interfaz web para consultar articulos recomendables para compra, con enlaces directos a Steam y BUFF, precios actuales, historico relevante, probabilidad supervisada, accion MARL y rentabilidad estimada.

## Contexto

Tras estabilizar datos, prediccion y politicas MARL, el siguiente paso operativo es visualizar rapidamente que articulos merecen revision o compra. La web debe priorizar claridad y toma de decision, no ser una landing page.

## Alcance

- Listar articulos candidatos a compra.
- Mostrar nombre, calidad, StatTrak, fecha de scraping y moneda.
- Mostrar precio Steam, precio BUFF, buy orders y ultimas ventas scrapeadas.
- Mostrar enlaces directos a Steam y BUFF en acciones visibles.
- Mostrar probabilidad calibrada del modelo supervisado.
- Mostrar accion/recomendacion resultante de Scout, Trader y Portfolio.
- Mostrar rentabilidad estimada cuando exista una formula validada.
- Mostrar historial de articulos comprados y vendidos.
- Mostrar calendario de desbloqueo/liberacion de articulos.
- Mostrar dinero disponible, dinero bloqueado, saldo por plataforma y valor efectivo estimado.
- Mostrar historial de dinero ingresado por persona/plataforma cuando exista el dato.
- Incluir calculadora de rentabilidad Steam-BUFF con escenarios de cash-out Steam 10%, 15% y 20%.
- Permitir ordenar o filtrar por rentabilidad, probabilidad, precio, fecha de scraping, calidad y StatTrak.
- Distinguir estados basicos: recomendable, observar, descartado, datos insuficientes.

## Criterios de aceptacion

- La web lee datos desde Supabase o desde una capa API conectada a Supabase.
- La tabla/listado permite identificar rapidamente mejores oportunidades.
- Cada articulo tiene links directos a Steam y BUFF.
- Se ve claramente cuando se scrapeo el dato y que versiones de modelo lo evaluaron.
- No se muestran campos tecnicos o de debug al usuario final.
- La rentabilidad se muestra solo si la formula usada esta definida y documentada.

## Decisiones tecnicas

- Usar como base `market_items` para estado actual y `market_history_points` para historico.
- Mantener predicciones, acciones MARL y recomendaciones en tablas o vistas separadas.
- Priorizar una interfaz densa y operativa: tabla, filtros, estados y acciones.

## Pasos realizados

- Iniciada la tarea como MVP local estatico en `apps/web`.
- Creada la consola operativa con secciones de Overview, Recomendaciones, Agentes,
  Portfolio y Backlog.
- Anadidos filtros basicos por estado y busqueda en la tabla de candidatos.
- Mostrada la limitacion principal sin maquillar: el modelo actual es experimental
  y el historico alineado de `buff163/sell_price` todavia no alcanza para entrenar
  bien la direccion operativa natural.
- Anadido estado inicial de agentes Scout, Trader y Portfolio conectado al avance
  real del entorno MARL minimo.
- Anadida vista de limites de riesgo Portfolio desde la configuracion actual.
- Documentado el MVP en `apps/web/README.md`.
- Creado `packages.web.dashboard_payload` para construir el JSON consumido por
  la web a partir de filas de `market_items`.
- Creado `python -m apps.cli.export_web_dashboard`, que exporta
  `apps/web/data/dashboard.json` desde Supabase.
- La web carga `data/dashboard.json` al abrir con `?data=dashboard.json` y mantiene
  fallback local honesto sin tocar red si no se pasa ese parametro.
- Anadidos resumen por estado, ordenacion por estado/profit/scraping/precio Steam
  y columnas de profit actual y fecha de scraping en la tabla.
- Ejecutado el export real contra Supabase con `--limit 50`; se genero
  `apps/web/data/dashboard.json` con 50 recomendaciones. El archivo queda ignorado por git.
- Validada la web local con Playwright cargando `?data=dashboard.json`: 50 filas renderizadas,
  resumen Total 50 / Revisar 19 / Observar 31 / Bloqueado 0 y cero errores de consola.
- Anadida columna de ruta operativa en recomendaciones para distinguir la direccion usada
  por el calculo actual, empezando por `BUFF listing -> Steam listing`.
- Revisada la BD real: `buff163/sell_price` ya se captura y existe en `market_items`
  y `market_history_points`, pero el historico alineado disponible es escaso para
  construir ejemplos `buff_to_steam_sell` a 8 dias.
- Dado por cerrado el MVP local de la web: lectura desde export Supabase, tabla filtrable,
  links Steam/BUFF, estados honestos, ruta operativa y riesgo Portfolio visibles.

## Pruebas ejecutadas

- `python -m pytest tests/unit/test_web_mvp.py`
- `python -m pytest tests/unit/test_web_dashboard_payload.py`
- `python -m apps.cli.export_web_dashboard --limit 50`
- `python -m json.tool apps/web/data/dashboard.json`
- `python -m pytest tests/unit/test_web_mvp.py tests/unit/test_web_dashboard_payload.py`
- Validacion Playwright local contra `http://127.0.0.1:8765/?data=dashboard.json`
- `python -m pytest tests/unit/test_web_mvp.py tests/unit/test_web_dashboard_payload.py`
- `python -m apps.cli.export_web_dashboard --limit 50`
- Validacion Playwright local contra `http://127.0.0.1:8765/?data=dashboard.json`: 50 filas,
  50 rutas renderizadas y cero errores de consola.
- Consulta de cobertura Supabase para `market_history_points`: `buff163/sell_price`
  existe con 121 filas / 119 articulos, pero `buff_to_steam_sell` genera 0 ejemplos
  con horizonte 8 dias y tolerancia 7 dias.
- `python -m apps.cli.build_trading_dataset --output model-runs/probe_buff_to_steam_sell --query-start 2025-01-01 --trade-direction buff_to_steam_sell --future-tolerance-days 7`
- `python -m apps.cli.build_trading_dataset --output model-runs/probe_steam_to_buff_buy_order --query-start 2025-01-01 --trade-direction steam_to_buff_buy_order --future-tolerance-days 7`

## Bloqueos o riesgos

- No quedan bloqueos para cerrar el MVP web local.
- Riesgo residual: las filas de recomendaciones no deben interpretarse como senales reales de compra.
- La siguiente mejora de datos queda fuera de esta tarea: acumular historico alineado de
  `buff163/sell_price` para entrenar la ruta natural `BUFF listing -> Steam listing`.
