# Pipeline OCR

## Motivo

El resumen inicial del TFM se centra en APIs, scraping y datos tabulares, pero el proyecto añade una vía de adquisición mediante OCR para capturar precios, históricos o tablas cuando la fuente no expone datos estructurados de forma cómoda.

## Alcance

El OCR pertenece a la capa de adquisición. Su salida debe ser equivalente a cualquier dato obtenido por API o scraping: una observación de mercado validada y persistida.

## Flujo

```text
captura o imagen
  -> preprocesado OpenCV
  -> OCR Tesseract
  -> parsing estructurado
  -> validación Pydantic
  -> normalización
  -> market_observations
  -> outbox: MarketObservationCaptured
```

## Componentes

### Preprocesado

Responsable de mejorar la imagen:

- recorte de región relevante;
- escala de grises;
- binarización;
- reducción de ruido;
- aumento de contraste;
- corrección de perspectiva si aplica.

### OCR

Responsable de extraer texto bruto.

Reglas:

- no bloquear el event loop;
- ejecutar Tesseract con `asyncio.to_thread()` si se invoca desde contexto asíncrono;
- guardar referencia a la fuente para auditoría.

### Parser

Responsable de convertir texto a datos estructurados:

- activo;
- plataforma;
- precio;
- moneda;
- volumen;
- fecha/hora observada;
- confianza de extracción.

### Validador

Responsable de rechazar datos imposibles:

- precios negativos;
- moneda desconocida;
- fechas futuras no justificadas;
- activos no reconocidos;
- confianza OCR demasiado baja.

## Datos a Persistir

La salida OCR se persiste como `market_observations` con `source_type = ocr`. El detalle de campos está en [data-model.md](data-model.md).

## Riesgos

- OCR frágil ante cambios visuales de la plataforma.
- Ambigüedad entre separadores decimales europeos y anglosajones.
- Capturas con baja resolución.
- Valores confundidos por símbolos de moneda o etiquetas cercanas.

## Estrategia de Tests

- tests unitarios para parser;
- fixtures de texto OCR simulado;
- pruebas con imágenes pequeñas controladas;
- validaciones contra casos con separador decimal `,` y `.`;
- test de rechazo de valores imposibles.
