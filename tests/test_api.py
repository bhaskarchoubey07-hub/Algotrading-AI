from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_is_paper_only():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


def test_strategy_registry_endpoint():
    response = client.get("/strategies")
    assert response.status_code == 200
    assert {x["strategy_id"] for x in response.json()} == {"ema_trend", "rsi_mean_reversion", "donchian_breakout"}


def test_paper_order_endpoint_is_simulated():
    response = client.post("/paper/orders", json={"symbol": "RELIANCE", "side": "buy", "quantity": 1})
    assert response.status_code == 200
    assert response.json()["status"] == "SIMULATED"
