# Implementar pipeline OCR

## Objetivo

Crear el pipeline de OCR para extraer observaciones de mercado desde imágenes o capturas.

## Contexto

El alcance del TFM añade OCR como vía complementaria de adquisición cuando no exista API o scraping fiable.

## Alcance

- Preprocesado básico con OpenCV.
- Invocación Tesseract sin bloquear el event loop.
- Parser de texto OCR a datos estructurados.
- Validación de confianza y datos imposibles.
- Persistencia como `market_observations` con `source_type = ocr`.

## Criterios de aceptación

- Hay un flujo OCR mínimo con fixtures.
- El OCR genera el mismo tipo de observación que otras fuentes.
- Las funciones bloqueantes usan `asyncio.to_thread()` cuando aplique.
- Hay tests de parser y validación.

## Decisiones técnicas

- El OCR vive en `packages/vision/`.
- La app de adquisición lo orquesta.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Requiere Tesseract instalado en la máquina.
- OCR puede ser frágil ante cambios visuales.
