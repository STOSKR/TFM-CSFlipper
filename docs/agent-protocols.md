# Protocolos de Agentes

## Objetivo

Definir cómo se comunican los agentes sin duplicar contratos ni mezclar lógica de negocio con SPADE.

## Agentes Iniciales

### Agente Analista

Responsabilidades:

- escuchar eventos `PredictionRequested` o `MarketObservationCaptured`;
- recuperar histórico desde persistencia;
- invocar servicios de predicción;
- guardar la predicción;
- enviar `PredictionCompleted` al Agente Jefe.

### Agente Jefe o Broker

Responsabilidades:

- recibir predicciones;
- convocar votación;
- recoger votos;
- calcular consenso;
- registrar decisión simulada.

### Agentes de Perfil de Riesgo

Ejemplos:

- Conservador;
- Moderado;
- Arriesgado;
- Liquidez;
- Tendencia;
- Arbitraje.

Responsabilidades:

- recibir una solicitud de voto;
- evaluar usando reglas de `packages/decision/`;
- devolver un voto estructurado.

## Mensajes Esperados

Los modelos Pydantic deben vivir en `packages/contracts/`.

### PredictionCompleted

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `prediction_id`
- `asset_id`
- `platform_id`
- `probability_up`
- `expected_return`
- `confidence`
- `prediction_horizon`

### VoteRequested

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `prediction_id`
- `risk_profile_id`
- `deadline_seconds`

### VoteSubmitted

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `prediction_id`
- `risk_profile_id`
- `agent_jid`
- `vote`
- `confidence`
- `reason`

### InvestmentDecisionMade

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `decision_id`
- `prediction_id`
- `decision`
- `consensus_score`
- `reason`

## Protocolo FIPA

El Agente Jefe debe usar una interacción tipo convocatoria:

```text
Broker -> perfiles: call for proposal / vote request
Perfiles -> Broker: proposal / vote submitted
Broker -> persistencia: investment decision
Broker -> interesados: decision notification
```

## Reglas

- Los agentes no deben contener reglas de inversión complejas.
- Los agentes validan contratos y delegan en servicios.
- Toda conversación debe usar `correlation_id`.
- Los mensajes inválidos se registran y se responden de forma controlada.
- La decisión final siempre queda persistida.

