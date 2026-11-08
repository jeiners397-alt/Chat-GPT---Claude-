# SPOT EDGE S2 — Investigador Cuantitativo de Indicadores (Binance Spot)

Motor de investigación estadística de indicadores técnicos LONG-only para
Binance Spot. Evalúa, con datos reales de la API pública de Binance, si las
señales de cada indicador tienen expectativa matemática positiva después de
costes, y produce una clasificación reproducible (A-E).

**No ejecuta órdenes reales. No usa apalancamiento. No invierte señales
automáticamente.** Es un analizador estadístico, no un bot de trading.

## Alcance honesto de la Fase 1

El catálogo (`CATALOGO_INDICADORES_200.json`) tiene 200 indicadores,
suministrados por el usuario sin verificación previa de que todos tengan una
fórmula pública reproducible. Este motor:

- **Implementa y evalúa con backtest real 45 indicadores** con fórmula
  pública verificable, usando sólo datos disponibles vía klines de Binance
  Spot (OHLCV + `taker_buy_base_volume`). Cada uno está documentado en
  `src/indicators/registry.py` con sus 10 campos (fórmula, parámetros,
  temporalidad, datos requeridos, señal LONG, condición de salida, estado,
  fuente técnica, limitaciones).
- **Clasifica honestamente los 155 restantes** en `UNTESTED_INDICATORS.csv`,
  con un motivo concreto asignado por una regla explícita y documentada (no
  una opinión improvisada indicador por indicador):
  - `NOT_EVALUABLE_PROPRIETARY`: scripts/visualizaciones propietarias (p. ej.
    LuxAlgo, "Market Cipher clone") sin fórmula matemática pública única.
  - `NOT_EVALUABLE_DATA`: requieren order book, interés abierto de futuros o
    datos on-chain/de wallets, no disponibles vía klines públicos de Spot.
  - `NOT_EVALUABLE_RELATIONAL`: métricas relacionales/de desempeño (Sharpe,
    correlaciones, co-integración) que no definen por sí solas una regla de
    entrada LONG sin una regla adicional no especificada por el usuario.
  - `NOT_EVALUABLE_PATTERN`: reconocimiento de patrones geométricos
    (hombro-cabeza-hombro, cuñas, Gann, armónicos, etc.) sin una única regla
    algorítmica objetiva y ampliamente aceptada.
  - `PENDING_NEXT_PHASE`: fórmula identificable y datos disponibles en
    principio, pero no priorizado en este primer motor. Candidatos
    explícitos para una Fase 2.

**No se inventaron implementaciones "equivalentes" para completar
artificialmente los 200** (instrucción explícita del encargo, sección 3).

## Cómo correr

### Windows (local)

```
run_windows.bat
```

Crea un entorno virtual, instala dependencias y corre el experimento
principal (60 días). Para ampliar a 180 días:

```
run_windows.bat --lookback-days 180
```

### Línea de comandos (cualquier plataforma)

```bash
pip install -r requirements.txt
python spot_indicator_research.py --lookback-days 60
```

Opciones relevantes:

| Flag | Descripción |
|---|---|
| `--lookback-days` | 60 (principal) o 180 (ampliado) |
| `--max-symbols` | 0 = universo completo. Usar un número bajo para pruebas rápidas |
| `--timeframes` | Subconjunto de `15m,1h,4h,1d` |
| `--symbols` | Fuerza una lista de símbolos (pruebas/depuración) |
| `--max-runtime-minutes` | Si se excede, guarda resultados parciales y marca la ejecución como incompleta |
| `--no-commission-sensitivity` | Omite la segunda pasada con comisiones x2 |

### GitHub Actions

El workflow `.github/workflows/spot_indicator_research.yml` permite ejecutar
el análisis manualmente desde la pestaña "Actions" del repositorio
(`workflow_dispatch`), con `lookback_days`, `max_symbols` y
`max_runtime_minutes` configurables. Los resultados se publican como
artefacto descargable (`RESULTADOS_SPOT_EDGE_S2`).

## Metodología (resumen)

- **Universo**: todos los pares `*/USDT` Spot elegibles (TRADING,
  `isSpotTradingAllowed`), excluyendo tokens apalancados y pares con
  liquidez insuficiente (umbral documentado en `config.py`). Todas las
  exclusiones quedan registradas, no sólo las admitidas.
