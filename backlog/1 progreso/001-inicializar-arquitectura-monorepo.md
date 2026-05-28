# Inicializar arquitectura monorepo y base Supabase

## Objetivo

Crear la estructura base del proyecto como monorepo modular, preparada para servicios Python asíncronos, agentes SPADE, contratos compartidos y persistencia en Supabase/Postgres.

## Contexto

El prompt maestro define el proyecto `CS2 Consorcio de Inversión` como un sistema distribuido inteligente con adquisición de datos, análisis temporal mediante LSTM y decisión por consenso entre agentes de riesgo.

También se ha revisado el resumen del TFM `Propuesta TFM v2.pdf`, que añade el contexto académico: mercado de activos digitales de CS2, fragmentación entre plataformas, trade hold de 7 días, simulación financiera, multiagente/MARL, predicción de series temporales y evaluación en datos no vistos. El alcance actual incorpora además adquisición mediante OCR.

## Alcance

- Crear estructura de carpetas `apps/`, `packages/`, `tests/` y `docs/`.
- Crear `pyproject.toml` con dependencias base de desarrollo.
- Añadir configuración inicial para tests, linting y tipado.
- Crear `.env.example` con variables esperadas para Supabase y agentes.
- Documentar la arquitectura inicial en `docs/architecture.md`.
- Definir una primera propuesta de tablas Supabase/Postgres en `docs/data-model.md`.

## Criterios de aceptación

- El proyecto tiene estructura monorepo clara.
- Las capas principales están separadas.
- Existe documentación mínima para que un nuevo chat entienda cómo continuar.
- No hay lógica duplicada ni contratos repetidos.
- Se puede ejecutar al menos un test mínimo de comprobación del entorno.

## Decisiones técnicas

- Repositorio monorepo modular.
- Persistencia preferente: Supabase/Postgres.
- Contratos compartidos: `packages/contracts/`.
- Dominio desacoplado de SPADE e infraestructura.

## Pasos realizados

- Movida la tarea desde `backlog/pendientes/` a `backlog/en_progreso/`.
- Creada estructura base `apps/`, `packages/`, `tests/` y `docs/`.
- Añadidos README de orientación en cada app y paquete principal.
- Creado `README.md` raíz con visión del proyecto y enlaces de documentación.
- Creado `pyproject.toml` con dependencias base y configuración de pytest, ruff y mypy.
- Creado `.env.example` con variables esperadas para Supabase, SPADE/XMPP y OCR.
- Creado `docker-compose.yml` con Postgres local compatible para desarrollo.
- Documentada la arquitectura inicial en `docs/architecture.md`.
- Documentado el resumen del TFM en `docs/tfm-proposal-summary.md`.
- Documentado el modelo de datos inicial en `docs/data-model.md`.
- Documentados los protocolos multiagente en `docs/agent-protocols.md`.
- Documentado el pipeline OCR en `docs/ocr-pipeline.md`.
- Documentado el modelo de simulación y evaluación en `docs/simulation-model.md`.
- Añadidos ADRs iniciales en `docs/decisions/`.
- Añadido test mínimo de estructura en `tests/unit/test_project_structure.py`.
- Añadido `ESTRUCTURA_PROYECTO.md` en la raíz para consultar rápidamente el árbol del monorepo, agentes, servicios y flujo funcional.
- Revisados los Markdown para reducir repetición: `ESTRUCTURA_PROYECTO.md` queda como índice rápido y los detalles se referencian desde `docs/`.
- Simplificados README internos de `apps/` y `packages/` para que enlacen al documento dueño de cada tema.
- Aclarado que scraping/API/CSV/OCR son automatizaciones de adquisición, no agentes SPADE iniciales.

## Pruebas ejecutadas

- `python` + `tomllib` para validar que `pyproject.toml` parsea correctamente: OK.
- Ejecución manual del test `test_project_structure_exists`: OK.
- `python -m py_compile .\tests\unit\test_project_structure.py`: OK.
- `python -m pytest`: no ejecutado porque `pytest` no está instalado en el entorno actual.
- `python -m ruff check .`: no ejecutado porque `ruff` no está instalado en el entorno actual.

## Bloqueos o riesgos

- Confirmar si se usará Supabase local mediante CLI/Docker o solo proyecto remoto.
- Confirmar versión exacta de Python objetivo.
- Instalar dependencias de desarrollo para ejecutar `pytest`, `ruff` y `mypy`.
