# Diseñar entorno PettingZoo de mercado

## Objetivo

Diseñar e implementar el entorno de simulacion de mercado en PettingZoo con datos historicos reales de Steam Market y Buff163.

## Contexto

El sistema MARL cooperativo necesita un entorno reproducible que avance por ventanas historicas, aplique acciones simuladas y devuelva observaciones, recompensas y estados compatibles con RLlib.

## Alcance

- Implementar un entorno PettingZoo multiagente para Scout, Trader y Portfolio.
- Cargar episodios desde datasets historicos versionados.
- Avanzar la simulacion por timestamp o ventana temporal.
- Conectar el simulador de cartera, trade hold, comisiones y liquidez.
- Definir `reset`, `step`, terminaciones, truncaciones e info por agente.
- Preparar wrapper o adaptador compatible con RLlib.
- Anadir tests de episodio pequeno y reproducible.

## Criterios de aceptacion

- El entorno ejecuta un episodio completo con datos historicos de prueba.
- Las observaciones y acciones cumplen espacios declarados.
- El estado de cartera evoluciona de forma consistente con acciones y trade hold.
- El entorno puede registrarse o envolverse para entrenamiento en RLlib.
- No hay dependencia de scraping en vivo durante entrenamiento.

## Decisiones tecnicas

- PettingZoo define la interfaz de entorno; RLlib se integra despues.
- Los datos reales se cargan desde artefactos o consultas versionadas, no desde conectores live.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Hay que decidir granularidad temporal y como manejar huecos de datos entre plataformas.

