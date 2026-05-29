# Implementar Agente Broker y votación FIPA

## Objetivo

Crear el Agente Jefe/Broker para convocar votaciones, recoger votos y registrar decisiones simuladas.

## Contexto

El Broker toma la decisión final basándose en consenso, no en una predicción aislada.

## Alcance

- Crear agente Broker en `apps/agents/`.
- Enviar `VoteRequested` a agentes de perfil.
- Recoger `VoteSubmitted` hasta timeout.
- Incluir al Risk/Portfolio Manager como votante con estado de cartera simulada.
- Calcular consenso.
- Persistir `investment_decisions`.
- Emitir `InvestmentDecisionMade`.

## Criterios de aceptación

- El Broker no contiene reglas internas duplicadas de perfiles.
- El timeout de votación está controlado.
- La votación considera capital disponible, capital bloqueado, exposición y fechas de liberación por trade hold.
- La decisión final queda persistida.
- Hay tests del cálculo de consenso.

## Decisiones técnicas

- Protocolo FIPA tipo convocatoria.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Depende de contratos y reglas de perfiles.
