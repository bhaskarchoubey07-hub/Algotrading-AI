import os
import pytest
from app.paper import PaperBroker, PaperOrder


def test_paper_broker_place_order_and_fill(tmp_path):
    state_file = str(tmp_path / "paper_test_state.json")
    broker = PaperBroker(initial_cash=500_000.0, state_file=state_file)

    order = broker.place_order("RELIANCE", "buy", 10, price=2800.0)
    assert order.status == "SIMULATED"
    assert order.fill_price > 0
    assert order.fees > 0
    assert "RELIANCE" in broker.positions
    assert broker.positions["RELIANCE"].quantity == 10

    # Available cash decreased by order cost + fees
    assert broker.cash_balance < 500_000.0


def test_paper_broker_automated_stop_loss(tmp_path):
    state_file = str(tmp_path / "paper_sl_state.json")
    broker = PaperBroker(initial_cash=500_000.0, state_file=state_file)

    broker.place_order("TCS", "buy", 5, price=4000.0, stop_loss=3900.0)
    assert "TCS" in broker.positions

    # Market price drops below stop loss
    triggered = broker.update_market_price("TCS", 3890.0)
    assert len(triggered) == 1
    assert "STOP_LOSS executed" in triggered[0]
    assert "TCS" not in broker.positions


def test_paper_broker_close_position(tmp_path):
    state_file = str(tmp_path / "paper_close_state.json")
    broker = PaperBroker(initial_cash=500_000.0, state_file=state_file)

    broker.place_order("INFY", "buy", 20, price=1700.0)
    assert "INFY" in broker.positions

    res = broker.close_position("INFY", exit_price=1750.0)
    assert res is not None
    assert "INFY" not in broker.positions
    assert broker.realized_pnl > 0


def test_paper_broker_state_persistence(tmp_path):
    state_file = str(tmp_path / "paper_persist_state.json")
    broker1 = PaperBroker(initial_cash=500_000.0, state_file=state_file)
    broker1.place_order("TATAMOTORS", "buy", 50, price=950.0)
    assert os.path.exists(state_file)

    # Instantiate new broker loading same state
    broker2 = PaperBroker(initial_cash=500_000.0, state_file=state_file)
    assert "TATAMOTORS" in broker2.positions
    assert broker2.positions["TATAMOTORS"].quantity == 50
