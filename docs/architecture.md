# Arquitectura

## Contexto

El contexto académico y de mercado está resumido en [tfm-proposal-summary.md](tfm-proposal-summary.md). Este documento se centra solo en la arquitectura técnica.

## Objetivo Técnico

Construir una plataforma de simulación financiera con arquitectura multiagente capaz de:

- adquirir datos de mercado mediante APIs, scraping y OCR;
- consolidar histórico en Supabase/Postgres;
- entrenar un modelo supervisado tabular que estime probabilidades calibradas de spread rentable;
- simular operaciones respetando reglas reales del mercado;
- entrenar agentes MARL cooperativos para tomar decisiones simuladas;
- evaluar rendimiento sobre periodos no vistos durante entrenamiento.

## Capas

### 1. Adquisición

Responsable de capturar datos desde:

- APIs públicas o privadas;
- scraping web;
- OCR sobre capturas, gráficos o tablas cuando no exista API cómoda;
- CSV/JSON importados manualmente.

La adquisición valida y normaliza datos antes de guardarlos. Después registra eventos en la outbox.

Los scrapers, conectores API, importadores CSV, SteamDT y procesos OCR pueden describirse como agentes extractores o agentes de adquisición: observan una fuente, extraen datos, controlan errores y publican observaciones. No forman parte del núcleo MARL ni se entrenan con MAPPO; deben poder ejecutarse como jobs, comandos CLI o servicios programados.

### 2. Persistencia

Supabase/Postgres es la fuente de verdad. El detalle de tablas vive en [data-model.md](data-model.md).

### 3. Predicción

Calcula features sobre histórico de precio, volumen, liquidez, spread y plataforma.

El componente supervisado compara modelos tabulares, selecciona el mejor con splits temporales, calibra probabilidades y serializa un artefacto de inferencia. Su salida principal es la probabilidad calibrada de que el spread siga siendo rentable en un horizonte simplificado de 8 días.

### 4. Decisión MARL

El núcleo de decisión usa aprendizaje por refuerzo multiagente cooperativo:

- Scout detecta y marca oportunidades;
- Trader decide compra, venta, mantener y tamaño de posición;
- Portfolio gestiona riesgo, exposición y capital bloqueado.

El objetivo de entrenamiento es MAPPO bajo CTDE: critico centralizado durante entrenamiento y ejecucion descentralizada por actor local en inferencia. El estado actual es mas pequeno: existe un smoke PPO multiagente con PettingZoo/RLlib, checkpoint y estado central expuesto; falta conectar el critico centralizado antes de presentarlo como MAPPO/CTDE completo. La probabilidad supervisada entra como feature de observacion, no como decision final.

### 5. Simulación y Evaluación

El simulador replica reglas de mercado como comisiones, liquidez y `trade hold`. El detalle vive en [simulation-model.md](simulation-model.md).

## Flujo Principal

```text
Fuente externa
  -> agentes extractores OCR/scraping/API/SteamDT
  -> market_items / market_history_points
  -> dataset supervisado
  -> modelo calibrado en inferencia
  -> entorno PettingZoo
  -> Scout / Trader / Portfolio
  -> decision simulada
  -> simulador/evaluador
```

El flujo operativo detallado, incluyendo scraping periódico, OCR, cookies, delays aleatorios,
workers paralelos, predicción supervisada, entorno MARL y cartera simulada, está en
[operational-flow.md](operational-flow.md).

## Regla de Dependencias

Las dependencias apuntan hacia dentro:

```text
apps -> packages
infrastructure -> domain
agents -> contracts/use cases
domain -> nada externo
```

PettingZoo, RLlib, Supabase, OpenCV, Tesseract y librerías ML son detalles de infraestructura o servicios especializados. No deben contaminar el dominio.
