"""
registry.py — Registro general de investigación de los 200 indicadores
(sección 3 del encargo).

Para cada uno de los 200 ítems del catálogo (CATALOGO_INDICADORES_200.json)
se documentan: nombre, fórmula, parámetros, temporalidad, datos necesarios,
señal LONG, condición de salida, estado de implementación, fuente técnica y
limitaciones.

Filosofía de esta fase (ver README "Alcance honesto de la Fase 1"):
  - IMPLEMENTED: ~43 indicadores con fórmula pública verificable, codificados
    en src/indicators/signals.py y respaldados por backtest real.
  - El resto del catálogo recibe un estado documentado y un motivo concreto,
    asignado por una regla explícita (no una opinión improvisada por
    indicador). Nada se marca "evaluado" sin haber corrido código real.

No se inventan implementaciones equivalentes para completar artificialmente
los 200 (instrucción explícita del encargo, sección 3).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from src.indicators.signals import REGISTRY_FUNCTIONS

CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                             "CATALOGO_INDICADORES_200.json")

STATUS_IMPLEMENTED = "IMPLEMENTED"
STATUS_NOT_EVALUABLE_PROPRIETARY = "NOT_EVALUABLE_PROPRIETARY"
STATUS_NOT_EVALUABLE_DATA = "NOT_EVALUABLE_DATA"
STATUS_NOT_EVALUABLE_RELATIONAL = "NOT_EVALUABLE_RELATIONAL"
STATUS_NOT_EVALUABLE_PATTERN = "NOT_EVALUABLE_PATTERN"
STATUS_PENDING_NEXT_PHASE = "PENDING_NEXT_PHASE"


@dataclass
class IndicatorDefinition:
    catalog_id: int
    name: str
    user_description: str
    formula: str = ""
    parameters: str = ""
    timeframes: tuple = ()
    data_required: str = ""
    long_signal_description: str = ""
    exit_condition: str = "Horizonte fijo de mantenimiento (4h / 24h / 72h). Ver config.HOLDING_HORIZONS_HOURS."
    implementation_status: str = STATUS_PENDING_NEXT_PHASE
    technical_source: str = ""
    limitations: str = ""
    signal_function_name: str = ""
    reason_if_not_implemented: str = ""

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timeframes"] = ",".join(self.timeframes)
        return d


# ---------------------------------------------------------------------------
# Fichas completas de los indicadores IMPLEMENTADOS (43).
# ---------------------------------------------------------------------------
_IMPLEMENTED_DEFS = [
    IndicatorDefinition(
        81, "Hull Moving Average (HMA) Suite",
        "Medias móviles sin retraso con códigos de color de dirección.",
        formula="HMA(n) = WMA(2*WMA(close,n/2) - WMA(close,n), round(sqrt(n)))",
        parameters="n=21", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio de cierre por encima de la HMA(21).",
        technical_source="Alan Hull (2005), fórmula de dominio público.",
        limitations="Sensible a ruido en temporalidades bajas (15m).",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_hma_cross",
    ),
    IndicatorDefinition(
        82, "Arnaud Legoux Moving Average (ALMA)",
        "Filtro gaussiano para suavizado perfecto con baja latencia.",
        formula="ALMA con ventana gaussiana (offset=0.85, sigma=6)",
        parameters="length=21, offset=0.85, sigma=6", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio por encima de ALMA(21).",
        technical_source="Arnaud Legoux & Dimitrios Kouzis Loukas (2009).",
        limitations="Parámetros offset/sigma elegidos por defecto estándar, no optimizados.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_alma_cross",
    ),
    IndicatorDefinition(
        83, "Kaufman Adaptive Moving Average (KAMA)",
        "Media ajustada automáticamente a la volatilidad del activo.",
        formula="KAMA con Efficiency Ratio; fast=2, slow=30, length=10",
        parameters="length=10, fast=2, slow=30", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio por encima de KAMA.",
        technical_source="Perry Kaufman, 'Smarter Trading' (1995).",
        limitations="Requiere 10+ velas de calentamiento interno además del warm-up general.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_kama_cross",
    ),
    IndicatorDefinition(
        84, "Tillson T3 Moving Average",
        "Media de triple suavizado para evitar falsas señales.",
        formula="T3 = c1*EMA6 + c2*EMA5 + c3*EMA4 + c4*EMA3 (Tillson, vfactor=0.7)",
        parameters="length=10, vfactor=0.7", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio por encima de T3(10).",
        technical_source="Tim Tillson, 'Technical Analysis of Stocks & Commodities' (1998).",
        limitations="Introduce lag residual mayor que HMA/ALMA.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_t3_cross",
    ),
    IndicatorDefinition(
        85, "Zero Lag Exponential Moving Average (ZLEMA)",
        "EMA con corrección de desfase temporal.",
        formula="ZLEMA = EMA(close + (close - close[lag]), n), lag=(n-1)/2",
        parameters="n=21", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio por encima de ZLEMA(21).",
        technical_source="John Ehlers / Rick Hindi (2000), fórmula de dominio público.",
        limitations="Puede sobre-reaccionar en velas con gaps grandes.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_zlema_cross",
    ),
    IndicatorDefinition(
        86, "McGinley Dynamic Indicator",
        "Mecanismo que ajusta su velocidad a la aceleración del mercado.",
        formula="MD[i] = MD[i-1] + (price - MD[i-1]) / (N * (price/MD[i-1])^4)",
        parameters="N=14", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Cruce del precio por encima de McGinley Dynamic(14).",
        technical_source="John R. McGinley (1990's), 'Journal of Technical Analysis'.",
        limitations="Recursivo; sensible al punto de arranque de la serie.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_mcginley_cross",
    ),
    IndicatorDefinition(
        110, "DEMA / TEMA Cross Overlay",
        "Cruces de doble y triple media móvil exponencial.",
        formula="DEMA=2*EMA-EMA(EMA); TEMA=3*EMA-3*EMA(EMA)+EMA(EMA(EMA))",
        parameters="length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="DEMA(20) cruza por encima de TEMA(20).",
        technical_source="Patrick Mulloy (1994), 'Technical Analysis of Stocks & Commodities'.",
        limitations="Ambas medias comparten base EMA; señal puede ser poco frecuente.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_dema_tema_cross",
    ),
    IndicatorDefinition(
        87, "Supertrend Multi-Timeframe",
        "Supertrend superpuesto desde marcos temporales superiores.",
        formula="Supertrend estándar: bandas HL2 ± mult*ATR(length), flip direccional.",
        parameters="length=10, mult=3.0", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Cambio de dirección de bajista a alcista (flip) en la misma temporalidad.",
        technical_source="Olivier Seban, fórmula de dominio público ampliamente documentada.",
        limitations="Implementado en una sola temporalidad (no multi-timeframe superpuesto como el nombre original sugiere); documentado como limitación.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_supertrend_flip",
    ),
    IndicatorDefinition(
        94, "Parabolic SAR Advanced",
        "Puntos SAR ajustados por volatilidad ATR variable.",
        formula="Parabolic SAR de Wilder, af_step=0.02, af_max=0.2 (versión estándar, no variable por ATR).",
        parameters="af_step=0.02, af_max=0.2", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Precio cruza por encima del SAR (flip a alcista).",
        technical_source="J. Welles Wilder, 'New Concepts in Technical Trading Systems' (1978).",
        limitations="Se implementó la versión estándar de Wilder, no la variante 'ATR-adaptativa' mencionada en el nombre comercial (no hay fórmula pública única para esa variante).",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_parabolic_sar_flip",
    ),
    IndicatorDefinition(
        95, "Donchian Channels Trend Ribbon",
        "Canales de ruptura adaptados a ciclos semanales.",
        formula="Canal superior = max(high, 20); ruptura cuando close > canal_superior[t-1]",
        parameters="length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Ruptura del canal superior de Donchian(20).",
        technical_source="Richard Donchian (1960's), fórmula de dominio público.",
        limitations="No implementa el 'ribbon' multi-periodo del nombre comercial; una sola longitud.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_donchian_breakout",
    ),
    IndicatorDefinition(
        109, "Triple Exponential Average (TRIX)",
        "Rate of change triple suavizado.",
        formula="TRIX = 100 * d/dt[EMA(EMA(EMA(close,n)))] / EMA(EMA(EMA(close,n)))[t-1]",
        parameters="n=15", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="TRIX cruza por encima de 0.",
        technical_source="Jack Hutson (1980), 'Technical Analysis of Stocks & Commodities'.",
        limitations="Lag considerable por el triple suavizado.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_trix_zero_cross",
    ),
    IndicatorDefinition(
        121, "Relative Strength Index (RSI) Multi-Length",
        "RSI con múltiples ventanas temporales simultáneas.",
        formula="RSI de Wilder, longitud=14 (se evalúa una sola longitud, no 'multi-length' simultáneo).",
        parameters="length=14, umbral_recuperación=30", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="RSI(14) recupera por encima de 30 tras estar en o por debajo de 30.",
        technical_source="J. Welles Wilder (1978).",
        limitations="No se implementan múltiples longitudes simultáneas pese al nombre comercial.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_rsi_recovery",
    ),
    IndicatorDefinition(
        122, "Stochastic RSI (StochRSI) Advanced",
        "Oscilador estocástico aplicado sobre los valores del RSI.",
        formula="StochRSI = 100*(RSI-min(RSI,n))/(max(RSI,n)-min(RSI,n)), n=14",
        parameters="rsi_length=14, stoch_length=14, umbral=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="StochRSI recupera por encima de 20.",
        technical_source="Tushar Chande & Stanley Kroll (1994).",
        limitations="Muy sensible a ruido; muchas señales en rangos.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_stochrsi_recovery",
    ),
    IndicatorDefinition(
        124, "Connors RSI (CRSI)",
        "Combinación de RSI, Streak RSI y Rate of Change (ROC).",
        formula="CRSI = (RSI(close,3) + RSI(streak,2) + PercentRank(ROC(close,1),100)) / 3",
        parameters="rsi_length=3, streak_rsi_length=2, rank_length=100", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="CRSI recupera por encima de 30.",
        technical_source="Laurence Connors & Cesar Alvarez (2012), 'Short Term Trading Strategies That Work'.",
        limitations="Implementación propia del percent-rank; puede diferir ligeramente de implementaciones comerciales.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_connors_rsi_recovery",
    ),
    IndicatorDefinition(
        128, "Commodity Channel Index (CCI) Woodies",
        "Versión extendida del CCI con barras de confirmación.",
        formula="CCI = (TP - SMA(TP,n)) / (0.015 * DesvMediaAbs(TP,n)), TP=(H+L+C)/3",
        parameters="length=20, umbral_recuperación=-100", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="CCI(20) recupera por encima de -100.",
        technical_source="Donald Lambert (1980).",
        limitations="No incluye las 'barras de confirmación Woodies' propietarias.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_cci_recovery",
    ),
    IndicatorDefinition(
        129, "Williams %R Momentum Bands",
        "Oscilador de sobrecompra/sobreventa con bandas de volatilidad.",
        formula="%R = -100 * (HH(n)-close) / (HH(n)-LL(n))",
        parameters="length=14, umbral=-80", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="%R recupera por encima de -80.",
        technical_source="Larry Williams (1973).",
        limitations="No se implementan las 'bandas de volatilidad' propietarias del nombre comercial.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_williams_r_recovery",
    ),
    IndicatorDefinition(
        130, "Awesome Oscillator (AO) Twin Peaks",
        "Identifica impulsos y divergencias en barras de histograma.",
        formula="AO = SMA(HL2,5) - SMA(HL2,34)",
        parameters="fast=5, slow=34", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low",
        long_signal_description="AO cruza por encima de 0.",
        technical_source="Bill Williams, 'New Trading Dimensions' (1998).",
        limitations="No implementa el patrón 'Twin Peaks' propietario; solo cruce de cero.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_awesome_oscillator_zero_cross",
    ),
    IndicatorDefinition(
        131, "Accelerator Oscillator (AC)",
        "Mide el cambio en la aceleración del Awesome Oscillator.",
        formula="AC = AO - SMA(AO,5)",
        parameters="length=5", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low",
        long_signal_description="AC cruza por encima de 0.",
        technical_source="Bill Williams, 'New Trading Dimensions' (1998).",
        limitations="Comparte base con AO; señales correlacionadas.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_accelerator_oscillator_zero_cross",
    ),
    IndicatorDefinition(
        132, "True Strength Index (TSI) Dual Line",
        "Oscilador doblemente suavizado para señalar impulsos macro.",
        formula="TSI = 100 * EMA(EMA(mom,25),13) / EMA(EMA(|mom|,25),13); señal=EMA(TSI,7)",
        parameters="long=25, short=13, signal=7", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Línea TSI cruza por encima de su señal.",
        technical_source="William Blau (1991).",
        limitations="Lag notable por doble suavizado.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_tsi_signal_cross",
    ),
    IndicatorDefinition(
        136, "Chande Momentum Oscillator (CMO)",
        "Mide el momentum calculando directamente las variaciones.",
        formula="CMO = 100 * (SumGanancias - SumPérdidas) / (SumGanancias + SumPérdidas)",
        parameters="length=14, umbral=-50", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="CMO recupera por encima de -50.",
        technical_source="Tushar Chande (1994).",
        limitations="Umbral de recuperación elegido por el equipo, no estándar universal.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_cmo_recovery",
    ),
    IndicatorDefinition(
        137, "Rate of Change (ROC) Percentage",
        "Tasa de variación porcentual pura entre períodos.",
        formula="ROC = 100 * (close - close[n]) / close[n]",
        parameters="length=12", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="ROC cruza por encima de 0.",
        technical_source="Fórmula estándar de dominio público.",
        limitations="Genera muchas señales en mercados laterales.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_roc_zero_cross",
    ),
    IndicatorDefinition(
        141, "Balance of Power (BOP)",
        "Mide la capacidad de los compradores para empujar el precio a extremos.",
        formula="BOP = (close - open) / (high - low)",
        parameters="sin parámetros (instantáneo)", timeframes=("15m", "1h", "4h", "1d"),
        data_required="open, high, low, close",
        long_signal_description="BOP cruza por encima de 0.",
        technical_source="Igor Livshin, 'Technical Analysis of Stocks & Commodities' (2001).",
        limitations="Muy ruidoso vela a vela; podría beneficiarse de suavizado (no aplicado en fase 1).",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_balance_of_power_zero_cross",
    ),
    IndicatorDefinition(
        149, "PPO (Percentage Price Oscillator)",
        "Expresa la diferencia de medias móviles en términos porcentuales.",
        formula="PPO = 100*(EMA(close,12)-EMA(close,26))/EMA(close,26); señal=EMA(PPO,9)",
        parameters="fast=12, slow=26, signal=9", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Línea PPO cruza por encima de su señal.",
        technical_source="Gerald Appel (variante porcentual del MACD), dominio público.",
        limitations="Mismo lag estructural que el MACD.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_ppo_signal_cross",
    ),
    IndicatorDefinition(
        96, "Keltner Channels Volatility Bands",
        "Canales basados en medias móviles exponenciales y ATR.",
        formula="Centro=EMA(close,20); Bandas=Centro ± mult*ATR(20), mult=2.0",
        parameters="length=20, mult=2.0", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Ruptura de la banda superior de Keltner.",
        technical_source="Chester Keltner (1960), variante ATR de Linda Bradford Raschke.",
        limitations="Sensible a la elección del múltiplo de ATR.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_keltner_breakout",
    ),
    IndicatorDefinition(
        97, "Choppiness Index (CHOP)",
        "Determina si la acción del precio es lateral (>61.8) o tendencial (<38.2).",
        formula="CHOP = 100*log10(Sum(TR,n)/(HH(n)-LL(n))) / log10(n)",
        parameters="length=14, umbral_tendencia=38.2", timeframes=("1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Compuesto: régimen de tendencia (CHOP<38.2) + cruce alcista EMA20/EMA50 (no es señal independiente, ver limitaciones).",
        technical_source="E.W. Dreiss (1993).",
        limitations="Por sí solo CHOP no genera señales LONG; se combinó con un cruce de medias para hacerlo comparable, combinación registrada explícitamente.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_choppiness_trend_composite",
    ),
    IndicatorDefinition(
        104, "Squeeze Momentum Deluxe",
        "Detección de fases de compresión y posterior explosión direccional.",
        formula="Squeeze = Bollinger(20,2) dentro de Keltner(20,1.5); salida cuando el histograma de momentum cruza a positivo.",
        parameters="bb_length=20, bb_mult=2.0, kc_length=20, kc_mult=1.5", timeframes=("1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Tras una fase de compresión (Bollinger dentro de Keltner), el momentum cruza de negativo a positivo.",
        technical_source="John Carter, 'Mastering the Trade' (concepto del 'squeeze'); implementación propia simplificada.",
        limitations="Versión simplificada; no replica exactamente el indicador comercial 'Squeeze Momentum Deluxe'.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_squeeze_momentum_breakout",
    ),
    IndicatorDefinition(
        119, "Detrended Price Oscillator (DPO)",
        "Aísla el precio de la tendencia para ubicar soportes cíclicos.",
        formula="DPO = close[t - (n/2+1)] - SMA(close,n)",
        parameters="length=20", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="DPO cruza por encima de 0.",
        technical_source="Fórmula estándar de dominio público.",
        limitations="Usa un desplazamiento intencional hacia atrás; no es apto para 'predecir', solo para ubicar ciclos pasados.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_dpo_zero_cross",
    ),
    IndicatorDefinition(
        120, "Mass Index Reversal Signal",
        "Identifica ensanchamientos del rango que preceden a cambios de tendencia.",
        formula="MI = Sum(EMA9(H-L)/EMA9(EMA9(H-L)), 25); señal reversal: MI>27 seguido de MI<26.5",
        parameters="ema_length=9, sum_length=25, bulge=27.0, reset=26.5", timeframes=("1h", "4h", "1d"),
        data_required="high, low, close",
        long_signal_description="Tras un 'bulge' (MI>27) reciente, MI cae por debajo de 26.5 y el precio sube respecto a la vela previa.",
        technical_source="Donald Dorsey (1992).",
        limitations="La 'Mass Index Reversal' original no define dirección por sí misma; se añadió el filtro de precio al alza, combinación documentada.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_mass_index_reversal",
    ),
    IndicatorDefinition(
        145, "Relative Volatility Index (RVI)",
        "Mide la dirección de los precios evaluando la desviación estándar.",
        formula="RVI = 100 * SuavizadoWilder(StdUp,14) / (SuavizadoWilder(StdUp,14)+SuavizadoWilder(StdDown,14))",
        parameters="std_length=10, smoothing_length=14, umbral=50", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="RVI recupera por encima de 50.",
        technical_source="Donald Dorsey (1993), revisado 1995.",
        limitations="No confundir con el 'Relative Vigor Index' (nombre similar, fórmula distinta); aquí se implementa el de volatilidad relativa de Dorsey.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_rvi_recovery",
    ),
    IndicatorDefinition(
        50, "On-Balance Volume (OBV) Advanced",
        "OBV con media móvil adaptativa para filtrar divergencias.",
        formula="OBV = cumsum(sign(Δclose)*volume); señal: OBV cruza por encima de SMA(OBV,20)",
        parameters="sma_length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close, volume",
        long_signal_description="OBV cruza por encima de su media móvil simple de 20 periodos.",
        technical_source="Joseph Granville (1963).",
        limitations="Se usó SMA simple como 'media adaptativa' aproximada (no KAMA/VIDYA sobre OBV en esta fase).",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_obv_breakout",
    ),
    IndicatorDefinition(
        51, "Chaikin Money Flow (CMF) 200",
        "Flujo de dinero ajustado para ventanas institucionales.",
        formula="CMF = Sum(((C-L)-(H-C))/(H-L)*Vol, n) / Sum(Vol, n)",
        parameters="length=20 (no 200; ver limitaciones)", timeframes=("1h", "4h", "1d"),
        data_required="high, low, close, volume",
        long_signal_description="CMF cruza por encima de 0.",
        technical_source="Marc Chaikin (1980's).",
        limitations="El nombre sugiere ventana de 200 periodos; se usó 20 (ventana institucional estándar) por disponibilidad de datos en 60 días. Documentado como desviación.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_cmf_zero_cross",
    ),
    IndicatorDefinition(
        52, "Accumulation/Distribution Line (A/D)",
        "Mide el balance de presión acumulativa.",
        formula="A/D = cumsum(((C-L)-(H-C))/(H-L)*Vol)",
        parameters="sma_length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close, volume",
        long_signal_description="A/D cruza por encima de su SMA(20).",
        technical_source="Marc Chaikin, dominio público.",
        limitations="Ninguna relevante adicional.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_ad_line_breakout",
    ),
    IndicatorDefinition(
        53, "Money Flow Index (MFI) Multi-timeframe",
        "RSI ponderado por volumen en matrices.",
        formula="MFI = 100 - 100/(1+MoneyFlowRatio); TP=(H+L+C)/3",
        parameters="length=14, umbral=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close, volume",
        long_signal_description="MFI recupera por encima de 20.",
        technical_source="Gene Quong & Avrum Soudack (1989).",
        limitations="Se evalúa una sola temporalidad por corrida, no 'matriz multi-timeframe' simultánea.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_mfi_recovery",
    ),
    IndicatorDefinition(
        57, "Taker Buy Ratio Spot (Binance)",
        "Proporción de volumen ejecutado al Ask (compras agresivas).",
        formula="ratio = taker_buy_base_volume / volume (campo nativo de los klines de Binance)",
        parameters="sma_length=10, umbral=0.55", timeframes=("15m", "1h", "4h", "1d"),
        data_required="volume, taker_buy_base_volume",
        long_signal_description="Ratio > 0.55, por encima de su media móvil, con precio al alza respecto a la vela previa.",
        technical_source="Campo oficial de la API pública de Binance (taker_buy_base_asset_volume).",
        limitations="Es un dato real de Binance (no estimado), a diferencia de otros indicadores de volumen 'simulados'.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_taker_buy_ratio_pressure",
    ),
    IndicatorDefinition(
        48, "Cumulative Volume Delta (CVD) Spot",
        "Medidor acumulado de presión compradora de mercado (Market Orders).",
        formula="delta = taker_buy_volume - (volume - taker_buy_volume); CVD = cumsum(delta)",
        parameters="sma_length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="volume, taker_buy_base_volume",
        long_signal_description="CVD cruza por encima de su SMA(20).",
        technical_source="Derivado del campo oficial taker_buy_base_asset_volume de Binance.",
        limitations="Aproximación por vela (no tick a tick); usa el campo agregado de klines, no el libro de órdenes.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_cvd_breakout",
    ),
    IndicatorDefinition(
        61, "Klinger Volume Oscillator (KVO)",
        "Mide la fuerza del flujo financiero a largo plazo.",
        formula="KVO = EMA(VF,34) - EMA(VF,55); señal=EMA(KVO,13); VF depende del 'trend' de HLC y Volumen Acumulado",
        parameters="fast=34, slow=55, signal=13", timeframes=("1h", "4h", "1d"),
        data_required="high, low, close, volume",
        long_signal_description="Línea KVO cruza por encima de su señal.",
        technical_source="Stephen Klinger (1977).",
        limitations="Implementación propia del 'volumen acumulado' (cm); puede diferir levemente de otras implementaciones comerciales en los primeros tramos de la serie.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_klinger_signal_cross",
    ),
    IndicatorDefinition(
        152, "Elder Force Index (EFI) 13 EMA",
        "Mide la fuerza detrás de cada vela Spot combinando precio y volumen.",
        formula="FI = EMA((close - close[1]) * volume, 13)",
        parameters="length=13", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close, volume",
        long_signal_description="Elder Force Index cruza por encima de 0.",
        technical_source="Alexander Elder, 'Trading for a Living' (1993).",
        limitations="Ninguna relevante adicional.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_elder_force_index_zero_cross",
    ),
    IndicatorDefinition(
        3, "Z-Score Distance from VWAP",
        "Desviación estadística en unidades Z respecto al valor ponderado.",
        formula="z = (close - VWAP(20)) normalizado por su propia media y desviación móvil (20)",
        parameters="vwap_length=20, zscore_length=20", timeframes=("15m", "1h", "4h", "1d"),
        data_required="high, low, close, volume",
        long_signal_description="El Z-score de la distancia al VWAP recupera por encima de -2.",
        technical_source="Concepto estadístico estándar aplicado a VWAP móvil (no al VWAP de sesión institucional).",
        limitations="Se usa un VWAP móvil de 20 periodos, no un VWAP anclado a apertura de sesión (dato de sesión no bien definido en mercado 24/7).",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_vwap_zscore_recovery",
    ),
    IndicatorDefinition(
        4, "Hurst Exponent Indicator",
        "Mide si el activo está en tendencia (H > 0.5) o en reversión (H < 0.5).",
        formula="H estimado por regresión log-log de la desviación estándar de diferencias rezagadas (método R/S simplificado), ventana=100",
        parameters="window=100", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Compuesto: H>0.55 (régimen persistente) + cruce alcista EMA20/EMA50.",
        technical_source="Harold Edwin Hurst (1951); método de estimación simplificado, no R/S completo de Mandelbrot.",
        limitations="El Hurst exponent por sí solo no da dirección; se combinó con un cruce de medias, combinación documentada explícitamente.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_hurst_trend_composite",
    ),
    IndicatorDefinition(
        5, "Kalman Filter Price Smoother",
        "Filtro estadístico adaptativo que elimina ruido de fondo.",
        formula="Filtro de Kalman escalar 1D (varianza de proceso=1e-5, varianza de medición=1e-2)",
        parameters="process_var=1e-5, measurement_var=1e-2", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Precio cruza por encima de la línea suavizada por el filtro de Kalman.",
        technical_source="Rudolf Kálmán (1960), formulación escalar estándar.",
        limitations="Varianzas fijadas por el equipo, no estimadas por máxima verosimilitud.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_kalman_cross",
    ),
    IndicatorDefinition(
        10, "Shannon Entropy Indicator",
        "Mide el grado de incertidumbre y desorden en la acción del precio.",
        formula="H = -Sum(p_i * log2(p_i)) sobre histograma de retornos (10 bins, ventana 20)",
        parameters="window=20, bins=10", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Compuesto: entropía baja (percentil 25 de las últimas 60 velas) seguida de ruptura del canal de Donchian(20).",
        technical_source="Claude Shannon (1948), teoría de la información.",
        limitations="La entropía por sí sola mide desorden, no dirección; se combinó con ruptura de Donchian, combinación documentada.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_entropy_compression_breakout",
    ),
    IndicatorDefinition(
        29, "Kaufman Efficiency Ratio (ER)",
        "Ratio de eficiencia entre el desplazamiento del precio y el ruido.",
        formula="ER = |close - close[n]| / Sum(|Δclose|, n)",
        parameters="length=10, umbral=0.3", timeframes=("1h", "4h", "1d"),
        data_required="close",
        long_signal_description="ER cruza por encima de 0.3 (mercado eficiente/direccional) con precio al alza.",
        technical_source="Perry Kaufman, 'Smarter Trading' (1995).",
        limitations="ER no indica dirección por sí mismo; se combinó con filtro de precio al alza, combinación documentada.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_kaufman_er_trend_composite",
    ),
    IndicatorDefinition(
        34, "Mean Reversion Z-Score Signal",
        "Alertas estadísticas en desvíos ±2.5σ.",
        formula="z = (close - SMA(close,20)) / Std(close,20)",
        parameters="length=20, umbral=-2.5", timeframes=("15m", "1h", "4h", "1d"),
        data_required="close",
        long_signal_description="Z-score recupera por encima de -2.5 tras haber estado en o por debajo de ese nivel.",
        technical_source="Concepto estadístico estándar (z-score de reversión a la media).",
        limitations="Asume que el precio reciente es aproximadamente estacionario en la ventana; no siempre se cumple.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_zscore_mean_reversion_recovery",
    ),
    IndicatorDefinition(
        37, "Augmented Dickey-Fuller (ADF) Test Indicator",
        "Verifica si una serie de precios es estacionaria.",
        formula="p-valor del test ADF (statsmodels.tsa.stattools.adfuller, maxlag=1) en ventana móvil de 60 velas",
        parameters="window=60, umbral_p=0.10", timeframes=("4h", "1d"),
        data_required="close",
        long_signal_description="Compuesto: ventana con p-valor ADF<0.10 (serie más estacionaria) + z-score(20) recuperando por encima de -1.",
        technical_source="David Dickey & Wayne Fuller (1979); implementación vía statsmodels.",
        limitations="Computacionalmente costoso (se recalcula por ventana); el test ADF por sí solo no genera dirección, se combinó con z-score, combinación documentada.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_adf_stationary_meanreversion",
    ),
    IndicatorDefinition(
        23, "Beta relative to BTC",
        "Cuantifica la sensibilidad de un altcoin frente al movimiento de Bitcoin.",
        formula="beta = Cov(ret_activo, ret_BTC,30) / Var(ret_BTC,30)",
        parameters="window=30, umbral_beta=1.0", timeframes=("1h", "4h", "1d"),
        data_required="close (activo) + close de BTC/USDT alineado",
        long_signal_description="Compuesto: beta>1 + retorno de BTC positivo + activo superando el retorno de BTC en la misma vela.",
        technical_source="William Sharpe (CAPM, 1964), aplicado a criptoactivos frente a BTC como benchmark.",
        limitations="Beta por sí sola es relacional, no direccional; se combinó con filtros de BTC y rendimiento relativo, combinación documentada.",
        implementation_status=STATUS_IMPLEMENTED, signal_function_name="sig_beta_btc_composite",
    ),
]

_IMPLEMENTED_IDS = {d.catalog_id for d in _IMPLEMENTED_DEFS}
assert len(_IMPLEMENTED_IDS) == len(_IMPLEMENTED_DEFS), "IDs de indicadores implementados duplicados"
assert len(_IMPLEMENTED_IDS) == len(REGISTRY_FUNCTIONS), (
    f"Descalce entre fichas ({len(_IMPLEMENTED_IDS)}) y funciones registradas ({len(REGISTRY_FUNCTIONS)})"
)


# ---------------------------------------------------------------------------
# Reglas de clasificación automática para el resto del catálogo (documentadas,
# no una opinión improvisada por ítem). Se aplican en orden; la primera regla
# que haga match decide el estado y el motivo.
# ---------------------------------------------------------------------------
_PROPRIETARY_MARKERS = (
    "luxalgo", "lazybear", "libero", "clone", "deluxe", "woodies",
    "ssl hybrid", "ut bot", "alpha trend", "trend magic", "halftrend",
    "coral trend", "smc suite", "market cipher",
)
_DATA_UNAVAILABLE_MARKERS = (
    "order book", "open interest", "liquidation", "wallet", "billetera",
    "spot vs. futures", "spot inflow", "futures", "interés abierto",
)
_RELATIONAL_MARKERS = (
    "correlation", "correlación", "sharpe", "sortino", "treynor",
    "information ratio", "jensen", "co-integration", "cointegration",
    "half-life", "spread monitor", "pairs",
)
_PATTERN_MARKERS = (
    "pattern", "patrón", "patrones", "harmonic", "head and shoulders",
    "hombro", "wedge", "cuña", "triangle", "triángulo", "flag", "bandera",
    "pennant", "banderín", "pitchfork", "gann", "fractal dimension",
    "elliott", "fibonacci", "pivot points", "wyckoff", "demark",
    "three line break", "point & figure", "point and figure", "kagi",
    "renko", "double top", "double bottom", "techo", "suelo",
)


def _classify_unimplemented(name: str, description: str) -> tuple[str, str]:
    text = f"{name} {description}".lower()
    for marker in _PROPRIETARY_MARKERS:
        if marker in text:
            return (
                STATUS_NOT_EVALUABLE_PROPRIETARY,
                "Script/visualización propietaria de TradingView u otro proveedor, sin fórmula "
                "matemática pública única y reproducible. No se construyó una 'implementación "
                "equivalente' para evitar inventar resultados (instrucción explícita del encargo).",
            )
    for marker in _DATA_UNAVAILABLE_MARKERS:
        if marker in text:
            return (
                STATUS_NOT_EVALUABLE_DATA,
                "Requiere datos de libro de órdenes, interés abierto de futuros, o flujos on-chain/"
                "de wallets, no disponibles mediante la API pública histórica de Binance Spot "
                "(klines). No evaluable con la fuente de datos permitida en este encargo.",
            )
    for marker in _RELATIONAL_MARKERS:
        if marker in text:
            return (
                STATUS_NOT_EVALUABLE_RELATIONAL,
                "Es una métrica relacional o de desempeño ajustado por riesgo; no define por sí "
                "sola una regla de entrada LONG objetiva sin una regla adicional no especificada "
                "por el usuario. Documentado como 'requiere combinación', sin inventar esa regla.",
            )
    for marker in _PATTERN_MARKERS:
        if marker in text:
            return (
                STATUS_NOT_EVALUABLE_PATTERN,
                "Reconocimiento de patrones geométricos/visuales que requiere un algoritmo de "
                "detección no trivial (no hay una única regla matemática objetiva ampliamente "
                "aceptada); su codificación fiable queda fuera del alcance de esta primera fase.",
            )
    return (
        STATUS_PENDING_NEXT_PHASE,
        "Indicador con fórmula identificable y datos disponibles en principio, pero no priorizado "
        "para codificación en este primer motor (alcance de Fase 1). Candidato explícito para una "
        "fase 2 de ampliación de cobertura, a definir junto con ChatGPT.",
    )


def load_catalog_raw() -> list[dict]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data["items"]


def build_full_registry() -> list[IndicatorDefinition]:
    """Construye la ficha de los 200 indicadores: implementados + clasificados."""
    implemented_by_id = {d.catalog_id: d for d in _IMPLEMENTED_DEFS}
    raw_items = load_catalog_raw()
    full: list[IndicatorDefinition] = []
    for item in raw_items:
        cid = item["id"]
        if cid in implemented_by_id:
            full.append(implemented_by_id[cid])
            continue
        status, reason = _classify_unimplemented(item["name"], item.get("user_description", ""))
        full.append(
            IndicatorDefinition(
                catalog_id=cid,
                name=item["name"],
                user_description=item.get("user_description", ""),
                implementation_status=status,
                reason_if_not_implemented=reason,
            )
        )
    full.sort(key=lambda d: d.catalog_id)
    assert len(full) == 200, f"Se esperaban 200 indicadores en el registro, hay {len(full)}"
    return full


def get_signal_function(name: str):
    return REGISTRY_FUNCTIONS[name]
