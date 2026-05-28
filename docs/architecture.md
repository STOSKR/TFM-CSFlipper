# Arquitectura

## Contexto

El contexto académico y de mercado está resumido en [tfm-proposal-summary.md](tfm-proposal-summary.md). Este documento se centra solo en la arquitectura técnica.

## Objetivo Técnico

Construir una plataforma de simulación financiera con arquitectura multiagente capaz de:

- adquirir datos de mercado mediante APIs, scraping y OCR;
- consolidar histórico en Supabase/Postgres;
- calcular señales predictivas sobre series temporales;
- simular operaciones respetando reglas reales del mercado;
- tomar decisiones simuladas mediante consenso entre agentes especializados;
- evaluar rendimiento sobre periodos no vistos durante entrenamiento.

## Capas

### 1. Adquisición

Responsable de capturar datos desde:

- APIs públicas o privadas;
- scraping web;
- OCR sobre capturas, gráficos o tablas cuando no exista API cómoda;
- CSV/JSON importados manualmente.

La adquisición valida y normaliza datos antes de guardarlos. Después registra eventos en la outbox.

Los scrapers, conectores API, importadores CSV y procesos OCR son automatizaciones de adquisición. No son agentes SPADE por defecto: deben poder ejecutarse como jobs, comandos CLI o servicios programados. Si más adelante se necesita coordinación inteligente de fuentes, se podrá añadir un agente coordinador de adquisición.

### 2. Persistencia

Supabase/Postgres es la fuente de verdad. El detalle de tablas vive en [data-model.md](data-model.md).

### 3. Predicción

Calcula features sobre histórico de precio, volumen, liquidez, spread, float y plataforma.

Puede empezar con modelos simples como medias móviles, momentum o regresión, y evolucionar a LSTM, Transformers de series temporales o modelos de aprendizaje por refuerzo.

### 4. Decisión Multiagente

Los agentes SPADE coordinan el flujo:

- el Agente Analista solicita o ejecuta predicciones;
- el Agente Jefe convoca votaciones;
- los agentes de perfil evalúan desde distintas estrategias.

La definición completa de agentes, mensajes y FIPA está en [agent-protocols.md](agent-protocols.md).

### 5. Simulación y Evaluación

El simulador replica reglas de mercado como comisiones, liquidez y `trade hold`. El detalle vive en [simulation-model.md](simulation-model.md).

## Flujo Principal

```text
Fuente externa
  -> adquisición OCR/scraping/API
  -> market_observations
  -> outbox: MarketObservationCaptured
  -> Agente Analista
  -> predictions
  -> Agente Jefe
  -> votación FIPA
  -> votes
  -> investment_decisions
  -> simulador/evaluador
```

## Regla de Dependencias

Las dependencias apuntan hacia dentro:

```text
apps -> packages
infrastructure -> domain
agents -> contracts/use cases
domain -> nada externo
```

SPADE, Supabase, OpenCV, Tesseract y TensorFlow son detalles de infraestructura o servicios especializados. No deben contaminar el dominio.
