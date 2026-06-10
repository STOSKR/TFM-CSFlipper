# Implementar pipeline de inferencia productivo MARL

## Objetivo

Implementar el pipeline de inferencia productivo completo: extractor de datos en tiempo real -> modelo supervisado en inferencia -> agentes MARL en ejecucion descentralizada -> capa de ejecucion de ordenes.

## Contexto

La arquitectura final separa entrenamiento y produccion. En produccion, el sistema carga artefactos ya entrenados y ejecuta actores locales sin critico centralizado.

## Alcance

- Consumir datos recientes desde scrapers, streaming o persistencia.
- Construir features productivas compatibles con el entrenamiento supervisado.
- Ejecutar el modelo supervisado serializado en modo inferencia.
- Construir observaciones locales para Scout, Trader y Portfolio.
- Restaurar politicas entrenadas y ejecutar actores descentralizados.
- Agregar acciones en una decision operativa coherente.
- Implementar capa de ejecucion de ordenes en modo simulado/paper trading por defecto.
- Persistir predicciones, acciones, decisiones, errores y trazabilidad.

## Criterios de aceptacion

- El pipeline corre sin acceder a datos de entrenamiento ni recalibrar modelos.
- Las politicas MARL restauradas generan acciones a partir de observaciones locales.
- La capa de ordenes no ejecuta compras reales por defecto.
- Cada decision queda trazada con versiones de modelo supervisado, checkpoint MARL y features.
- Hay un modo dry-run reproducible para validar extremo a extremo.

## Decisiones tecnicas

- Ejecucion descentralizada por actor local en inferencia.
- La ejecucion real de ordenes queda bloqueada hasta decision explicita fuera de esta tarea.
- El antiguo Broker/FIPA se sustituye por la coordinacion de acciones derivada de politicas MARL.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Hay que definir contratos claros entre acciones MARL y ordenes simuladas.
- La ejecucion real exige controles adicionales de seguridad, credenciales y cumplimiento.

