# Comparación finalista con validación fija

Las ejecuciones anteriores se usaron para detectar configuraciones candidatas,
pero cada semilla seleccionaba ventanas de validación distintas. Esta fase
corrige ese factor: las diez ejecuciones comparten exactamente las mismas
ventanas de validación y solo cambia la inicialización aleatoria del
entrenamiento.

Se comparan la configuración base y una tasa de aprendizaje de 0,00010 con
cinco semillas por configuración. Todas usan como máximo 50 iteraciones de
ocho episodios y parada temprana con paciencia 12. El conjunto de prueba no se
consulta. La configuración se elegirá comparando la media, la dispersión, el
valor final de cartera y el número de operaciones cerradas.
