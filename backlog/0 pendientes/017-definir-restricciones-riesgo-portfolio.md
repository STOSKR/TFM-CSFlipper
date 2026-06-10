# Definir restricciones de riesgo para Portfolio

## Objetivo

Definir las reglas y limites de riesgo que usara el agente Portfolio para gestionar exposicion global, capital bloqueado y liquidez.

## Contexto

La tarea antigua de perfiles de riesgo y votacion se transforma en restricciones de entorno y senales para el agente Portfolio. Ya no se implementan votantes Conservador, Moderado o Arriesgado como agentes separados.

## Alcance

- Definir limites configurables de exposicion por item, plataforma, rareza o grupo.
- Definir limites de capital bloqueado por trade hold.
- Definir umbrales de liquidez minima y volatilidad maxima.
- Exponer estas restricciones al simulador y al espacio de observacion del agente Portfolio.
- Generar metricas de violacion o cercania al limite.
- Anadir tests unitarios de reglas de riesgo.

## Criterios de aceptacion

- Las restricciones son configurables fuera del codigo de agentes.
- Portfolio puede observar capital disponible, capital bloqueado, exposicion y riesgo agregado.
- Las penalizaciones de recompensa pueden reutilizar estas metricas.
- No queda logica de perfiles duplicada dentro de agentes.

## Decisiones tecnicas

- Reglas deterministas iniciales para controlar el entorno.
- La politica MARL aprende acciones sobre estas senales, no reemplaza la validacion basica de riesgo.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Ajustar thresholds con datos reales.

