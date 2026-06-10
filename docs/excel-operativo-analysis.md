# Analisis del Excel operativo Steam-Buff

## Archivo revisado

- Fuente: `material_a_integrar/009-analizar-excel-operativo-y-migrar-formulas/Calculos steam buff.xlsm`
- Tipo: `.xlsm` con macros.
- Estado de macros: no ejecutadas. La revision se hizo leyendo el contenido Open XML del libro.
- Hojas detectadas: `Trades`, `Pagos`, `Calculadora`, `Historial de compras`, `Calculadora (2)`, `Fees`, `Buy Orders`, `TradeUps`, `Calendario`.
- Tablas detectadas: `Tabla2`, `Tabla3`, `Historial`, `Tabla35`.
- Enlaces externos: existe un enlace externo residual a `Calendario`.

## Lectura general

El Excel mezcla tres tipos de informacion:

- Registro operativo de compras, ventas, pagos y saldos.
- Formulas economicas reutilizables: conversion EUR/CNY, fees por plataforma, profit, porcentaje y capital bloqueado.
- Vistas auxiliares: calendario de liberacion, calculadoras manuales y buy orders.

Para el TFM conviene migrar primero las reglas economicas y dejar las vistas como derivadas.

## Hojas relevantes

### Historial de compras

Es la hoja mas importante para modelar posiciones. Contiene una tabla `Historial` en `B1:U276` con columnas:

- `Nombre Articulo`
- `Calidad`
- `ST`
- `Fecha C`
- `No vendida`
- `Plataforma C`
- `Precio C`
- `Divisa C`
- `Precio CE`
- `Precio CY`
- `Fecha V`
- `Columna1`
- `Precio V`
- `Divisa V`
- `Precio VE`
- `Precio VY`
- `Profit`
- `Porcentaje`
- `Fecha desbloqueo`

Formulas clave:

```text
No vendida =
IF(Fecha desbloqueo > TODAY(), 0, IF(Fecha V <> "", 0, 1))

Divisa C =
IF(Plataforma C = "BUFF", "CNY", "EUR")

Precio CE =
IF(Divisa C = "EUR", Precio C, Precio C / 8)

Precio CY =
IF(Divisa C = "CNY", Precio C, Precio C * 8)

Plataforma venta esperada =
IF(Plataforma C = "-", "-", IF(Plataforma C = "BUFF", "STEAM", "BUFF"))

Divisa V =
IF(Plataforma venta esperada = "BUFF", "CNY", "EUR")

Precio VE =
IF(Divisa V = "EUR", Precio V, Precio V / 8)
* IF(Plataforma venta esperada = "STEAM", 1, IF(Plataforma venta esperada = "BUFF", 0.975, 1))

Precio VY =
IF(Divisa V = "CNY", Precio V, Precio V * 8)
* IF(Plataforma venta esperada = "STEAM", 1, IF(Plataforma venta esperada = "BUFF", 0.975, 1))

Profit =
IF(No vendida = 1 OR Fecha desbloqueo > TODAY(), 0, Precio VE - Precio CE)

Porcentaje =
IF(Precio CE = 0 AND Profit = 0, 0, Profit / Precio CE)

Fecha desbloqueo =
Fecha C + 8
```

Interpretacion:

- La compra en BUFF se trata como CNY y se convierte a EUR dividiendo por un tipo de cambio fijo.
- La venta en BUFF aplica fee neto de `0.975`.
- Steam cobra una comision de `0.87`.
- Sacar saldo de Steam a banco aplica una perdida adicional asumida del 20% en el escenario conservador. Se conservan escenarios de referencia del 10%, 15% y 20%.
- El trade hold se modela como `Fecha C + 8`: compra + 7 dias + X horas hasta la siguiente ventana de desbloqueo de las 09:00.

### Pagos

Es un ledger operativo mas flexible que mezcla pagos, compras y ventas con codigos de transaccion.

Columnas relevantes:

- `Fecha`
- `Persona`
- `Calidad`
- `ST`
- `Nombre Articulo`
- `Transaccion`
- `Precio`
- `PrecioReal`
- `Fecha`
- `Fecha desbloqueo`
- `Plataforma`
- `Profit`
- `isSold`
- `%`
- `NO SUMAR`
- `Items en espera`
- `Saldo en espera`

Codigos observados:

- `CR`: compra en BUFF.
- `CL`: compra en Steam.
- `VR`: venta en BUFF.
- `VL`: venta en Steam.

