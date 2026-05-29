# Implementar simulador con trade hold

## Objetivo

Crear el simulador de cartera que aplique trade hold de 7 días, comisiones, liquidez y posiciones simuladas.

## Contexto

El TFM necesita validar decisiones sin ejecutar compras reales y medir impacto del capital inmovilizado.

## Alcance

- Modelar cartera y posiciones.
- Aplicar bloqueo de 7 días.
- Calcular comisiones por plataforma.
- Exponer estado consultable por el Risk/Portfolio Manager: capital disponible, capital bloqueado, posiciones abiertas y fechas de liberación.
- Registrar posiciones abiertas/cerradas.
- Calcular métricas iniciales.

## Criterios de aceptación

- Una decisión de compra simulada crea posición bloqueada.
- La posición no puede venderse antes de fin de trade hold.
- El simulador puede responder cuánto capital hay disponible y cuánto queda bloqueado.
- Las métricas incluyen rentabilidad neta y capital bloqueado.
- Hay tests unitarios del ciclo de vida de posición.

## Decisiones técnicas

- Simulación antes que operación real.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Definir comisiones iniciales por plataforma.
