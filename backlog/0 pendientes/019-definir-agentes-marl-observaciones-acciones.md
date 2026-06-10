# Definir agentes MARL, observaciones y acciones

## Objetivo

Implementar los tres agentes MARL especializados y cooperativos con sus espacios de observacion y accion individuales.

## Contexto

La arquitectura objetivo usa Scout, Trader y Portfolio bajo CTDE. Estos agentes no son procesos SPADE ni votantes FIPA: son politicas dentro del entorno MARL, entrenadas de forma cooperativa.

## Alcance

- Definir agente Scout para detectar y marcar oportunidades.
- Definir agente Trader para decidir compra, venta, mantener y tamaño de posicion.
- Definir agente Portfolio para gestionar riesgo, exposicion y capital bloqueado.
- Especificar espacios de observacion individuales.
- Especificar espacios de accion individuales y validaciones por agente.
- Documentar que informacion local recibe cada agente durante inferencia descentralizada.
- Anadir tests de shape, tipos, limites y mascaras de accion cuando aplique.

## Criterios de aceptacion

- Cada agente tiene observacion y accion declaradas en el entorno.
- Las acciones invalidas se rechazan o enmascaran de forma controlada.
- Scout no ejecuta operaciones; solo senala oportunidades.
- Trader no ignora restricciones de Portfolio y simulador.
- Portfolio puede limitar exposicion sin decidir oportunidades por si solo.

## Decisiones tecnicas

- Tres agentes cooperativos: Scout, Trader y Portfolio.
- Ejecucion descentralizada: cada actor usa observacion local en inferencia.
- Entrenamiento centralizado: el critico podra usar estado global durante MAPPO.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Acciones demasiado amplias pueden dificultar el aprendizaje.
- Acciones demasiado discretas pueden ocultar oportunidades reales.

