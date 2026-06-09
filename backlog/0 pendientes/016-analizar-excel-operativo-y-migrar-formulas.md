# Analizar Excel operativo y migrar formulas

## Objetivo

Revisar el Excel actual que calcula oportunidades, rentabilidad y seguimiento de compras para migrar sus formulas utiles al sistema.

## Contexto

El Excel ya resuelve parte del flujo manual: calculos, formulas y seguimiento operativo. Antes de reimplementar margen, confianza o rentabilidad, conviene entender que formulas funcionan, cuales fallan y que datos usa cada una.

## Alcance

- Inventariar hojas, columnas y formulas relevantes.
- Identificar inputs necesarios: precios, comisiones, historico, buy orders, fechas y cantidades.
- Separar formulas de rentabilidad, seguimiento de compras y prediccion.
- Documentar formulas actuales y supuestos.
- Comparar formulas actuales con la nueva estructura de datos.
- Proponer que formulas se migran tal cual, cuales se ajustan y cuales se descartan.
- Crear tests con ejemplos del Excel para validar los calculos migrados.

## Criterios de aceptacion

- Existe un documento o modulo con las formulas relevantes explicadas.
- Cada formula migrada tiene al menos un caso de prueba basado en el Excel.
- Queda claro que datos de Supabase necesita cada calculo.
- La formula de margen/rentabilidad queda versionada para poder mejorarla despues.

## Decisiones tecnicas

- No mezclar formulas operativas con scraping.
- Mantener formulas de decision en un modulo propio, reutilizable por backend y web.
- Usar el Excel como especificacion inicial, no como fuente permanente de verdad.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Necesitamos el archivo Excel y una explicacion breve de que columnas consideras fiables.
- Algunas formulas pueden depender de datos manuales que todavia no existen en Supabase.
