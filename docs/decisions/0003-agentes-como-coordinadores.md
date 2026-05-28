# ADR 0003: Agentes como Coordinadores

## Estado

Aceptada.

## Contexto

SPADE facilita comunicación multiagente, pero mezclar reglas de negocio dentro de comportamientos de agentes generaría acoplamiento y duplicación.

## Decisión

Los agentes SPADE solo coordinan. La lógica de OCR, predicción, simulación, voto y consenso vive en paquetes desacoplados.

## Consecuencias

- Tests más simples.
- Menos duplicación.
- Mayor facilidad para cambiar SPADE o ejecutar servicios sin agentes.

