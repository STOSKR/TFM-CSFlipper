# ADR 0004: Entrenamiento Steam y BUFF como Entrada Viva de Flip

## Estado

Aceptada.

## Contexto

El proyecto empezo con una linea experimental Steam/BUFF basada en historico alineado entre
plataformas. Esa aproximacion permitio construir `trading_profit_v1`, probar el simulador y
conectar el entorno multiagente, pero tambien mostro dos limitaciones:

- el historico Steam/BUFF alineado genera pocos positivos en validacion y test;
- la captura recurrente de BUFF aumenta fragilidad operativa y riesgo de restricciones de cuenta.

La duda metodologica no es eliminar BUFF, sino separar su papel. Steam tiene mas historico
temporal y es mejor fuente de entrenamiento. BUFF sigue siendo util como precio vivo de entrada
cuando se evalua un flip concreto.

## Decision

El entrenamiento principal se hara con datos historicos de Steam. El modelo estimara riesgo y
retorno de salida en Steam a un horizonte de ocho dias, no precio exacto de BUFF.

BUFF se usara en inferencia como cotizacion puntual de entrada para calcular si un candidato
BUFF -> Steam conserva margen despues de comisiones, trade hold y riesgo de salida. Si no hay
precio BUFF vivo, el candidato queda en observacion por `missing_entry_price`; no se considera
un fallo del modelo Steam.

## Consecuencias

- Se conserva el trabajo Steam/BUFF como antecedente experimental trazable.
- Se reduce la dependencia de scraping recurrente de BUFF para entrenamiento.
- La recomendacion operativa se formula como `review`, `observe` o `blocked`, con probabilidad de
  salida segura y retorno esperado.
- BUFF puede reincorporarse mas adelante como fuente de validacion puntual, scraping limitado o
  ejecucion simulada de flips.
