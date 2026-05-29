# Protocolos de Agentes

## Objetivo

Definir cómo se comunican los agentes sin duplicar contratos ni mezclar lógica de negocio con SPADE.

## Agentes Iniciales

| Agente | Responsabilidad | Paquetes principales |
| --- | --- | --- |
| Analista | Lee histórico, invoca predicción y emite `PredictionCompleted`. | `packages/prediction/`, `packages/persistence/`, `packages/contracts/` |
| Jefe/Broker | Convoca votación, recoge votos, calcula consenso y registra la decisión simulada. | `packages/decision/`, `packages/persistence/`, `packages/contracts/` |
| Conservador | Vota priorizando confianza alta, liquidez y baja exposición. | `packages/decision/` |
| Moderado | Equilibra retorno esperado, confianza, liquidez y calidad de datos. | `packages/decision/` |
| Arriesgado | Tolera más incertidumbre si el retorno esperado compensa. | `packages/decision/` |
| Liquidez | Evalúa volumen, spread y capacidad de venta posterior. | `packages/decision/`, `packages/simulation/` |
| Tendencia | Evalúa momentum, consistencia temporal y posibles reversiones. | `packages/prediction/`, `packages/decision/` |
| Arbitrajista | Compara precios netos entre plataformas. | `packages/decision/`, `packages/simulation/`, `packages/persistence/` |
| Risk Manager | Supervisa capital, exposición global y bloqueo por trade hold. | `packages/decision/`, `packages/simulation/`, `packages/persistence/` |

Regla común: los agentes validan mensajes y coordinan; la lógica de inversión vive en `packages/decision/`, `packages/prediction/` o `packages/simulation/`.

Los procesos de scraping, API, CSV y OCR no se modelan como agentes iniciales. Pertenecen a la capa de adquisición y publican eventos para que los agentes reaccionen.

El Risk Manager actúa como participante de la votación cuando exista una predicción accionable.
Su voto debe considerar capital disponible, capital bloqueado, posiciones abiertas, fechas de
liberación por `trade hold`, exposición máxima y liquidez mínima. No decide solo: aporta una
restricción de cartera simulada al consenso del Broker.

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
