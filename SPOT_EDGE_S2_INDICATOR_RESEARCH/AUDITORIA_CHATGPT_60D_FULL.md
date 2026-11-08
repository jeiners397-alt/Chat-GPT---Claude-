# AUDITORÍA INDEPENDIENTE — SPOT EDGE S2 / 60 DÍAS

**Fuente:** artefacto `RESULTADOS_SPOT_EDGE_S2`, GitHub Actions run [#4](https://github.com/jeiners397-alt/Chat-GPT---Claude-/actions/runs/42443550513), ID 42443550513, completado con **success** 2026-11-08 04:05 UTC. Archivo `SUMMARY.json` y los 8 CSV correspondientes; código del commit `dbb8a133...`. Auditoría de ChatGPT, no cambio de resultados originales.

## 1. Cobertura real

- 200 indicadores registrados, **45 implementados** y **155 no ejecutados**.
- 69 símbolos con 4 temporalidades cada uno = 276 registros de cobertura. Cero errores de descarga reportados y cero huecos dentro de los segmentos recibidos.
- 60 días de evaluación, con calentamientos distintos por temporalidad, ejecución ~1.597,5 segundos (26,6 minutos).
- **450 configuraciones** (indicador × temporalidad × horizonte); **427** con alguna operación, **23** sin operación. No representan 450 indicadores independientes.
- Conteos por *configuraciones*: **8 A**, **69 B**, **136 C**, **237 D**. Los **8 A corresponden a solo 7 indicadores distintos**, porque CHOP aparece dos veces.
- Los 155 no implementados tienen motivos: **103 PENDING_NEXT_PHASE**, 24 patrones sin regla, 13 propietarios, 10 relacionales y 5 datos no disponibles. No llamar «imposibles» a los 103 pendientes.
- La selección de universo usa *liquidez actual*, filtro de al menos 2 millones de USDT de volumen en 24h, por lo que puede introducir sesgo de supervivencia / selección retrospectiva. Se incluyeron algunos stablecoins, fiat y tokens no equivalentes a altcoins (por ejemplo USDCUSDT, USD1USDT, RLUSDUSDT, EURUSDT, NVDABUSDT, MSTRBUSDT); segmentarlos antes de conclusiones de crypto Spot.

## 2. Configuraciones categoría A: PROMETEDORAS SOLO EN ESTE HISTÓRICO

| Indicador | TF | Mantener | Trades | Win rate | PF informado | Retorno neto | DD informado | Retorno con costes ×2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Shannon Entropy | 4h | 24h | 36 | 33,33% | 3,6824 | +185,51% | -49,57% | +156,25% |
| Choppiness Index (CHOP) | 1h | 4h | 100 | 33,00% | 2,0757 | +137,82% | -21,17% | +76,13% |
| Mass Index Reversal | 1h | 24h | 34 | 41,18% | 2,5187 | +96,29% | -19,51% | +77,24% |
| Klinger Volume Oscillator | 1d | 24h | 50 | 42,00% | 1,9060 | +62,98% | -26,65% | +40,25% |
| CHOP | 4h | 4h | 38 | 50,00% | 2,2009 | +36,96% | -12,18% | +22,19% |
| DEMA/TEMA Cross | 4h | 24h | 53 | 43,40% | 1,5361 | +30,23% | -18,42% | +11,07% |
| Chande Momentum Oscillator | 4h | 24h | 51 | 47,06% | 1,5233 | +25,61% | -13,39% | +7,78% |
| Kalman Price Smoother | 1d | 24h | 45 | 37,78% | 1,3720 | +17,11% | -22,72% | +2,31% |

Todos los 8 cumplen la comprobación positiva por subperíodos definida por el motor y siguen positivos en la simulación con costes duplicados. **NO** son 8 estrategias rentables independientemente verificadas: fueron identificadas **después de examinar 450 configuraciones sobre los mismos 60 días**. Una segunda ventana *realmente nueva* es imprescindible. Las cifras de DD y PF tienen limitaciones contables detalladas abajo.

**El supuesto «mejor indicador» TRIX en 1d/24h obtiene +294,99%, pero solo 15 operaciones y categoría D_NO_CONCLUYENTE. No utilizarlo como ganador demostrado.**

## 3. Concentración en movimientos extraordinarios

En `INDICATOR_BY_SYMBOL.csv`:
- Shannon Entropy 4h/24h registra **una operación en LSKUSDT con +259,02%**; esa operación representa ~78,3% de la suma de rendimientos positivos por símbolo para esa configuración. Un cálculo mecánico *solo para mostrar sensibilidad* (sin reordenar las demás operaciones) al eliminar el factor de esa única operación haría pasar +185,51% a aproximadamente **-20,48%**. NO es un backtest contrafactual válido porque al omitirla habría habido otras oportunidades y distinto capital.
- TRIX 1d/24h: una operación en ONEUSDT +94,15% y otra en BMTUSDT +67,51% explican gran parte del +294,99% agregado; muestra insuficiente.
- Mass Index 1h/24h tiene contribución concentrada en LSKUSDT (+68,43% acumulado para ese símbolo) y GTCUSDT (+29,89%).
- La API oficial Spot consultada directamente devuelve alzas grandes en esos pares dentro del período. Esto no descarta movimientos puntuales, deslizamiento real ni problemas de ejecución.

Repetir con un análisis robusto *sin el mayor movimiento ganador*, y por separado con límites de liquidez, spreads, tamaño de orden y sensibilidad a prioridad de símbolos.

## 4. Peores configuraciones LONG; candidatos a INVESTIGACIÓN, NO a inversión automática

| Indicador | TF/H | Trades | Retorno | PF informado |
|---|---|---:|---:|---:|
| Kaufman Efficiency Ratio (ER) | 1h/4h | 341 | -88,22% | 0,4735 |
| Stochastic RSI Advanced | 1h/4h | 348 | -83,83% | 0,5214 |
| Taker Buy Ratio Spot | 15m/4h | 359 | -82,70% | 0,5281 |
| OBV Advanced | 15m/4h | 357 | -81,37% | 0,5755 |
| ZLEMA | 15m/4h | 358 | -80,54% | 0,5459 |

Hay **136 configuraciones C**, correspondientes a **42 indicadores únicos**. **117 de 136** C son negativas en ambos subperíodos, aunque eso no acredita una estrategia inversa rentable (Spot LONG-only no permite replicar simplemente un SHORT).

## 5. TOP GAINERS: cifra llamativa pero engañosa si se interpreta como anticipación

El resumen presenta **Shannon Entropy 1d** con **84,21% de precisión: 16 hits de 19 señales**. No es una tasa confirmada de «comprar desde T0».
- La etiqueta se basa en estar dentro del top 10 de **los 69 símbolos de esta muestra**, NO del universo Spot total.
- El detector comprueba pertenencia al top 10 **el mismo día UTC de la señal o hasta el siguiente**; no exige que el movimiento que otorgó la posición de Top Gainer ocurra después de la señal.
- En `topgainers.py`, `hours_before=(day - signal_time)` puede ser **negativo** si la señal aparece después de medianoche del mismo día; por tanto, no mide necesariamente anticipación real.
- La columna `tasa_falsas_alarmas_pct` solo cuenta un subconjunto de falsos positivos (no-Top-Gainer que además cayó), **no** todos los falsos positivos. El 0,00% publicado no significa ausencia de alertas fallidas.
- El clasificador de Top Gainers no guarda cobertura/recall real en el CSV.

Reescribir la etiqueta como incremento futuro después de una entrada observable, e incluir baseline/base rate, tiempo mínimo previo al impulso y sensibilidad por top 5/10 del universo histórico elegible.

## 6. DEFECTOS DEL MOTOR QUE IMPIDEN DECLARAR GANANCIAS FIABLES

**P0. Capital/selección:** `execute_experiment` ordena solo por `entry_time`; para muchas señales simultáneas se elige la que aparezca primero en el orden de los símbolos recuperados, sin regla económica previa. Eso puede determinar si se captura o pierde un «pump». Fijar prioridad causal, documentada, y repetir con prioridad aleatoria determinista para medir estabilidad.

**P0. Drawdown y rentabilidad diaria:** `src/stats.py::_build_equity_curve` construye el patrimonio únicamente con valores **después de cerrar trades**, sin marcar las posiciones abiertas diariamente. Los DD publicados NO son MTM; la rentabilidad diaria promedio usa esta curva de equity solo realizada. Necesitamos ledger cronológico de wallet + posición mark-to-market.

**P0. Profit Factor:** `src/stats.py` divide la suma de `pnl_pct_net` de trades positivos por suma absoluta de los negativos. Esto es PF calculado con **porcentajes de trades**, no con ganancias/pérdidas en USDT de una cuenta que reinvierte todo; puede diferir del PF real de cartera. Calcular también PF monetario con `equity_after-equity_before`.

**P1. Benchmark:** `compute_benchmark_stats` existe e importa en `spot_indicator_research.py`, pero **no se invoca ni exporta** en los resultados recibidos. Falta comparar contra BTC buy-and-hold y 100% USDT en la misma ventana.

**P1. Universo retrospectivo:** `get_24h_tickers` toma la liquidez del día de ejecución y decide qué contratos eran elegibles hace 60 días. Puede omitir activos que eran líquidos antes y favorecer supervivientes; crear selección cronológica con volúmenes observables en t.

**P1. Sesgo de selección / múltiples pruebas:** analizar 450 configuraciones y elegir las 8 positivas en el tramo «comprobación» implica *seleccionar sobre ese tramo* al anunciar ganadores. No es un OOS final nuevo. Exigir validación posterior con parámetros congelados.

**P1. Contaminación de régimen:** `_build_btc_regime_series` calcula EMA con el close del día y clasifica entradas intradía de ese mismo día según ese close; el reporte por régimen usa información posterior (aunque esa etiqueta no participa en entradas del backtest). Usar último día cerrado, no el día de entrada.

**P2. Cobertura y auditabilidad:** cuatro símbolos registran menos de 120 velas 1d totales (AEROUSDT 115, HYPEUSDT 46, RWUSDUSDT 27, 牛来USDT 61). No se exporta un ledger TRADE_BY_TRADE, por lo que no se pueden reproducir completamente los balances ni cuantificar la sensibilidad a operaciones extremas sin re-ejecutar.

## 7. Decisión

**NO abandonar ni operar en real.** Dos acciones siguientes: (1) congelar exactamente las ocho combinaciones A y auditar contrafactuales / contabilidad en los 60 días ya conocidos; (2) ejecutar **período independiente posterior** con selección de pares punto-en-tiempo y spreads más realistas. Para una prueba rápida de robustez priorizar CHOP 4h/4h y CMO 4h/24h por menor DD relativo y menor exposición a una única operación que Shannon Entropy, pero **sin presentarlas como rentables**.

**Estado final:** éxito técnico del pipeline; evidencia exploratoria, no ventaja estadística validada.
