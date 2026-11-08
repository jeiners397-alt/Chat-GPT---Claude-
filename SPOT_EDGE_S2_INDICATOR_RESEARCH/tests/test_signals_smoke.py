"""Prueba de humo: todas las señales implementadas deben ejecutarse sin error
sobre datos sintéticos y devolver una Serie booleana alineada al índice."""

import pandas as pd
import pytest

from src.indicators.signals import REGISTRY_FUNCTIONS
from tests.conftest import make_synthetic_df


@pytest.mark.parametrize("name", list(REGISTRY_FUNCTIONS.keys()))
def test_signal_function_runs_and_returns_boolean_series(name):
    df = make_synthetic_df(seed=hash(name) % 1000)
    fn = REGISTRY_FUNCTIONS[name]
    btc_close = df.set_index("open_time")["close"]
    result = fn(df, btc_close=btc_close)
    assert isinstance(result, pd.Series)
    assert len(result) == len(df)
    non_null = result.dropna()
    assert set(non_null.unique()).issubset({True, False})


def test_signal_never_uses_future_close_naively():
    """Prueba de no-look-ahead indirecta: si se trunca el DataFrame a los
    primeros N registros, la señal en la posición N-1 debe ser idéntica a la
    que se obtiene evaluando la serie completa (el resultado en un punto no
    puede depender de datos posteriores a ese punto)."""
    df_full = make_synthetic_df(seed=7, n=300)
    cutoff = 250
    df_truncated = df_full.iloc[: cutoff + 1].reset_index(drop=True)

    from src.indicators.signals import sig_rsi_recovery, sig_donchian_breakout, sig_obv_breakout

    for fn in (sig_rsi_recovery, sig_donchian_breakout, sig_obv_breakout):
        sig_full = fn(df_full)
        sig_trunc = fn(df_truncated)
        val_full = bool(sig_full.iloc[cutoff]) if pd.notna(sig_full.iloc[cutoff]) else False
        val_trunc = bool(sig_trunc.iloc[cutoff]) if pd.notna(sig_trunc.iloc[cutoff]) else False
        assert val_full == val_trunc, f"{fn.__name__} parece usar información futura"
