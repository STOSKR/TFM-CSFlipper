# Integrar probabilidad supervisada en observacion

## Objetivo

Incorporar el output de probabilidad calibrada del modelo supervisado como feature adicional dentro del espacio de observacion de Scout, Trader y Portfolio.

## Contexto

El modelo supervisado no toma la decision final. Su probabilidad de que el spread sea rentable a 7 dias actua como senal informativa para las politicas MARL.

## Alcance

- Calcular o cargar `spread_profitable_probability_7d` para cada timestep/item.
- Incorporar la feature en la observacion de Scout, Trader y Portfolio.
- Incluir version del modelo y manejo de probabilidades ausentes.
- Evitar leakage: en entrenamiento solo usar predicciones disponibles en el timestamp simulado.
- Permitir ejecutar episodios con la feature activada o desactivada para ablation study.
- Anadir tests de observacion con y sin feature supervisada.

## Criterios de aceptacion

- Los tres agentes reciben la probabilidad calibrada en su observacion cuando esta activada.
- El entorno puede desactivar la feature mediante configuracion.
- Las observaciones mantienen shape estable aunque falte prediccion.
- La ablation con/sin feature puede configurarse sin cambiar codigo de agentes.

## Decisiones tecnicas

- La probabilidad supervisada es feature, no regla de compra.
- El modelo supervisado se ejecuta offline para entrenamiento y en modo inferencia para produccion.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Si se precalculan predicciones sobre todo el historico, hay que garantizar que cada fold/modelo respeta temporalidad.

