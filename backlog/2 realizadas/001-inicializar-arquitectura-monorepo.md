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

- Movida la tarea al carril activo del backlog físico (`backlog/1 progreso/`).
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
- Aclarada en `README.md`, `ESTRUCTURA_PROYECTO.md` y `prompt_maestro.md` la estructura real del backlog: `0 pendientes`, `1 progreso` y `2 realizadas`.
- Añadida regla explícita de inventariar e integrar material existente antes de crear implementaciones nuevas.
- Registrada `material_a_integrar/` como zona local de entrada para repos, scripts, notebooks, datasets, capturas y documentación previa.
- Añadida regla en `.gitignore` para no versionar repos/datos brutos dentro de `material_a_integrar/`.
- Revisado el inventario inicial de `material_a_integrar/` para detectar piezas reutilizables antes de implementar servicios nuevos.
- Extraídas piezas útiles a carpetas de `material_a_integrar/` alineadas con las tareas del backlog (`002-...`, `003-...`, etc.), separadas por repo de origen y listas para migración selectiva.
- Recuperado material adicional antes de limpiar repos brutos: catálogos completos, métricas de experimentos, scheduler, scripts de notebooks/policy bundle, demo web y documentación de evaluación.
- Conservados artefactos entrenados del predictor (`.joblib`) y splits (`.pkl`) en la carpeta de la tarea `008` para no perder el modelo existente.
- Documentado el flujo operativo objetivo en `docs/operational-flow.md` y enlazado desde `README.md` y `docs/architecture.md`.
- Actualizadas tareas pendientes relacionadas con almacenamiento append-only, scraping con cookies/delays/workers, prefiltro del predictor, votación con Risk/Portfolio Manager y simulación de capital bloqueado.
- Detectado que el test minimo de estructura seguia validando nombres antiguos del backlog (`pendientes`, `en_progreso`, `realizadas`).
- Corregido `tests/unit/test_project_structure.py` para validar las carpetas reales `backlog/0 pendientes`, `backlog/1 progreso` y `backlog/2 realizadas`.
- Aniadida validacion de `apps/cli` al test minimo de estructura.

## Inventario de material a integrar

Revisión realizada sobre `material_a_integrar/` sin leer secretos (`.env`) ni considerar entornos virtuales, `.git`, logs o sesiones como material reutilizable.

### `Cs-scraper`

Proyecto Python amplio para construir dataset histórico de mercado CS2, entrenar modelos de dirección de precio, servir recomendaciones y visualizar históricos.

Áreas detectadas:

- `auth/`: captura de sesión CSFloat con Playwright, cookies cifradas con Fernet y validación contra `/api/v1/me`.
- `catalog/`: construcción de catálogo maestro desde CSFloat, normalización de nombres, wear, StatTrak, rareza, colección y clasificación por categoría.
- `scraper/`: scraping de histórico Steam Market por variante (`wear` + `st`), fallback por `priceoverview`, fallback Playwright, rate limiting y almacenamiento incremental JSON jerárquico.
- `analytics/`: carga de históricos, agregación diaria ponderada, generación de dataset científico, features temporales, señales baseline, métricas de política y bundles de inferencia.
- `model_service/`: API FastAPI para `/predict` y `/recommendations` sobre artefactos LightGBM.
- `dashboard/`: dashboard Streamlit para catálogo, cobertura, series, proveedores y panel de predicción.
- `notebooksV2/`: notebooks y artefactos de experimentación temporal con LightGBM, thresholds, calibración, evaluación final y `policy_bundle.json`.
- `tests/`: cobertura útil para scraping, almacenamiento, catálogo, dashboard, dataset, políticas y servicio de modelo.

Piezas aprovechables:

- `catalog/_parsing.py` y `catalog/_schema.py`: muy útiles para `packages/domain/` y `packages/contracts/` al definir assets, variantes, wear, StatTrak, categorías, rareza y colecciones.
- `scraper/_price_storage.py`: buen formato incremental por item/variante y deduplicación por timestamp. Puede inspirar importación local y normalización a `market_observations`.
- `scraper/price_scraper.py`: lógica de extracción Steam Market, parsing de precio/volumen/moneda, fallback ante errores y validación de snapshots. Encaja con `apps/acquisition/` y tarea `006`.
- `analytics/loader.py`: loader robusto para JSON jerárquico y legacy, con agregación diaria ponderada. Encaja con `packages/prediction/` y tareas `005`/`008`.
- `analytics/direction_dataset.py` y `analytics/scientific_dataset.py`: base fuerte para dataset temporal leakage-free, features, target de dirección y splits temporales. Encaja directamente con `packages/prediction/` y tarea `008`.
- `analytics/direction_signal.py`: predictor baseline simple por momentum/volatilidad. Encaja como primera versión de `packages/prediction/`.
- `analytics/policy_metrics.py` y `analytics/policy_bundle.py`: selección por thresholds, cobertura, precisión, pérdida y utilidad. Encaja con `packages/decision/`, `packages/prediction/` y evaluación.
- `model_service/features.py`: cálculo de features para inferencia online desde histórico corto. Útil para servir predicciones sin depender de notebooks.
- `model_service/recommendations.py`: ranking de candidatos por probabilidad, subida esperada o score híbrido. Puede alimentar simulación/evaluación antes de agentes.
- `tests/`: especialmente aprovechables los tests de dataset, storage, price scraper, policy metrics, recomendaciones y features.
- `notebooksV2/artifacts/scientific_v2/final_results.json`: evidencia experimental existente. El resultado global no supera claramente el baseline (`balanced_accuracy` ~0.4666 vs referencia ~0.4673), pero los thresholds selectivos muestran señales de alta precisión con baja cobertura.
- `notebooksV2/artifacts/scientific_v2/policy_bundle.json`: útil como referencia de contrato de inferencia/política, aunque indica que el modelo primario `lgbm_grid_1` no está disponible localmente y usa fallback `lgbm_grid_2`.

