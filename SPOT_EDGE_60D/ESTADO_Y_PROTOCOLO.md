# SPOT EDGE — Plan verificable de 60 días (2026-09-08 a 2026-11-06 UTC)

Repositorio compartido ChatGPT / Claude. Este archivo fue creado mediante el conector GitHub de ChatGPT para comprobar permisos de lectura y escritura.

## Objetivo
Evaluar todos los 200 nombres de estrategias, 200 indicadores y 36 hipótesis adicionales del catálogo, SIN confundir el catálogo con implementaciones. Solo las estrategias con fórmula causal ejecutable y datos disponibles se podrán backtestear; las demás deben permanecer en el registro con motivos: NOT_IMPLEMENTED, PROPRIETARY, NEEDS_L2_HISTORY, INCOMPATIBLE_SPOT, INSUFFICIENT_WARMUP o DATA_MISSING.

## Período
- Ventana de evaluación: **2026-09-08T00:00:00Z <= t < 2026-11-07T00:00:00Z** (60 días completos).
- Train 30d / Validación 15d / Test sellado 15d; si las estrategias se escogieron usando esta ventana, reportar TEST como seleccionado/contaminado, NO como OOS independiente.
- Descargar barras de calentamiento previas si los indicadores lo requieren (EMA200/Donchian55); no contabilizar warmup como rendimiento de esos 60 días.
- Universo: Binance Spot USDT, detectar listados/deslistados y registrar supervivencia.
- Las reglas deben utilizar SOLO velas cerradas y ejecutarse en la siguiente apertura / evento posterior observable.

## Dos brazos ficticios independientes por cada estrategia
A: 100 USDT; sin stop; cierre solo con beneficio neto, en ventana 07:00-21:00 America/Lima; pérdidas latentes SIEMPRE en patrimonio. No declarar 100% de aciertos como prueba de rentabilidad.
B: 100 USDT; stop estructural debajo de soporte/invalidez, TP de acuerdo con regla; costes y deslizamiento; no permitir saldo negativo.
Cuenta agregada **por estrategia** sobre el universo; NO reponer 100 USDT por cada símbolo ni sumar balances incompatibles.

## Indicadores + modelos
Documentar para cada uno: formula, timeframe, dependencia, versión, estado de implementación. OHLCV permite EMA, RSI, ATR, Donchian, BB/Keltner, RVOL, OBV, CMF y taker-buy-ratio de klines. Un book snapshot actual NO recrea libro histórico.
Las estrategias nuevas se versionan por hash, registrando pruebas perdedoras y duplicados.

## Métricas obligatorias
Equity MTM diario, net PnL, ret% diario aritmético y compuesto, Win Rate con n, PF con n, max DD MTM, exposición, capital bloqueado, turnover, comisiones, Sharpe con cautela, retornos por régimen, por activo y timeframe, y benchmarks BTC Buy-and-Hold + 100% USDT. Marcar métricas indefinidas como N/A, nunca infinito como éxito automático.

## Fuentes de investigación (contexto, no garantía)
- https://academic.oup.com/raps/advance-article-abstract/doi/10.1093/rapstu/raag011/8914819
- https://www.sciencedirect.com/science/article/pii/S0264999323001359
- https://www.sciencedirect.com/science/article/pii/S1042443122000816
- https://www.sciencedirect.com/science/article/pii/S1544612320304414
- https://developers.binance.me/en/docs/products/spot/faqs/market_data_only
- https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/binance-crypto-price-data

## Restricciones
No órdenes reales, no promesas de estrategias necesariamente rentables, no profit diarios inventados, ni optimización con TEST. Ranking inicial = **prioridad heurística de investigación, no ranking de ganancias**.
