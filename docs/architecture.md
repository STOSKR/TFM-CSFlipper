# Arquitectura

## Contexto

El proyecto estudia el mercado de activos digitales de CS2 como un ecosistema financiero fragmentado. Un mismo activo puede tener precios, liquidez, comisiones y tiempos de disponibilidad distintos en Steam, Skinport, Buff u otras plataformas.

El problema principal no es solo predecir precio. También hay que gestionar fricción temporal, especialmente el `trade hold` de 7 días, comisiones, capital inmovilizado, liquidez y riesgo.

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

### 2. Persistencia

Supabase/Postgres es la fuente de verdad.

Guarda:

- activos;
- observaciones de mercado;
- predicciones;
- perfiles de riesgo;
- votos;
- decisiones;
- eventos de dominio;
- resultados de simulación.

### 3. Predicción

Calcula features sobre histórico de precio, volumen, liquidez, spread, float y plataforma.

Puede empezar con modelos simples como medias móviles, momentum o regresión, y evolucionar a LSTM, Transformers de series temporales o modelos de aprendizaje por refuerzo.

### 4. Decisión Multiagente

Los agentes SPADE coordinan el flujo:

- el Agente Analista solicita o ejecuta predicciones;
- el Agente Jefe convoca votaciones;
- los agentes de perfil evalúan desde distintas estrategias;
- el consenso genera una decisión simulada.

La lógica de decisión vive en `packages/decision/`, no dentro de los agentes.

### 5. Simulación y Evaluación

El simulador replica:

- comisiones por plataforma;
- trade hold de 7 días;
- capital disponible e inmovilizado;
- inventario;
- liquidez;
- slippage o diferencia entre precio observado y precio ejecutable;
- ventanas temporales de entrenamiento y evaluación.

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

