# Automatizar registro de compras desde correo

## Objetivo

Leer automaticamente los correos de confirmacion de compra para registrar articulos comprados, precio de compra y fechas en las que se liberan para poder venderlos.

## Contexto

El flujo futuro no solo debe recomendar compras, tambien debe llevar control de posiciones reales. Al comprar un articulo, llega un correo que puede servir como fuente de verdad para registrar la operacion sin introducirla a mano.

## Alcance

- Identificar proveedor de correo y formato de los emails de compra.
- Extraer articulo comprado, calidad, StatTrak, precio, moneda, fecha de compra y plataforma.
- Calcular fecha de liberacion para venta segun trade hold aplicable.
- Guardar compras en una tabla de posiciones/compras reales.
- Marcar estado de cada compra: bloqueada, vendible, vendida, error de parseo.
- Evitar duplicados si el mismo correo se procesa varias veces.
- Registrar el contenido minimo necesario para auditar errores sin almacenar datos personales innecesarios.

## Criterios de aceptacion

- Un correo de compra valido crea o actualiza una compra registrada.
- La fecha de liberacion queda calculada y visible.
- Los emails ya procesados no generan duplicados.
- Los errores de parseo quedan registrados con motivo.
- El flujo puede ejecutarse manualmente al principio y automatizarse despues.

## Decisiones tecnicas

- Crear una tabla separada para compras reales, distinta de `market_snapshots`.
- Usar una clave de deduplicacion basada en identificador del email o hash del contenido relevante.
- Empezar con importacion manual/exportada si la conexion directa al correo retrasa demasiado la fase inicial.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Necesitamos ejemplos reales de correo para definir el parser.
- La integracion con email requiere manejar credenciales con cuidado.
- Confirmar la regla exacta de trade hold y si varia por plataforma o tipo de item.
