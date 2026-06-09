# Crear web de recomendaciones de compra

## Objetivo

Crear una interfaz web para consultar articulos recomendables para compra, con enlaces directos a Steam y BUFF, precios actuales, historico relevante y rentabilidad estimada.

## Contexto

Tras simplificar la fase de scraping en `market_items` y `market_snapshots`, el siguiente paso operativo es visualizar rapidamente que articulos merecen revision o compra. La web debe priorizar claridad y toma de decision, no ser una landing page.

## Alcance

- Listar articulos candidatos a compra.
- Mostrar nombre, calidad, StatTrak, fecha de scraping y moneda.
- Mostrar precio Steam, precio BUFF, buy orders y ultimas ventas scrapeadas.
- Mostrar enlaces directos a Steam y BUFF en acciones visibles.
- Mostrar rentabilidad estimada cuando exista una formula validada.
- Permitir ordenar o filtrar por rentabilidad, precio, fecha de scraping, calidad y StatTrak.
- Distinguir estados basicos: recomendable, observar, descartado, datos insuficientes.
- Preparar la interfaz para incorporar despues prediccion de precio, confianza y margen mejorado.

## Criterios de aceptacion

- La web lee datos desde Supabase o desde una capa API conectada a Supabase.
- La tabla/listado permite identificar rapidamente mejores oportunidades.
- Cada articulo tiene links directos a Steam y BUFF.
- Se ve claramente cuando se scrapeo el dato.
- No se muestran campos tecnicos o de debug al usuario final.
- La rentabilidad se muestra solo si la formula usada esta definida y documentada.

## Decisiones tecnicas

- Usar como base `market_snapshot_view` para una primera version simple.
- Mantener la prediccion y la recomendacion en tablas o vistas separadas cuando se implemente la fase avanzada.
- Priorizar una interfaz densa y operativa: tabla, filtros, estados y acciones.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Definir formula fiable de rentabilidad neta antes de usarla como criterio principal.
- Decidir si la primera version sera local, desplegada o integrada directamente con Supabase.