Formulas clave:

```text
PrecioReal =
IF(Plataforma = "BUFF", Precio / Currency,
  IF(Plataforma = "STEAM" AND Transaccion empieza por "V", Precio * 0.8, Precio)
)

Fecha desbloqueo =
IF(Transaccion empieza por "C", Fecha + 8, "")

isSold / posicion acumulada =
SUMPRODUCT(
  mismo ST,
  misma calidad,
  mismo nombre,
  compras CR/CL - ventas VL/VR
)

Profit de venta =
IF(
  Transaccion empieza por "V",
  PrecioReal - XLOOKUP(ultima compra abierta equivalente),
  0
)

Porcentaje =
IF(ratio = 0, 0, (PrecioReal / precio_compra_equivalente - 1) * 100)

NO SUMAR =
IF(venta en BUFF y existe compra Steam del mismo articulo, 1, 0)

Items en espera STEAM =
0.8 * SUMIFS(PrecioReal, Fecha desbloqueo >= TODAY(), Transaccion in CL/CR, Plataforma = STEAM)

Items en espera BUFF/etc. =
SUMIFS(PrecioReal, Fecha desbloqueo >= TODAY(), Transaccion in CL/CR, Plataforma = plataforma)
```

Interpretacion:

- `Pagos` resuelve matching entre compras y ventas con `XLOOKUP` hacia atras usando item, calidad, ST y contador acumulado.
- Aplica un factor `0.8` a ventas o saldos Steam para reflejar la perdida conservadora al sacar saldo Steam a banco.
- Tiene formulas con rangos amplios y algunos hardcodes de filas/personas/saldos, por lo que conviene migrar la logica y no la estructura exacta.

### Calculadora y Calculadora (2)

Son calculadoras manuales de margen con fees.

Constantes detectadas:

```text
Steam venta 0,9 = 0.87 * 0.9
Steam venta 0,8 = 0.87 * 0.8
BUFF = 0.975
```

Conversiones observadas:

```text
BUFF EUR = BUFF CNY / 8.1
BUFF EUR = BUFF CNY / 8.25
```

Formula de margen:

```text
Ganancia = precio_venta * fee_factor
Porcentaje = (Ganancia / precio_compra - 1) * 100
```

Interpretacion:

- Las calculadoras son utiles para extraer constantes iniciales de fees.
- CSFloat y Skinport aparecen como referencia historica, pero quedan fuera del dominio principal del TFM.
- Los tipos de cambio estan hardcodeados y cambian entre hojas (`8`, `8.1`, `8.25`, `D28`, `D35`). En el sistema deben ser parametros versionados por fecha.

### Buy Orders

Lista operativa de candidatos con enlaces BUFF y una mini calculadora de margen minimo.

Formulas clave:

```text
Variable costes = 0.87 * 0.8
Minimo venta = Precio compra / Variable costes
Margen actual = (Precio venta actual - Precio compra) / Precio compra
Margen minimo = (Minimo venta - Precio compra) / Precio compra
Margen restante = (Precio venta actual * Variable costes - Precio compra) / Precio compra
```

Interpretacion:

- Sirve como especificacion de margen neto minimo para comprar.
- Debe migrarse a una funcion reusable de profit/margen neto.

### Calendario

Vista visual derivada para fechas de desbloqueo. Tiene muchas formulas de calendario y nombres definidos.

Interpretacion:

- No debe migrarse como logica principal.
- En el sistema puede reconstruirse desde posiciones con `unlock_at` y una vista web/calendario.

### Trades y TradeUps

- `Trades` parece una simulacion simple de semanas con compra/venta y multiplicadores.
- `TradeUps` contiene datos auxiliares de floats/rangos y enlaces/scripts.

Interpretacion:

- No son prioritarias para el dataset supervisado.
- Pueden revisarse despues si el TFM incorpora trade-ups o escenarios de sensibilidad.

## Reglas a migrar primero

1. Conversion de moneda.

```python
price_eur = price if currency == "EUR" else price / fx_cny_per_eur
price_cny = price if currency == "CNY" else price * fx_cny_per_eur
```

2. Fee neto por plataforma.

```python
net_sale = gross_sale * fee_factor[platform]
```

Valores iniciales extraidos:

