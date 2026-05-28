# ADR 0001: Monorepo Modular con Supabase/Postgres

## Estado

Aceptada.

## Contexto

El proyecto combina adquisición, OCR, predicción, simulación y coordinación multiagente. Estas piezas comparten contratos, entidades, tests y reglas de negocio.

## Decisión

Usar un monorepo modular y Supabase/Postgres como persistencia preferente.

## Consecuencias

- Refactors más simples entre capas.
- Contratos compartidos sin duplicación.
- Auditoría fuerte de predicciones, votos y decisiones.
- Menos coste operativo que un multirepo durante el TFM.

