"""
accounting.py — Contabilidad de cartera a precios de mercado (sección 3 de la
orden SPOT EDGE S2.1). Corrige el defecto P0 identificado por la auditoría:
`_build_equity_curve` de S2 solo registraba el equity en el instante de
CIERRE de cada operación, ignorando la ganancia/pérdida NO realizada mientras
la posición estaba abierta. Esto subestimaba el drawdown real y distorsionaba
el retorno diario.

Fórmula objetivo (sección 3, textual):
    Equity_t = Cash_t + Σ_i Q_i,t · P_i,t

Dado que el motor de S2.1 sigue usando una única posición abierta por
experimento (100 USDT compartidos, sin apalancamiento, sin posiciones
simultáneas dentro del mismo experimento — eso es justamente lo que impone
"capital compartido"), la fórmula se reduce en todo momento a:

    Equity_t = Cash_t                              (sin posición abierta)
    Equity_t = Q_abierta,t · P_abierta,t            (con posición abierta)

pero se calcula explícitamente a partir de precios de mercado reales en cada
barra del período de tenencia, no solo en el cierre, por lo que el drawdown
intra-operación queda correctamente representado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class LedgerTrade:
    """Una operación ejecutada, con todo lo necesario para que un tercero
    (ChatGPT u otro auditor) reconstruya la contabilidad de forma independiente
    sin volver a descargar datos de Binance."""

    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    equity_before: float          # capital comprometido en esta operación (USDT)
    entry_price_effective: float  # precio de entrada tras slippage
    exit_price_effective: float   # precio de salida tras slippage
    qty: float                    # cantidad del activo comprada
    commission_entry_usdt: float
    commission_exit_usdt: float
    gross_exit_value_usdt: float
    equity_after: float            # capital resultante tras comisión de salida
    pnl_usdt: float                 # equity_after - equity_before
    pnl_pct_net: float               # (equity_after/equity_before) - 1
    holding_hours: float
    # Trayectoria de precios de cierre entre entrada y salida (inclusive),
    # usada exclusivamente para mark-to-market. No introduce información
    # futura: cada punto es el close de una vela YA CERRADA en ese instante.
    mtm_times: list = field(default_factory=list)
    mtm_closes: list = field(default_factory=list)


def mark_to_market_curve(trades: list[LedgerTrade], initial_capital: float, start_time: pd.Timestamp | None = None) -> pd.Series:
    """Construye la curva de equity completa (Equity_t = Cash_t + Q_t·P_t)
    a resolución nativa de las velas, no solo en los instantes de cierre.

    Entre operaciones (sin posición abierta) el equity es constante (todo en
    cash); dentro de una operación, el equity sigue el precio de mercado del
    activo abierto multiplicado por la cantidad poseída, y se ajusta al valor
    neto realizado exactamente en el instante de salida (tras comisión).
    """
    if not trades:
        idx = [start_time] if start_time is not None else []
        return pd.Series([initial_capital] * len(idx), index=pd.DatetimeIndex(idx) if idx else pd.DatetimeIndex([]))

    points_time = []
    points_equity = []
    first_point_time = start_time if start_time is not None else trades[0].entry_time
    points_time.append(first_point_time)
    points_equity.append(initial_capital)

    for t in trades:
        if t.mtm_times:
            for ts, close in zip(t.mtm_times, t.mtm_closes):
                points_time.append(ts)
                points_equity.append(t.qty * close)
            # Corrige el último punto (instante de salida) al valor REALIZADO
            # neto de comisión de salida, no al valor bruto de mercado.
            points_time[-1] = t.exit_time
            points_equity[-1] = t.equity_after
        else:
            # Sin trayectoria disponible (no debería ocurrir en uso normal):
            # degradar a solo-cierre, documentado como limitación de datos.
            points_time.append(t.exit_time)
            points_equity.append(t.equity_after)

    series = pd.Series(points_equity, index=pd.DatetimeIndex(points_time))
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()


def max_drawdown_pct(equity_curve: pd.Series) -> float | None:
    if len(equity_curve) < 2:
        return None
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return float(drawdown.min() * 100)


def daily_equity(equity_curve: pd.Series) -> pd.Series:
    """Resamplea la curva MTM a resolución diaria (último valor del día,
    propagado hacia adelante en días sin barras — correcto porque sin
    operación el equity no cambia)."""
    if len(equity_curve) < 1:
        return equity_curve
    return equity_curve.resample("1D").last().ffill()


def daily_returns(daily_equity_series: pd.Series) -> pd.Series:
    if len(daily_equity_series) < 2:
        return pd.Series(dtype=float)
    return daily_equity_series.pct_change().dropna()


def build_trade_ledger_rows(trades: list[LedgerTrade], indicator_id, indicator_name, timeframe, horizon_hours) -> list[dict]:
    """Filas para TRADE_LEDGER.csv — suficientes para que un auditor externo
    reconstruya capital_disponible, capital_comprometido, pnl realizado y
    equity resultante operación por operación, sin volver a tocar Binance."""
    rows = []
    for t in trades:
        rows.append({
            "catalog_id": indicator_id,
            "indicator_name": indicator_name,
            "timeframe": timeframe,
            "horizon_hours": horizon_hours,
            "symbol": t.symbol,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat(),
            "capital_disponible_antes_usdt": round(t.equity_before, 6),
            "capital_comprometido_usdt": round(t.equity_before, 6),
            "cantidad_activo": t.qty,
            "precio_entrada_efectivo": t.entry_price_effective,
            "comision_entrada_usdt": round(t.commission_entry_usdt, 6),
            "precio_salida_efectivo": t.exit_price_effective,
            "valor_mercado_salida_bruto_usdt": round(t.gross_exit_value_usdt, 6),
            "comision_salida_usdt": round(t.commission_exit_usdt, 6),
            "pnl_realizado_usdt": round(t.pnl_usdt, 6),
            "pnl_realizado_pct": round(t.pnl_pct_net * 100, 6),
            "capital_resultante_usdt": round(t.equity_after, 6),
            "holding_horas": t.holding_hours,
        })
    return rows
