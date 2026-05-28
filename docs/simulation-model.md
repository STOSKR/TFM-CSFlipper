# Simulación y Evaluación

## Objetivo

El sistema debe evaluar estrategias sin exponer capital real. Todas las compras y ventas son simuladas hasta que el Scrum Master indique explícitamente otra cosa.

## Reglas de Mercado a Simular

### Trade Hold

Los activos comprados quedan bloqueados durante 7 días. Durante ese periodo:

- no pueden venderse;
- el capital queda inmovilizado;
- el sistema debe medir coste de oportunidad;
- una caída de precio puede afectar al rendimiento aunque la señal inicial fuera positiva.

### Comisiones

Cada plataforma puede aplicar comisiones distintas.

El simulador debe calcular:

- coste de entrada;
- coste de salida;
- precio neto;
- rentabilidad neta.

### Liquidez

No basta con que el precio suba. Debe existir capacidad razonable de salida.

Métricas posibles:

- volumen observado;
- número de listings;
- spread;
- tiempo estimado de venta.

## Agentes Estratégicos

La capa operativa puede evolucionar hacia varios perfiles:

- Flipper: corto plazo.
- Swing trader: medio plazo.
- Inversor: largo plazo.
- Arbitrajista: discrepancias entre plataformas.

## Evaluación

El sistema debe separar:

- datos de entrenamiento;
- datos de validación;
- datos de evaluación no vistos.

Métricas iniciales:

- rentabilidad neta;
- drawdown;
- porcentaje de aciertos;
- capital inmovilizado medio;
- rotación de cartera;
- decisiones rechazadas por riesgo;
- impacto del trade hold.

## Salidas Esperadas

Cada ejecución de simulación debe producir:

- configuración usada;
- periodo temporal;
- activos evaluados;
- decisiones simuladas;
- posiciones abiertas/cerradas;
- métricas agregadas;
- errores o datos insuficientes.

