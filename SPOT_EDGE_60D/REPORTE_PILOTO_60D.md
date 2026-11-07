# Primeros resultados Spot 60 días — cribado, NO validación

Fecha 2026-11-07. Binance Spot público. Ventana de 60d completos: 2026-09-08T00:00Z a 2026-11-07T00:00Z (exclusivo). Warmup 2026-07-25 a 09-08. Precio 4h de 10 pares: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, LINKUSDT, NEARUSDT, ADAUSDT, AVAXUSDT.

**VEREDICTO:** 8 reglas núcleo × 2 brazos = 16 carteras, **16/16 pérdidas** después de coste. A = sin SL, cerrar ganancia neta solamente en 07–21 America/Lima. B = stop estructural/ATR, TP 2,5R. $100 iniciales por cartera; 3 slots; fee 0,10% cada lado + slip 0,05% cada lado. Entradas en la apertura siguiente al cierre de señal. Backtest simplificado; no inferir probabilidad de éxito futuro.

| Regla núcleo | A 60d | B 60d | PF B | Max DD B |
|---|---:|---:|---:|---:|
| DONCHIAN20_RVOL | -6.63% | -5.92% | 0.43 | -8.38% |
| RANGE_SQUEEZE_RVOL | -9.08% | -6.86% | 0.27 | -7.95% |
| EMA_CROSS_TREND | -7.03% | -3.10% | 0.45 | -4.16% |
| EMA_PULLBACK | -4.95% | -2.72% | 0.74 | -7.82% |
| SWEEP_RECLAIM | -6.14% | -1.48% | 0.81 | -5.68% |
| RSI_RECOVERY | -5.19% | -4.88% | 0.53 | -8.98% |
| MOMENTUM_T0 (4h proxy) | -7.83% | -1.10% | 0.80 | -4.09% |
| RANGE_BREAKOUT | -8.48% | -5.87% | 0.27 | -6.67% |

**Métrica engañosa:** A presenta 100% Win Rate entre cierres, pero todas las 8 cuentas A perdieron por posiciones abiertas perdedoras; el retorno de patrimonio sí incluye MTM. Por tanto **no repetir la promesa de que no usar SL asegura ganancias**.

**Limitaciones:** 10 símbolos no representan universo Spot; estrategias variantes de familias más amplias; costes y stop modelados, no replicación de exchange; período ya explorado, no OOS; 4h NO valida T0 de 1m; no histórico order book; tests de estrategias exactas 200/200 todavía pendientes.

Archivo estructurado con todas las métricas en [PILOTO_60D_10_PARES_8_NUCLEOS.json](./PILOTO_60D_10_PARES_8_NUCLEOS.json).

El ranking de 200 estrategias e indicadores, extras y propuestas nuevas están en este directorio como CSVs. Son **prioridades de investigación**, no órdenes empíricos de rendimiento. Hasta backtest real de cada fórmula no existe ranking objetivo de ganancia.

Fuentes:
https://academic.oup.com/raps/advance-article-abstract/doi/10.1093/rapstu/raag011/8914819
https://www.sciencedirect.com/science/article/pii/S1042443122000816
https://www.sciencedirect.com/science/article/pii/S1544612320304414
