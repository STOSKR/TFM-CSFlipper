# Modelar rutas de compra, venta y cashflow

## Objetivo

Definir e implementar el contrato de oportunidades como rutas completas de trading: plataforma de compra, tipo de entrada, plataforma de salida, precio neto esperado, liquidez, `trade hold` y destino del saldo.

## Contexto

El objetivo operativo no es comprar siempre desde una plataforma fija. La estrategia real busca meter capital, comprar lo mas barato posible, vender lo mas caro posible y decidir si el dinero generado se reinvierte o se extrae.

## Alcance

- Modelar rutas como `BUFF listing -> Steam listing`, `BUFF listing -> Steam buy order`,
  `BUFF buy order -> Steam listing`, `BUFF buy order -> Steam buy order` y sus equivalentes
  plataforma/Steam cuando sean utiles.
- Distinguir precio normal/listing, buy order/oferta, ultima venta y precio neto de salida.
- Incluir plataforma de compra en el entorno MARL y en los datasets.
- Incluir plataforma/tipo de salida esperada antes de entrenar MAPPO.
- Representar valor efectivo del saldo resultante: reinversion en BUFF/Steam o cash-out.
- Revisar acciones de Trader para que no sean solo `hold`/`buy_one` si el entrenamiento necesita decidir ruta o salida.
- Ejecutar el scraping periodico con los perfiles SteamDT activos: normalmente `steam_sell_slow`
  y `platform_arbitrage_safe`.
- Mantener modo simulado; no ejecutar compras reales.

## Criterios de aceptacion

- Cada ejemplo de trading identifica plataforma y tipo de precio de entrada.
- Cada ejemplo identifica salida esperada y neto tras comisiones.
- La observacion MARL distingue entrada normal frente a entrada por buy order.
- La observacion MARL distingue salida normal/listing frente a venta directa contra buy order.
- El entorno MARL no hardcodea la compra en Steam.
- La observacion informa al menos la plataforma de entrada.
- Queda decidido si la seleccion de ruta la hace el dataset/candidato o la politica Trader.

## Decisiones tecnicas

- Empezar por rutas candidatas preconstruidas en el dataset. El agente decide comprar o no comprar esa ruta.
- Pasar a acciones de ruta solo si hay suficientes datos y variedad para aprenderlas.

## Pasos realizados

- Detectado que el entorno compraba siempre como `STEAM`.
- Anadido soporte inicial de `buy_platform` al `MarketEpisodeStep`.
- Anadido soporte inicial de `buy_price_type`, `sell_platform` y `sell_price_type` al
  `MarketEpisodeStep`.
- Activado `run_all_profiles = true` en `csflipper_config.toml` con `enabled_profiles` limitado
  a `steam_sell_slow` y `platform_arbitrage_safe`.
- Anadido override `--all-profiles/--no-all-profiles` a `scrape_flow.py`.

## Pruebas ejecutadas

- Pendiente tras implementar el contrato completo.

## Bloqueos o riesgos

- Sin precios de listing/venta de BUFF, la ruta natural `BUFF -> Steam` queda incompleta.
- Entrenar `022` antes de cerrar este contrato puede producir politicas sesgadas por una ruta incorrecta.
