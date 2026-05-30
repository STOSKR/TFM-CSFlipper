# Implementar pipeline OCR

## Objetivo

Crear el pipeline de OCR para extraer observaciones de mercado desde imagenes o capturas.

## Contexto

El alcance del TFM anade OCR como via complementaria de adquisicion cuando no exista API o scraping fiable.

## Alcance

- Preprocesado basico con OpenCV.
- Invocacion Tesseract sin bloquear el event loop.
- Parser de texto OCR a datos estructurados.
- Validacion de confianza y datos imposibles.
- Persistencia como `market_observations` con `source_type = ocr`.

## Criterios de aceptacion

- Hay un flujo OCR minimo con fixtures.
- El OCR genera el mismo tipo de observacion que otras fuentes.
- Las funciones bloqueantes usan `asyncio.to_thread()` cuando aplique.
- Hay tests de parser y validacion.

## Decisiones tecnicas

- El OCR vive en `packages/vision/`.
- La app de adquisicion lo orquesta.
- OpenCV y Tesseract se cargan de forma perezosa para que parser y tests de texto no fallen si el binario local no esta instalado.

## Pasos realizados

- Implementado paquete `packages.vision` con preprocesado OpenCV, adaptador Tesseract, pipeline async y parser OCR.
- Implementada orquestacion en `apps.acquisition.ocr_import`.
- Implementado CLI `python -m apps.cli.import_ocr_observations`.
- El CLI acepta `.txt` como fixture de texto OCR y capturas de imagen cuando OpenCV/Tesseract esten disponibles.
- La persistencia en Supabase existe pero requiere `--persist` explicito.
- Anadido fixture `tests/fixtures/ocr_observations.txt`.
- Documentados comandos en `apps/cli/README.md`.

## Pruebas ejecutadas

- `python -m pytest`
- `python -m ruff check .`
- `python -m mypy packages apps tests`
- `python -m apps.cli.import_ocr_observations tests\fixtures\ocr_observations.txt --dry-run`

## Bloqueos o riesgos

- Requiere el binario de Tesseract instalado en la maquina para procesar imagenes reales.
- OCR puede ser fragil ante cambios visuales.
- El entorno local actual no tenia `cv2` instalado; para prueba real con captura hay que instalar las dependencias del proyecto y Tesseract.
