# Cribado de hiperparámetros CTDE

Este experimento compara configuraciones de entrenamiento después de fijar la
estructura de recompensa. Todas las ejecuciones usan los mismos cortes
temporales y se seleccionan exclusivamente con validación. Cada modelo admite
un máximo de 50 iteraciones de ocho episodios y se detiene antes si durante 12
iteraciones consecutivas no mejora la validación. El corte de prueba permanece
sin consultar.

Cada ejecución parte de 1.000 EUR y guarda, para cada iteración, el retorno
del valor de la cartera, el valor final de la cartera, el efectivo disponible,
el beneficio neto obtenido en ventas cerradas, el capital que continúa
invertido y el número de posiciones y operaciones cerradas. El valor final de
la cartera es la métrica de selección. El efectivo disponible se presenta como
complemento porque una parte del capital puede seguir invertida al finalizar un
episodio.

Se estudian la tasa de aprendizaje, el factor de descuento, la entropía de
exploración, el límite PPO y el número de épocas de actualización. Tras el
cribado, las dos configuraciones con mejor validación se repetirán con varias
semillas y un número mayor de episodios antes de realizar una única evaluación
en el conjunto de prueba.