- **Datos**: klines consultados vía `https://data-api.binance.vision`,
  paginados y procesados en memoria. Nada se descarga a disco; sólo se
  guardan los resultados estadísticos finales.
- **Sin look-ahead**: la señal se calcula con el cierre de la vela `t`; la
  entrada se simula en la apertura de `t+1`; la salida, en la apertura de
  `t+1+horizonte`.
- **Capital compartido**: cada experimento (indicador × temporalidad ×
  horizonte) es UNA cuenta de 100 USDT compartida entre todos los símbolos,
  procesados en orden cronológico real. Una señal que llega con la posición
  ya abierta se cuenta como señal pero no como operación ejecutada.
- **Exploración vs. comprobación**: el período se divide cronológicamente
  (ver `config.EXPLORATION_FRACTION`); un indicador sólo puede clasificarse
  como Categoría A si es positivo en AMBOS tramos (control de sobreajuste).
- **Sensibilidad a comisiones**: se corre una segunda pasada con comisión y
  slippage duplicados.
- **Clasificación A-E**: umbrales congelados en `config.py` ANTES de
  ejecutar, no ajustados después de ver resultados.

### Decisiones de diseño documentadas (limitaciones conocidas)

- El capital compartido se ejecuta en orden cronológico global por
  experimento; no hay gestión de múltiples posiciones simultáneas (una
  posición abierta bloquea nuevas entradas hasta cerrarse).
- El "Top Gainer" del día se define como estar entre los N (`config.TOP_GAINERS_N`)
  símbolos con mayor variación porcentual diaria dentro del universo evaluado
  ese día — no es una fuente externa de ranking de mercado completo.
  Se usa únicamente como etiqueta posterior, nunca para decidir entradas.
  El régimen de mercado en `INDICATOR_BY_REGIME.csv` se define de forma
  simple (EMA20 vs EMA50 de BTC/USDT diario); es una aproximación razonable,
  no una taxonomía de régimen validada académicamente.
- Varios indicadores "compuestos" (Hurst, Entropía de Shannon, ADF, Kaufman
  ER, Choppiness Index) no producen dirección por sí solos; se combinaron
  con una regla adicional (cruce de medias, ruptura de Donchian) para
  convertirlos en una señal LONG comparable. Esa combinación está declarada
  explícitamente en su ficha, no oculta.

## Resultados generados (`RESULTADOS_SPOT_EDGE_S2/`)

| Archivo | Contenido |
|---|---|
| `INDICATOR_RANKING.csv` | Clasificación completa ordenada por rentabilidad neta |
| `INDICATOR_METRICS.csv` | Resultados por indicador, temporalidad y horizonte |
| `INDICATOR_BY_SYMBOL.csv` | Rendimiento por criptomoneda |
| `INDICATOR_BY_REGIME.csv` | Resultados por régimen de mercado (BTC alcista/bajista) |
| `TOP_GAINERS_DETECTION.csv` | Precisión/cobertura de detección temprana de Top Gainers |
| `INVERSE_CANDIDATES.csv` | Indicadores Categoría C (candidatos a señal inversa futura; sin operaciones inversas simuladas) |
| `UNTESTED_INDICATORS.csv` | Los 155 indicadores no evaluados en esta fase, con motivo |
| `DATA_COVERAGE.csv` | Cobertura real de datos y errores por símbolo/temporalidad |
| `SUMMARY.json` | Resumen final legible por ChatGPT |

## Pruebas automatizadas

```bash
pytest tests/ -v
```

Cubren: ausencia de look-ahead en señales y backtest, bloqueo correcto del
capital compartido, cálculo de estadísticas (incluyendo que lo indefinido se
reporte como `N/A`, nunca inventado), umbrales de clasificación congelados,
y que el registro documente los 200 indicadores sin omitir ninguno.

## Próximos pasos sugeridos (Fase 2, junto con ChatGPT)

1. Auditoría matemática independiente de las 45 fórmulas implementadas.
2. Ampliar cobertura: priorizar indicadores `PENDING_NEXT_PHASE` (103 ítems)
   con mayor probabilidad de aportar valor (ver nombres en
   `UNTESTED_INDICATORS.csv`).
3. Ejecutar el experimento ampliado de 180 días una vez validado el de 60.
4. Para los indicadores Categoría C, diseñar (sin ejecutar todavía) el
   protocolo de la hipótesis de señal inversa.
