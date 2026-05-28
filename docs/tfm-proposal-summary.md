# Resumen del TFM

## Título de Trabajo

Arquitectura multiagente para la toma de decisiones en mercados de activos digitales.

## Contexto

El proyecto se sitúa en la economía virtual de Counter-Strike 2. Los activos principales son skins, cuchillos, guantes, pegatinas y otros objetos cosméticos cuyo valor depende de factores como rareza, demanda, liquidez y float.

Estos activos se negocian en varias plataformas, como Steam, Skinport o Buff. La fragmentación del mercado provoca diferencias de precio entre plataformas y abre oportunidades de arbitraje.

## Problema

La gestión de carteras en este mercado suele hacerse de forma manual o con herramientas estáticas como hojas de cálculo. Esto genera varios problemas:

- dificultad para monitorizar muchos activos a la vez;
- datos fragmentados entre varias plataformas;
- exposición al `trade hold` de 7 días;
- capital inmovilizado;
- dificultad para reaccionar ante cambios rápidos;
- ausencia de herramientas analíticas abiertas y adaptadas al mercado de CS2.

## Propuesta

Diseñar y desarrollar una plataforma de simulación financiera basada en sistemas multiagente.

La plataforma debe permitir:

- validar estrategias de inversión con datos históricos;
- automatizar la gestión simulada del riesgo y del capital;
- descentralizar el análisis mediante agentes especializados;
- evaluar si una arquitectura multiagente puede mejorar la toma de decisiones humana en mercados con alta fricción.

## Metodología

El sistema se apoya en una arquitectura multiagente con especialización por plataforma, horizonte temporal y perfil de riesgo.

Capas conceptuales:

- capa operativa: flippers, swing traders, inversores y arbitrajistas;
- capa analítica: predicción y análisis de series temporales;
- capa de supervisión: gestión global de cartera y riesgo;
- capa de evaluación: medición del rendimiento en datos no vistos.

## Predicción

El mercado de CS2 ofrece histórico de ventas, pero no predicciones propias. El proyecto incorpora modelos de análisis temporal para estimar probabilidad de subida, confianza y rentabilidad esperada.

La implementación puede evolucionar por fases:

1. baselines estadísticos;
2. modelos supervisados sobre features tabulares;
3. LSTM o Transformers para series temporales;
4. aprendizaje por refuerzo multiagente cuando el simulador esté maduro.

## OCR Añadido al Alcance

Además de APIs, scraping y CSV/JSON, el proyecto incluye OCR como mecanismo de adquisición.

El OCR permite extraer datos desde capturas, tablas o interfaces donde no exista una API directa. El flujo técnico está en [ocr-pipeline.md](ocr-pipeline.md).

## Tecnología Base

La pila técnica operativa se mantiene en `pyproject.toml`; las decisiones arquitectónicas están en [architecture.md](architecture.md) y [decisions/](decisions/).

## Restricción Clave

El sistema debe operar como simulador. No debe ejecutar compras reales ni mover capital real durante el desarrollo del TFM.
