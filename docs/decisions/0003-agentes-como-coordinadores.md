# ADR 0003: Agentes como Coordinadores

## Estado

Aceptada como antecedente. Revisada por el giro a MARL.

## Contexto

SPADE facilita comunicación multiagente, pero mezclar reglas de negocio dentro de comportamientos de agentes generaría acoplamiento y duplicación. El alcance actual del TFM se orienta a PettingZoo/RLlib con MAPPO, manteniendo la misma idea de separacion: los agentes no deben contener logica duplicada.

## Decisión

Los agentes extractores solo adquieren datos. Los agentes MARL solo consumen observaciones y emiten acciones. La lógica de OCR, predicción supervisada, simulación, riesgo y evaluación vive en paquetes desacoplados.

## Consecuencias

- Tests más simples.
- Menos duplicación.
- Mayor facilidad para cambiar frameworks de agentes, usar PettingZoo/RLlib o ejecutar servicios sin agentes.