Riesgos:

- Mezcla muchas responsabilidades en un mismo repo: adquisición, dataset, ML, API, dashboard, notebooks y despliegue web. Hay que migrar por piezas, no copiar estructura completa.
- Hay scripts temporales `tmp_*`, notebooks ejecutados, artefactos pesados y datos crudos; no deben entrar al monorepo como código final.
- Usa `requests` y Playwright síncrono en partes críticas; en el monorepo conviene envolver o rediseñar para no bloquear servicios async.
- El objetivo actual del TFM es simulación auditada multiagente; las recomendaciones directas de compra deben traducirse a decisiones simuladas y votos, no acciones reales.
- Los modelos/artifacts existentes sirven como baseline experimental, pero no deben darse por válidos sin reproducir dataset, splits, métricas y trazabilidad.

### `Cs-Tracker`

Proyecto Python orientado a arbitraje BUFF -> Steam con Playwright, Pydantic, Supabase, Click y structlog.

Piezas aprovechables:

- `app/domain/rules.py`: fórmulas iniciales de comisiones, ROI, beneficio y conversión CNY/EUR. Encaja en `packages/simulation/` y `packages/decision/`, pero debe parametrizarse; ahora usa constantes fijas.
- `app/domain/models.py`: modelo Pydantic `ScrapedItem` útil como referencia para contratos de adquisición, aunque habrá que adaptarlo a `market_observations` y al modelo común de `packages/contracts/`.
- `app/services/scraping.py`, `workers.py` y extractores: patrón producer-consumer con workers concurrentes para scraping. Encaja como base para `apps/acquisition/` y la tarea `006`.
- `app/services/extractors/buff_extractor.py`, `steam_extractor.py` y `detailed_item_extractor.py`: lógica específica de plataformas, reutilizable como referencia al crear conectores desacoplados.
- `config/schema.sql`: vistas e índices útiles como inspiración, pero no debe copiarse tal cual porque el monorepo ya define un modelo más general (`assets`, `platforms`, `market_observations`, `predictions`, `votes`, `investment_decisions`).
- `config/scraper_config.json`: perfiles de estrategia y límites de scraping útiles para configuración futura de adquisición/decisión.

Riesgos:

- Incluye `.env`, `venv`, logs, sesiones y `.git`; deben permanecer fuera del control de versiones.
- Usa Supabase client síncrono envuelto en executor; para el monorepo conviene preferir `asyncpg` o SQLAlchemy async en `packages/persistence/`.
- Está orientado a oportunidades directas de arbitraje, mientras que este TFM exige simulación, outbox y trazabilidad multiagente.

### `Master-IA-ARA`

Proyecto Python más cercano a una librería de extracción histórica multi-fuente. Usa `httpx`, `pandas`, `pandera`, Pydantic, Typer, pytest, ruff y mypy.

Piezas aprovechables:

- `src/extraction/kernel.py`: kernel asíncrono con concurrencia limitada, reintentos, métricas y dumps de anomalías. Muy aprovechable para `apps/acquisition/` y `packages/persistence`/outbox como patrón de observabilidad.
- `src/extraction/connectors/`: conectores probe-first para Steam, SteamDT, Buff, CSFloat y CS.Money. Encaja directamente con la tarea `006`.
- `src/extraction/models.py`: dataclasses limpias para `ExtractionTarget`, `PricePoint`, `ConnectorExtraction` y métricas. Buena base conceptual para contratos/dominio, aunque en el monorepo los contratos compartidos deben ir con Pydantic V2.
- `src/cs2_trend/domain/canonical_id.py`: generación determinista de IDs canónicos de items. Encaja en `packages/domain/` y tarea `002`.
- `src/cs2_price_trend/quality/`: validación Pandera de históricos, contratos tabulares y saneamiento. Encaja en `packages/prediction/` o adquisición antes de persistir observaciones.
- `data/catalog/`: catálogo maestro CS2 ya generado en CSV/JSON. Puede servir como semilla para `assets` en tarea `003`.
- `tests/`: buena base de tests unitarios para extracción, calidad, catálogo, pathing y métricas.

