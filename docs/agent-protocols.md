# Arquitectura de Agentes

## Objetivo

Definir la separacion entre agentes extractores de datos y agentes MARL de decision, sin duplicar contratos ni mezclar logica de negocio con infraestructura.

## Tipos de agentes

### Agentes extractores

Los scrapers, conectores API, OCR, importadores CSV y SteamDT pueden considerarse agentes extractores porque observan fuentes externas, extraen datos, controlan errores y publican observaciones. No se entrenan con reinforcement learning y no deciden operaciones.

| Agente extractor | Responsabilidad | Paquetes principales |
| --- | --- | --- |
| Steam Market extractor | Captura precio, volumen, buy orders e historico disponible de Steam. | `apps/acquisition/`, `packages/persistence/` |
| Buff extractor | Captura precio, volumen, buy orders e historico disponible de Buff. | `apps/acquisition/`, `packages/persistence/` |
| SteamDT extractor | Descubre candidatos y estrategias de busqueda. | `steamdt.py`, `market_workers.py` |
| OCR extractor | Convierte capturas en observaciones estructuradas. | `packages/vision/`, `apps/acquisition/` |
| CSV/API importer | Carga historicos o muestras controladas. | `apps/acquisition/`, `packages/contracts/` |

### Agentes MARL

Los agentes MARL son las politicas cooperativas entrenadas en el entorno PettingZoo/RLlib.

| Agente | Responsabilidad | Paquetes principales |
| --- | --- | --- |
| Scout | Detecta y marca oportunidades de arbitraje. | `packages/simulation/`, entorno PettingZoo |
| Trader | Decide comprar, vender, mantener y tamaño de posicion. | `packages/simulation/`, entorno PettingZoo |
| Portfolio | Gestiona capital, riesgo, exposicion y trade hold. | `packages/simulation/`, `packages/decision/` |

Regla comun: los agentes no contienen logica duplicada de extraccion, prediccion o simulacion. La logica comun vive en `packages/`, y los agentes consumen contratos estables.

## Modelo supervisado

El modelo supervisado no es un agente. Es un servicio de inferencia que devuelve la probabilidad calibrada de que el spread sea rentable a 8 dias. Esa probabilidad se incorpora al espacio de observacion de Scout, Trader y Portfolio.

## Contratos esperados

Los modelos Pydantic deben vivir en `packages/contracts/`.

### MarketSnapshotCaptured

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `asset_id`
- `market_hash_name`
- `steam_price`
- `buff_price`
- `volume`
- `observed_at`
- `source_type`

### SupervisedPredictionCompleted

Contenido minimo:

- `schema_version`
- `correlation_id`
- `prediction_id`
- `asset_id`
- `probability_spread_profitable_8d`
- `model_name`
- `model_version`
- `features_snapshot`

### AgentActionRecorded

Contenido minimo:

- `schema_version`
- `correlation_id`
- `episode_id`
- `agent_id`
- `action`
- `action_payload`
- `policy_checkpoint`

### InvestmentDecisionMade

Contenido mínimo:

- `schema_version`
- `correlation_id`
- `decision_id`
- `asset_id`
- `decision`
- `model_version`
- `policy_checkpoint`
- `reason`

## Flujo MARL

```text
Agentes extractores -> historico/snapshots
Historico -> dataset supervisado
Modelo calibrado -> probabilidad 8d
PettingZoo env -> observaciones locales
Scout/Trader/Portfolio -> acciones cooperativas
Simulador -> recompensa compartida y metricas
```

## SPADE/FIPA

El diseño anterior basado en SPADE, Broker y votacion FIPA queda como antecedente arquitectonico, no como camino principal del TFM actual. Si se recupera, debe implementarse como capa de coordinacion externa y no sustituir al entrenamiento MARL.

## Reglas

- Los agentes extractores no deciden compras.
- Los agentes MARL no hacen scraping ni acceden a fuentes externas.
- Toda accion o prediccion debe usar `correlation_id`.
- Los datos invalidos se registran y se rechazan de forma controlada.
- La decisión final siempre queda persistida.
