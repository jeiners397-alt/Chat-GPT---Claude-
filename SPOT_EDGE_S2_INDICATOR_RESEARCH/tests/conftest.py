import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest


def make_synthetic_df(seed=0, n=400, freq="1h", trend=0.0, tz="UTC", start="2026-01-01"):
    rng = np.random.RandomState(seed)
    dates = pd.date_range(start, periods=n, freq=freq, tz=tz)
    price = 100 * np.exp(np.cumsum(rng.normal(trend, 0.01, n)))
    high = price * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = price * (1 - np.abs(rng.normal(0, 0.003, n)))
    open_ = price * (1 + rng.normal(0, 0.001, n))
    volume = np.abs(rng.normal(1000, 200, n))
    taker_buy = volume * rng.uniform(0.3, 0.7, n)
    return pd.DataFrame(
        {
            "open_time": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": price,
            "volume": volume,
            "taker_buy_base_volume": taker_buy,
        }
    )


@pytest.fixture
def synthetic_df():
    return make_synthetic_df(seed=1)
