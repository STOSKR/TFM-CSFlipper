# Diseñar recompensa cooperativa MARL

## Objetivo

Diseñar la funcion de recompensa compartida cooperativa para el entorno MARL.

## Contexto

Scout, Trader y Portfolio deben optimizar un objetivo comun. La recompensa debe capturar beneficio realizado sin incentivar sobreexposicion, inactividad artificial o carteras excesivamente volatiles.

## Alcance

- Incluir profit realizado neto de comisiones.
- Penalizar sobreexposicion segun restricciones de Portfolio.
- Penalizar inactividad prolongada cuando existan oportunidades accionables.
- Penalizar volatilidad de cartera y drawdown.
- Definir normalizacion y escalado de terminos.
- Registrar desglose de recompensa en `info` para analisis.
- Anadir tests de casos controlados: beneficio, perdida, inactividad, sobreexposicion y volatilidad.

## Criterios de aceptacion

- La recompensa compartida se calcula igual para los tres agentes, salvo que se documente una excepcion.
- Cada componente de recompensa es trazable y configurable.
- Una politica que sobreexpone cartera recibe penalizacion aunque tenga beneficio bruto.
- La funcion no usa informacion futura no disponible en el timestep.

## Decisiones tecnicas

- Empezar con recompensa interpretable y auditable antes de hacer reward shaping avanzado.
- Reutilizar metricas del simulador y reglas de riesgo.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Una mala escala de recompensas puede hacer inestable MAPPO.

