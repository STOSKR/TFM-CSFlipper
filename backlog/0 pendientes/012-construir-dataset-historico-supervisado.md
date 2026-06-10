# Construir dataset historico supervisado

## Objetivo

Implementar el pipeline de extraccion y procesamiento de datos historicos de precios, spreads, volumen y tendencias de Steam Market y Buff163 para entrenar el modelo supervisado.

## Contexto

El modelo supervisado predice la probabilidad calibrada de que el spread entre mercados siga siendo rentable en un horizonte de 7 dias. Esa probabilidad sera despues una feature dentro de la observacion de los agentes MARL.

## Alcance

- Extraer historico desde `market_items`, `market_snapshots` y fuentes historicas validadas.
- Alinear observaciones de Steam y Buff163 por item, timestamp, moneda y ventana temporal.
- Calcular features de precio, spread neto, volumen, liquidez, tendencia, volatilidad y comisiones.
- Construir la etiqueta supervisada: spread rentable a 7 dias segun formula versionada.
- Separar dataset de entrenamiento, validacion y test respetando orden temporal.
- Guardar dataset versionado con metadatos de generacion, rango temporal y filtros aplicados.
- Anadir tests de transformaciones criticas y casos de leakage temporal.

## Criterios de aceptacion

- Existe un comando reproducible para generar el dataset supervisado.
- Cada fila tiene features, target de 7 dias y claves de trazabilidad al item y snapshots fuente.
- No se usan datos posteriores al timestamp de decision para construir features.
- La etiqueta de rentabilidad neta usa comisiones y trade hold documentados.
- El dataset puede consumirse por experimentos sin depender de scraping en vivo.

## Decisiones tecnicas

- Separar generacion de dataset de entrenamiento de la inferencia productiva.
- Versionar formulas y parametros usados en la etiqueta.
- Priorizar datos tabulares antes de modelos secuenciales complejos.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- La calidad del dataset depende de disponer de historico real suficiente de ambas plataformas.
- El cambio de moneda o comisiones puede invalidar etiquetas si no queda versionado.