Riesgos:

- Requiere credenciales/cookies para fuentes protegidas, especialmente CSFloat/Buff.
- Hay que separar material académico/orquestador de código importable.
- Usa dataclasses para modelos internos; habrá que mapearlos a contratos Pydantic y entidades del monorepo.

### `Master-IA-RES-ReconocimientoGrafica`

Proyecto Python de visión/OCR para reconstruir series temporales desde gráficas rasterizadas de Steam/CS2. Usa OpenCV, NumPy, pandas, scikit-learn y PaddleOCR opcional.

Piezas aprovechables:

- `src/recongrafica/pipeline.py`: flujo completo imagen -> layout -> OCR/anclas -> señal -> serie -> métricas -> salidas. Encaja con `packages/vision/` y tarea `007`.
- `src/recongrafica/parsing.py`: parser robusto de precios y fechas con separadores europeos/anglosajones. Muy útil para OCR y adquisición.
- `src/recongrafica/calibration.py`: transformación de coordenadas de píxel a fechas/precios mediante anclas de ejes. Base fuerte para reconstrucción de histórico visual.
- `src/recongrafica/models.py`: dataclasses para cajas, layout, OCRResult, anclas y puntos de serie. Reutilizable como referencia de dominio interno de visión.
- `tests/`: pruebas de parsing, calibración y pipeline sintético. Buen punto de partida para tests de `packages/vision/`.
- `docs/memoria_tecnica.md` y resultados de ejemplo: útiles para justificar el componente OCR en el TFM.

Riesgos:

- Está pensado para gráficas, no para tablas/listings; hay que integrarlo como una variante del pipeline OCR.
- Usa PaddleOCR opcional, mientras que la documentación actual menciona Tesseract. Conviene decidir si mantener Tesseract, permitir PaddleOCR como backend alternativo o abstraer motor OCR.
- Las salidas actuales son CSV/JSON; habrá que normalizarlas a `market_observations`.

### Priorización recomendada de integración

1. Para `002-definir-dominio-y-contratos`: reutilizar ideas de IDs canónicos de `Master-IA-ARA`, modelos de observación/precio de `Master-IA-ARA`, catálogo/variantes/wear de `Cs-scraper` y campos de `ScrapedItem` de `Cs-Tracker`.
2. Para `003-definir-modelo-datos-supabase`: usar catálogos de `Master-IA-ARA` y `Cs-scraper` como posibles semillas de `assets`; revisar vistas/índices de `Cs-Tracker` como inspiración, no como esquema final.
3. Para `004-implementar-persistencia-y-outbox`: inspirarse en métricas/dumps de `Master-IA-ARA`; evitar copiar la persistencia Supabase síncrona de `Cs-Tracker`.
4. Para `005-adquisicion-manual-csv`: aprovechar loaders de `Cs-scraper` para JSON jerárquico de precios y normalizarlos a observaciones.
5. Para `006-automatizaciones-scraping-plataformas`: partir de conectores probe-first de `Master-IA-ARA`, scraping Steam/CSFloat de `Cs-scraper` y scraping Playwright/worker pool de `Cs-Tracker`.
6. Para `007-implementar-pipeline-ocr`: migrar selectivamente parsing, calibración, extracción de señal, tests y documentación de `Master-IA-RES-ReconocimientoGrafica`.
7. Para `008-implementar-predictor-baseline`: partir de `analytics/direction_signal.py`, `analytics/direction_dataset.py`, `analytics/scientific_dataset.py`, `model_service/features.py` y resultados de `notebooksV2`.
8. Para `010-implementar-reglas-perfiles-riesgo`: reutilizar ideas de `analytics/policy_metrics.py` y `policy_bundle.py` para thresholds, cobertura, precisión, pérdida y utilidad.

## Pruebas ejecutadas

- `python --version`: OK (`Python 3.11.9`).
- `python -c "import tomllib, pathlib; tomllib.load(pathlib.Path('pyproject.toml').open('rb')); print('pyproject OK')"`: OK.
- `python -m py_compile tests\unit\test_project_structure.py`: OK.
- Invocacion directa de `test_project_structure_exists` mediante `importlib`: OK.
- `python -m pytest`: no ejecutado porque `pytest` no esta instalado en el entorno actual.
- `python -m ruff check .`: no ejecutado porque `ruff` no esta instalado en el entorno actual.

## Bloqueos o riesgos

- Confirmar si se usara Supabase local mediante CLI/Docker o solo proyecto remoto.
- Instalar dependencias de desarrollo para ejecutar `pytest`, `ruff` y `mypy` como checks completos.
