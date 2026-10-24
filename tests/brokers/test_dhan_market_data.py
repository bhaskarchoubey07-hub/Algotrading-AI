"""Tests for DhanMarketDataManager, Quote Freshness, and Staleness Detection."""

from datetime import datetime, timedelta, timezone
import pytest
from app.brokers.base import BrokerQuote
from app.brokers.dhan.exceptions import DhanStaleDataError
from app.brokers.dhan.market_data import DhanMarketDataManager


def test_dhan_market_data_get_quote_sandbox():
    md = DhanMarketDataManager()
    quote = md.get_quote("RELIANCE", exchange_segment="NSE_EQ")
    assert quote.symbol == "RELIANCE"
    assert quote.last_price > 0
    assert quote.is_stale is False
    assert quote.security_id == "2885"


def test_dhan_market_data_staleness_detection():
    md = DhanMarketDataManager(max_stale_seconds=30.0)

    # Fresh quote passes
    fresh_quote = BrokerQuote(
        symbol="TCS",
        security_id="11536",
        exchange_segment="NSE_EQ",
        last_price=4100.0,
        open_price=4080.0,
        high_price=4120.0,
        low_price=4070.0,
        close_price=4100.0,
        volume=50000,
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_stale=False,
    )
    # Should not raise
    md.validate_data_freshness(fresh_quote)

    # Stale quote (5 minutes old) must raise DhanStaleDataError
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    stale_quote = BrokerQuote(
        symbol="TCS",
        security_id="11536",
        exchange_segment="NSE_EQ",
        last_price=4100.0,
        open_price=4080.0,
        high_price=4120.0,
        low_price=4070.0,
        close_price=4100.0,
        volume=50000,
        timestamp=old_time,
        is_stale=False,
    )
    with pytest.raises(DhanStaleDataError) as exc_info:
        md.validate_data_freshness(stale_quote)
    assert "old" in str(exc_info.value).lower() or "expired" in str(exc_info.value).lower()


def test_dhan_market_data_historical_daily():
    md = DhanMarketDataManager()
    df = md.get_historical_daily("INFY", from_date="2026-01-01", to_date="2026-01-31")
    assert not df.empty
    assert "timestamp" in df.columns
    assert "open" in df.columns
    assert "high" in df.columns
    assert "low" in df.columns
    assert "close" in df.columns
    assert "volume" in df.columns


def test_dhan_market_data_intraday_minute():
    md = DhanMarketDataManager()
    df = md.get_intraday_minute("HDFCBANK", from_date="2026-10-23", to_date="2026-10-23", interval=5)
    assert not df.empty
    assert len(df) > 10
    assert "close" in df.columns
