"""Verifica que la selección de universo documente TODAS las exclusiones
(sección 2 del encargo) y no seleccione sólo activos con ganancias."""

from src.universe import build_universe


class _FakeClient:
    def __init__(self, exchange_info, tickers):
        self._exchange_info = exchange_info
        self._tickers = tickers

    def get_exchange_info(self):
        return self._exchange_info

    def get_24h_tickers(self):
        return self._tickers


def _symbol_entry(symbol, base, quote="USDT", status="TRADING", spot=True):
    return {"symbol": symbol, "baseAsset": base, "quoteAsset": quote, "status": status, "isSpotTradingAllowed": spot}


def test_excludes_leveraged_tokens_and_documents_reason():
    exchange_info = {
        "symbols": [
            _symbol_entry("BTCUSDT", "BTC"),
            _symbol_entry("BTCUPUSDT", "BTCUP"),
        ]
    }
    tickers = [
        {"symbol": "BTCUSDT", "quoteVolume": "50000000"},
        {"symbol": "BTCUPUSDT", "quoteVolume": "50000000"},
    ]
    client = _FakeClient(exchange_info, tickers)
    included, exclusions = build_universe(client)
    assert "BTCUSDT" in included
    assert "BTCUPUSDT" not in included
    reasons = {e.symbol: e.reason for e in exclusions}
    assert "apalancado" in reasons["BTCUPUSDT"].lower()


def test_excludes_low_liquidity_and_documents_reason():
    exchange_info = {"symbols": [_symbol_entry("LOWUSDT", "LOW")]}
    tickers = [{"symbol": "LOWUSDT", "quoteVolume": "100"}]
    client = _FakeClient(exchange_info, tickers)
    included, exclusions = build_universe(client)
    assert "LOWUSDT" not in included
    assert any("Liquidez" in e.reason for e in exclusions)


def test_does_not_filter_by_recent_performance():
    """El filtro de universo no debe usar variación de precio/ganancia como
    criterio (evitar sesgo de supervivencia hacia ganadores recientes)."""
    exchange_info = {"symbols": [_symbol_entry("ANYUSDT", "ANY")]}
    tickers = [{"symbol": "ANYUSDT", "quoteVolume": "50000000", "priceChangePercent": "-40.0"}]
    client = _FakeClient(exchange_info, tickers)
    included, _ = build_universe(client)
    assert "ANYUSDT" in included  # cae con -40% y aun así es admitido por liquidez


def test_non_spot_and_non_trading_excluded():
    exchange_info = {
        "symbols": [
            _symbol_entry("A_USDT", "A", spot=False),
            _symbol_entry("B_USDT", "B", status="BREAK"),
        ]
    }
    tickers = [
        {"symbol": "A_USDT", "quoteVolume": "50000000"},
        {"symbol": "B_USDT", "quoteVolume": "50000000"},
    ]
    client = _FakeClient(exchange_info, tickers)
    included, exclusions = build_universe(client)
    assert included == []
    assert len(exclusions) == 2
