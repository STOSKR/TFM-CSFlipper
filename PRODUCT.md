# Product

## Register

product

## Users

El usuario principal es el desarrollador-investigador del TFM y operador del sistema CSFlipper. Usa la interfaz para entender el estado del proyecto, revisar datos de mercado, verificar modelos, inspeccionar simulaciones y, mas adelante, observar decisiones de agentes MARL antes de aceptar cualquier recomendacion.

El contexto de uso es trabajo tecnico y operativo: sesiones largas frente a escritorio, comparacion de precios Steam/BUFF, lectura de metricas, depuracion de pipelines y validacion de decisiones simuladas. La interfaz debe ayudar a pensar, no competir por atencion.

## Product Purpose

CSFlipper visualiza el progreso del sistema multiagente de inversion simulada en mercados de activos digitales de CS2. La interfaz debe convertir componentes tecnicos en estados comprensibles: adquisicion, modelo supervisado, simulador de cartera, restricciones de riesgo, agentes Scout/Trader/Portfolio y recomendaciones.

El exito es poder abrir el panel y responder rapidamente: que funciona, que esta pendiente, que modelo esta activo, que capital esta bloqueado, que agentes estan actuando y por que una oportunidad se recomienda, se observa o se descarta.

## Brand Personality

Profesional, analitica y sobria.

La voz debe sonar como una herramienta de decision seria: precisa, calmada y honesta con las limitaciones. Puede tener pequenos momentos de claridad visual, pero no debe sentirse dramatica, ludica ni promocional.

## Anti-references

- No debe parecer una landing page de SaaS.
- No debe usar heroes gigantes, gradientes morados, glassmorphism decorativo ni metricas falsas.
- No debe parecer un dashboard generico hecho por IA con tarjetas repetidas y poco contenido real.
- No debe ser visualmente complicada: evitar capas innecesarias, exceso de colores, animaciones decorativas y ruido ornamental.
- No debe ocultar incertidumbre. Si un modelo es experimental o un dato es insuficiente, debe decirlo claramente.

## Design Principles

1. Estado antes que espectaculo: cada pantalla debe mostrar el estado operativo real del sistema antes que decorar.
2. Densidad moderada: aprovechar el espacio con tablas, filtros y paneles utiles, sin abrumar ni llenar la vista de adornos.
3. Trazabilidad visible: cada recomendacion debe poder explicar modelo, threshold, dato de entrada, agente o restriccion implicada.
4. Honestidad experimental: distinguir claramente entre modelo experimental, simulacion, decision MARL y accion real.
5. Progreso acumulativo: la interfaz debe crecer con el backlog, dejando huecos utiles para tareas futuras sin fingir que ya existen.

## Accessibility & Inclusion

Objetivo minimo WCAG AA para contraste, foco visible y navegacion por teclado en controles principales. El color nunca debe ser el unico canal para comunicar estado: usar texto, iconos y etiquetas. El movimiento debe ser reducido, limitado a transiciones de estado y respetar preferencias de reduccion de movimiento cuando se implemente.
