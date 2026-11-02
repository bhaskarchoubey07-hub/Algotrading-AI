"""Test suite for DhanHQ market data verification suite and schema validation."""

import pytest
from app.brokers.dhan.market_data import DhanMarketDataManager, MockMarketDataProvider


def test_dhan_market_data_verify_connectivity_mock():
    """Verify that market data verify_connectivity runs and outputs valid schema."""
    mgr = DhanMarketDataManager()
    result = mgr.verify_connectivity(symbol="RELIANCE")

    assert "overall_status" in result
    assert result["overall_status"] in {"PASSED", "MOCK_VALIDATED"}
    assert result["schema_valid"] is True
    assert "quote_test" in result
    assert result["quote_test"]["ltp"] > 0
    assert result["historical_test"]["rows"] > 0
    assert result["data_source"] in {"mock", "dhan_live", "cached"}


def test_mock_provider_quote():
    """Verify MockMarketDataProvider delivers normalized BrokerQuote."""
    provider = MockMarketDataProvider()
    quote = provider.get_quote("INFY", "NSE_EQ")

    assert quote.symbol == "INFY"
    assert quote.last_price > 0
    assert quote.high_price >= quote.low_price
    assert quote.data_source == "mock"
    assert quote.is_stale is False


def test_mock_provider_historical_data():
    """Verify MockMarketDataProvider delivers formatted OHLCV DataFrame."""
    provider = MockMarketDataProvider()
    df = provider.get_historical_data("1333", "NSE_EQ", "EQUITY", "1D", "2026-01-01", "2026-02-01")

    assert not df.empty
    assert set(["timestamp", "open", "high", "low", "close", "volume"]).issubset(df.columns)
    assert len(df) == 30
