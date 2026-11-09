import pandas as pd

from src_s21.universe import _is_non_crypto, finalize_universe_with_historical_liquidity


def test_stablecoin_and_tokenized_equity_excluded_from_crypto_universe():
    """La auditoría encontró USDCUSDT, EURUSDT, NVDABUSDT, MSTRBUSDT, etc.
    dentro del universo de S2. S2.1 debe excluirlos explícitamente."""
    assert _is_non_crypto("USDC") is True
    assert _is_non_crypto("EUR") is True
    assert _is_non_crypto("NVDAB") is True
    assert _is_non_crypto("MSTRB") is True
    assert _is_non_crypto("BTC") is False
    assert _is_non_crypto("SOL") is False


def test_universe_inclusion_based_on_historical_liquidity_not_current_ticker():
    """Defecto P1 de S2: la inclusión se decidía con el ticker de 24h ACTUAL.
    S2.1 debe decidir con el volumen cotizado HISTÓRICO REAL de la ventana
    analizada, calculado a partir de las velas diarias ya descargadas."""
    dates = pd.date_range("2026-01-01", periods=10, freq="1D", tz="UTC")

    # Símbolo con alto volumen histórico real -> debe quedar incluido.
    liquid_df = pd.DataFrame({"open_time": dates, "close": [100.0] * 10, "volume": [50_000.0] * 10})
    # close*volume = 5,000,000 USDT/día promedio > umbral 2,000,000

    # Símbolo con bajo volumen histórico real -> debe quedar excluido, SIN
    # importar que su ticker "de hoy" pudiera ser alto (no se consulta aquí).
    illiquid_df = pd.DataFrame({"open_time": dates, "close": [1.0] * 10, "volume": [100.0] * 10})
    # close*volume = 100 USDT/día << umbral

    daily_df_by_symbol = {"LIQUIDUSDT": liquid_df, "ILLIQUIDUSDT": illiquid_df}
    included, excluded = finalize_universe_with_historical_liquidity(
        daily_df_by_symbol, ["LIQUIDUSDT", "ILLIQUIDUSDT"]
    )
    assert "LIQUIDUSDT" in included
    assert "ILLIQUIDUSDT" not in included
    assert any(e.symbol == "ILLIQUIDUSDT" and e.stage == "liquidez_historica" for e in excluded)


def test_symbol_without_daily_coverage_is_documented_as_excluded_not_silently_dropped():
    included, excluded = finalize_universe_with_historical_liquidity({}, ["NODATAUSDT"])
    assert "NODATAUSDT" not in included
    assert len(excluded) == 1
    assert "Sin velas diarias" in excluded[0].reason
