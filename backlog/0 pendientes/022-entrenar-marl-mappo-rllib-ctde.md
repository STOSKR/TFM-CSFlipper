# Entrenar MARL con MAPPO en RLlib

## Objetivo

Entrenar el sistema MARL con MAPPO via RLlib bajo el paradigma CTDE: critico centralizado durante entrenamiento y ejecucion descentralizada por actor local en inferencia.

## Contexto

El entrenamiento debe usar el entorno PettingZoo, tres politicas cooperativas y estado global para el critico centralizado. La inferencia no debe depender del estado global completo.

## Alcance

- Registrar el entorno PettingZoo para RLlib.
- Configurar MAPPO o PPO multiagente con parametros compatibles con CTDE.
- Definir politicas para Scout, Trader y Portfolio.
- Incorporar estado global al critico centralizado durante entrenamiento.
- Guardar checkpoints, configuracion, seeds y metricas.
- Preparar script reproducible de entrenamiento.
- Anadir smoke test de entrenamiento corto.

## Criterios de aceptacion

- Un entrenamiento corto ejecuta sin errores con datos historicos de prueba.
- Los checkpoints permiten restaurar politicas.
- La inferencia usa actores locales y observaciones individuales.
- Las metricas incluyen recompensa, profit, exposicion, drawdown, operaciones y capital bloqueado.
- Queda documentada la configuracion CTDE usada.

## Decisiones tecnicas

- MAPPO es el algoritmo objetivo.
- RLlib gestiona entrenamiento multiagente; PettingZoo define entorno.
- Los modelos supervisados no se reentrenan durante entrenamiento MARL.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Conviene cerrar `027` antes de entrenar para no fijar una politica sesgada a una ruta de compra/venta incompleta.
- RLlib puede requerir wrappers especificos para PettingZoo y versiones compatibles.
- MAPPO con critico centralizado puede requerir personalizar modelo o view requirements.
