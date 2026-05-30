# Implementar adquisicion manual por CSV/JSON

## Objetivo

Crear la primera via simple de ingesta para cargar observaciones de mercado sin depender todavia de scraping ni OCR.

## Contexto

Antes de automatizar fuentes externas, conviene poder alimentar el sistema con datos controlados para probar persistencia, prediccion y agentes.

## Alcance

- Definir formato CSV/JSON esperado.
- Soportar el formato JSON jerarquico extraido en `material_a_integrar/005-adquisicion-manual-csv-json/cs-scraper`.
- Crear parser y normalizador.
- Validar observaciones con contratos.
- Persistir `market_observations`.
- Crear evento `MarketObservationCaptured`.
- Anadir comando CLI de importacion.

## Criterios de aceptacion

- Se puede importar un archivo de ejemplo.
- Se puede importar o adaptar un historico local previamente extraido sin reescribir el scraper.
- Los datos invalidos se rechazan con errores claros.
- Cada observacion valida genera evento outbox.
- Hay tests unitarios del parser.

## Decisiones tecnicas

- Esta ingesta es automatizacion de adquisicion, no agente SPADE.
- Parser implementado con libreria estandar (`csv`, `json`) para no depender de pandas en runtime.
- CSV/JSON planos se normalizan a `MarketObservationContract`.
- JSON jerarquico de `cs-scraper` se interpreta como importacion manual `source_type=csv`, plataforma `steam` y precio en centimos convertido a EUR.
- La persistencia usa `MarketObservationIngestionRepository`, que inserta observacion y evento outbox en una transaccion.

## Pasos realizados

- Movida la tarea al carril activo del backlog fisico (`backlog/1 progreso/`).
- Revisado material de `material_a_integrar/005-adquisicion-manual-csv-json/`.
- Implementado `apps/acquisition/manual_import.py`.
- Implementado CLI `python -m apps.cli.import_observations`.
- Aniadido modo `--dry-run` para validar sin persistir.
- Aniadido fixture `tests/fixtures/manual_observations.csv`.
- Aniadidos tests unitarios para CSV, JSON jerarquico e input invalido.
- Probado CLI con fixture en modo dry-run.

## Pruebas ejecutadas

- `python -m apps.cli.import_observations tests\fixtures\manual_observations.csv --dry-run`: OK (`validated_observations=1`).
- `python -m pytest`: OK (`18 passed`).
- `python -m ruff check .`: OK.
- `python -m mypy packages apps tests`: OK.

## Bloqueos o riesgos

- No quedan bloqueos para esta tarea.
- La importacion real sin `--dry-run` requiere `.env` con `DATABASE_URL` valida.
