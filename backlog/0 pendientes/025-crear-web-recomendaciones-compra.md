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

- Usar como base `market_snapshot_view` para una primera version simple.
- Mantener predicciones, acciones MARL y recomendaciones en tablas o vistas separadas.
- Priorizar una interfaz densa y operativa: tabla, filtros, estados y acciones.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Definir formula fiable de rentabilidad neta antes de usarla como criterio principal.
- Decidir si la primera version sera local, desplegada o integrada directamente con Supabase.
