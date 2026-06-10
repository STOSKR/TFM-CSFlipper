# Validar MARL con baselines y ablations

## Objetivo

Validar experimentalmente el sistema MARL multiagente frente a un baseline de agente unico y realizar ablation study con y sin la feature del modelo supervisado.

## Contexto

El TFM necesita evidencia experimental, no solo un flujo ejecutable. La validacion debe comparar el aporte de la arquitectura multiagente y de la probabilidad supervisada calibrada.

## Alcance

- Preparar splits temporales de evaluacion no vistos.
- Implementar baseline single-agent RL comparable.
- Ejecutar MARL con feature supervisada.
- Ejecutar MARL sin feature supervisada.
- Comparar profit neto, drawdown, volatilidad, exposicion, numero de operaciones, ratio de aciertos y capital bloqueado.
- Generar reporte reproducible con tablas, graficas y configuracion.
- Conectar el flujo completo desde dataset hasta metricas finales.

## Criterios de aceptacion

- Existe una prueba e2e reproducible de evaluacion experimental.
- El reporte compara multiagente vs single-agent y con/sin feature supervisada.
- La evaluacion usa datos no vistos y respeta temporalidad.
- Las decisiones, acciones y metricas quedan trazadas por episodio.
- Queda documentado si el MARL mejora o no mejora frente a los baselines.

## Decisiones tecnicas

- Primero evaluacion reproducible pequena; despues escalado.
- El baseline single-agent debe compartir datos y costes para que la comparacion sea justa.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Si los datos no tienen suficiente variedad temporal, las conclusiones pueden ser debiles.

