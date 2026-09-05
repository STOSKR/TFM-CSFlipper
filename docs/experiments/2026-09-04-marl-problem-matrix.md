# Matriz de problemas MARL

Esta matriz evalúa el aprendizaje con PPO sobre cinco problemas de cartera.
Todos usan `trading_profit_v2`, la ruta de compra en BUFF y venta en Steam,
episodios temporales de 14 días y las particiones temporales ya definidas por
el dataset. La prueba independiente no se carga ni se consulta durante la
matriz: la selección se realiza únicamente con validación.

| Problema | Activos | Saldo inicial | Perfil de cartera |
|---|---:|---:|---|
| Pequeño y restrictivo | 5 | 500 EUR | Máximo de 3 posiciones, reserva de efectivo del 25 % y límites estrictos de exposición. |
| Medio estándar | 20 | 1.000 EUR | Máximo de 8 posiciones y límites de referencia. |
| Grande estándar | 100 | 5.000 EUR | Máximo de 20 posiciones y límites de referencia. |
| Medio concentrado | 20 | 1.000 EUR | Máximo de 3 posiciones y límites de posición, activo y plataforma más amplios. |
| Medio diversificado | 20 | 1.000 EUR | Máximo de 12 posiciones y límites más estrictos por posición y activo. |

Cada problema se repite con las semillas 7, 19 y 31: 15 entrenamientos en
total. Los activos de los escenarios de 5 y 20 elementos se eligen de forma
determinista, repartiendo sus precios medianos en el rango disponible de los
cortes de entrenamiento y validación. Así, la selección no usa la prueba ni
la etiqueta futura.

En cada iteración se guardan las recompensas común e individual por agente,
sus componentes híbridos, la distribución de acciones, la entropía de cada
política, la pérdida del actor, el `value loss`, la fracción de actualización
recortada por PPO y la divergencia KL aproximada. Las figuras se generan con:

```powershell
python -m apps.cli.render_marl_learning_figures `
  --matrix-report model-runs/marl_ctde/problem_matrix_20260904/matrix_report.json
```