```text
STEAM_SALE_FEE: 0.87
STEAM_CASHOUT_LOSS_CONSERVATIVE: 20%
STEAM_CASHOUT_LOSS_REFERENCE: 10%, 15%, 20%
STEAM_TO_BANK_CONSERVATIVE: 0.87 * 0.8 = 0.696
STEAM_TO_BANK_MEDIUM: 0.87 * 0.85 = 0.7395
STEAM_TO_BANK_OPTIMISTIC: 0.87 * 0.9 = 0.783
BUFF: 0.975
```

3. Fecha de desbloqueo.

```python
unlock_at = bought_at + trade_hold_days
```

Para el TFM se usara `trade_hold_days = 8` como simplificacion conservadora.

4. Profit realizado.

```python
realized_profit_eur = net_sale_eur - buy_price_eur
```

5. Rentabilidad porcentual.

```python
return_pct = realized_profit_eur / buy_price_eur
```

6. Estado de posicion.

```python
is_open = sold_at is None and unlock_at <= today
is_locked = sold_at is None and unlock_at > today
```

7. Capital bloqueado.

```python
locked_capital = sum(position.buy_price_eur for position in positions if position.unlock_at >= today)
```

El Excel aplica factor `0.8` a parte del saldo Steam; esto se modela como perdida de cash-out, no como precio original del mercado.

## Encaje con el TFM

### Funcionalidades web derivadas

Varias pestañas del Excel deben considerarse especificación funcional para la web futura:

- `Historial de compras`: historial de artículos comprados/vendidos, estado de posición, profit y porcentaje.
- `Calendario`: calendario visual de desbloqueo/liberación.
- `Pagos`: dinero ingresado por persona, saldos, movimientos, capital en espera y profit agregado.
- `Calculadora` y `Calculadora (2)`: calculadora de rentabilidad Steam-BUFF.
- `Buy Orders`: seguimiento de candidatos, precio de compra, precio de venta actual, margen mínimo y margen restante.

Estas vistas deben reconstruirse desde datos normalizados, no copiando la estructura exacta del Excel.

### Dataset supervisado

Usar las formulas migradas para construir el target:

```text
spread_profitable_8d = 1 si el spread neto tras fees, cambio y trade hold sigue siendo rentable en horizonte simplificado de 8 dias.
```

Features candidatas desde el Excel:

- precio Steam neto;
- precio BUFF neto;
- spread bruto;
- spread neto;
- plataforma de compra;
- plataforma de venta esperada;
- fee aplicado;
- moneda y tipo de cambio;
- volumen/buy orders cuando existan;
- dias hasta desbloqueo si se simula una posicion.

### Simulador

Migrar:

- posiciones abiertas/cerradas;
- fecha de compra;
- fecha de desbloqueo;
- precio de compra neto;
- precio de venta neto;
- profit realizado;
- capital bloqueado;
- valor efectivo del saldo Steam.

### MARL

El Excel no define agentes MARL, pero si aporta:

- funcion economica base de recompensa;
- penalizacion/estado de capital bloqueado;
- restricciones iniciales de liquidez y exposicion;
- labels para evaluar si una decision habria sido rentable.

## Riesgos detectados

- Tipos de cambio hardcodeados en varias celdas (`8`, `8.1`, `8.25`, `D28`, `D35`).
- Fees de Steam representados en varias capas: fee de mercado `0.87` y cash-out `0.8`, `0.85` o `0.9`.
- `Fecha desbloqueo = Fecha C + 8` se adopta como simplificacion conservadora del horizonte.
- `Pagos` mezcla ledger, calculadora, saldos por persona y formulas de matching; no debe migrarse como tabla unica.
- Hay formulas con `XLOOKUP`, por lo que la logica de matching debe reimplementarse explicitamente en Python.
- Hay un enlace externo residual a `Calendario`.

## Propuesta de migracion

1. Crear un modulo de formulas economicas puras en `packages/simulation/` o `packages/domain/`.
2. Crear tests con ejemplos del Excel: compra BUFF -> venta Steam, compra Steam -> venta BUFF, venta bloqueada, posicion abierta y capital bloqueado.
3. Crear tabla/configuracion versionada de fees y FX.
4. Crear un importador opcional del historial Excel a entidades de posiciones, sin depender de macros.
5. Usar las formulas migradas para etiquetar el dataset supervisado y calcular recompensa MARL.

## Preguntas abiertas

- Definir si el escenario de salida Steam por defecto seguira siendo siempre 20% o si se expondra en configuracion de usuario.
- Confirmar si el tipo de cambio debe venir de fuente externa, tabla manual versionada o configuracion fija por experimento.
