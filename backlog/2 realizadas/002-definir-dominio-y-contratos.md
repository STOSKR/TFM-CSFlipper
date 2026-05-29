# Definir dominio y contratos Pydantic

## Objetivo

Crear los modelos base del dominio y los contratos Pydantic V2 compartidos entre servicios y agentes.

## Contexto

El sistema necesita evitar payloads duplicados o improvisados entre adquisicion, prediccion, votacion y decision.

El material de `cs-tracker` ya esta conectado a una tabla real de Supabase (`scraped_items`). Esa tabla se considera una fuente legacy/importable: contiene datos utiles de arbitraje BUFF/Steam, pero no sustituye al modelo canonico del TFM basado en `assets`, `platforms`, `market_observations`, eventos, predicciones, votos y decisiones simuladas.

## Alcance

- Crear entidades/value objects iniciales en `packages/domain/`.
- Crear contratos en `packages/contracts/`.
- Definir enums compartidos para fuente de datos, voto, decision y estado de evento.
- Anadir tests unitarios de validacion.

## Criterios de aceptacion

- Existen modelos Pydantic para eventos y mensajes principales.
- Los contratos incluyen `schema_version` y `correlation_id` cuando aplique.
- No hay contratos duplicados en `apps/`.
- Los tests unitarios pasan.

## Decisiones tecnicas

- Pydantic V2.
- Dominio sin dependencia de SPADE ni Supabase.
- Separar dominio puro y contratos: `packages/domain/` usa dataclasses/enums estandar, `packages/contracts/` usa Pydantic V2.
- Preferir el enfoque limpio de `master-ia-ara` para IDs canonicos y observaciones temporales.
- Tratar la tabla real `scraped_items` de `cs-tracker` como fuente legacy/importable, no como modelo canonico del TFM.
- Preservar campos de arbitraje de `cs-tracker` (`profitability`, `profit_eur`, URLs y precios BUFF/Steam) en un contrato legacy para adaptarlos despues a `assets`, `platforms`, `market_observations` y `raw_payload`.

## Pasos realizados

- Movida la tarea al carril activo del backlog fisico (`backlog/1 progreso/`) tras cerrar la base `001`.
- Revisado material de referencia en `material_a_integrar/002-definir-dominio-y-contratos/` para planificar la integracion selectiva de IDs canonicos, modelos de assets/variantes y observaciones de precio.
- Revisado el esquema Supabase existente de `cs-tracker` (`scraped_items`) y su servicio de almacenamiento.
- Creado `.env` local ignorado por git con `SUPABASE_PROJECT_ID` y `SUPABASE_URL` del proyecto existente.
- Aniadida la variable `SUPABASE_PROJECT_ID` vacia a `.env.example` sin exponer el valor real.
- Creado `packages/__init__.py` para que `mypy` resuelva el monorepo como paquete Python explicito.
- Implementado `packages/domain/canonical_id.py` con generacion determinista de IDs canonicos basada en nombres de mercado, calidad y flags StatTrak/Souvenir.
- Implementados enums compartidos de fuente, voto, decision, estado de evento y tipo de evento en `packages/domain/enums.py`.
- Implementadas entidades puras en `packages/domain/entities.py` para assets, plataformas, observaciones, predicciones, votos, decisiones y outbox.
- Implementados contratos Pydantic V2 en `packages/contracts/` para observaciones normalizadas, eventos outbox y mensajes de agentes.
- Implementado `LegacyScrapedItemContract` para validar filas de la tabla Supabase real `scraped_items`.
- Aniadidos tests unitarios de IDs canonicos, validacion de observaciones, eventos, mensajes y contrato legacy.
- Instaladas herramientas de desarrollo necesarias en el entorno actual: `pydantic`, `pytest`, `pytest-asyncio`, `ruff` y `mypy`.

## Pruebas ejecutadas

- `python -m py_compile packages\domain\canonical_id.py packages\domain\enums.py packages\domain\entities.py packages\contracts\base.py packages\contracts\observations.py packages\contracts\events.py packages\contracts\messages.py packages\contracts\legacy.py tests\unit\test_domain_contracts.py`: OK.
- `python -m pytest`: OK (`7 passed`).
- `python -m ruff check .`: OK.
- `python -m mypy packages tests`: OK.

## Bloqueos o riesgos

- Ajustar nombres finales con el modelo de datos cuando se implemente `003`.
- Definir en `003` si `scraped_items` se migra, se deja como tabla legacy de entrada o se transforma mediante vista/staging.
- Los valores reales de claves Supabase siguen pendientes; solo se ha configurado el project id y la URL local.
