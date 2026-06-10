# Implementar simulador de cartera con trade hold

## Objetivo

Crear el simulador de cartera que aplique trade hold de 7 dias, comisiones, liquidez y posiciones simuladas.

## Contexto

El entorno PettingZoo y la recompensa MARL necesitan una dinamica de cartera fiable antes de entrenar politicas. El TFM debe validar decisiones sin ejecutar compras reales y medir impacto del capital inmovilizado.

## Alcance

- Modelar cartera y posiciones.
- Aplicar bloqueo de 7 dias.
- Calcular comisiones por plataforma.
- Exponer estado consultable por el agente Portfolio: capital disponible, capital bloqueado, posiciones abiertas y fechas de liberacion.
- Registrar posiciones abiertas/cerradas.
- Calcular metricas iniciales de rentabilidad, drawdown, exposicion y capital bloqueado.
- Preparar una API interna usable desde el entorno PettingZoo.

## Criterios de aceptacion

- Una decision de compra simulada crea posicion bloqueada.
- La posicion no puede venderse antes de fin de trade hold.
- El simulador puede responder cuanto capital hay disponible y cuanto queda bloqueado.
- Las metricas incluyen rentabilidad neta y capital bloqueado.
- Hay tests unitarios del ciclo de vida de posicion.

## Decisiones tecnicas

- Simulacion antes que operacion real.
- El simulador no debe depender de RLlib, PettingZoo ni modelos ML.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Definir comisiones iniciales por plataforma.
- Confirmar la regla exacta de trade hold y si varia por plataforma o tipo de item.

