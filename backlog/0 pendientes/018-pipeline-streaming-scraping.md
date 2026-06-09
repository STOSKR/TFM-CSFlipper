# Crear pipeline streaming de scraping

## Objetivo

Convertir el flujo actual en un pipeline incremental donde los articulos descubiertos en SteamDT puedan pasar a los workers de Steam y BUFF sin esperar a terminar toda la fase de descubrimiento.

## Contexto

El flujo actual ya evita abrir paginas detalle de SteamDT, trabaja con batches en `market_workers.py`, persiste cada lote y deduplica articulos repetidos por varias combinaciones de SteamDT. Aun asi, sigue habiendo dos comandos: primero se extrae una lista de candidatos y despues se scrapean plataformas. Para escalar mejor y reducir tiempos muertos, conviene conectar ambas fases con una cola interna.

## Alcance

- Extraer candidatos desde la tabla principal de SteamDT en modo incremental.
- Enviar cada candidato valido a una cola de trabajo.
- Ejecutar workers de Steam y BUFF consumiendo esa cola con concurrencia limitada.
- Persistir cada snapshot cuando se completen los datos disponibles de un articulo.
- Mantener backpressure para no saturar Steam, BUFF ni SteamDT.
- Permitir cancelar y conservar lo ya persistido.

## Criterios de aceptacion

- El pipeline empieza a scrapear Steam/BUFF antes de finalizar toda la lectura de SteamDT.
- La concurrencia y delays se configuran desde CLI.
- Cada articulo completado se persiste en `market_snapshots`.
- Los errores por plataforma no detienen el resto del pipeline.
- Hay logs por candidato, lote y plataforma.

## Decisiones tecnicas

- Usar `asyncio.Queue` como primera version local.
- Mantener batches pequenos y delays con jitter.
- No introducir agentes/RL en esta fase; eso vendra despues de estabilizar datos.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- SteamDT puede virtualizar la tabla y no exponer todas las filas de golpe.
- Hay que medir si el cuello de botella real esta en SteamDT, Steam, BUFF o persistencia.
