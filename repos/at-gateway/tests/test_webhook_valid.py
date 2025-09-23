from fastapi.testclient import TestClient
from at_gateway.app import app

def test_webhook_valid():
    c = TestClient(app)
    r = c.post("/webhook/tradingview", json={"instrument":"SI1!","price":"28.41","signal":"breakout_long","strength":0.72})
    assert r.status_code == 200
    assert "trace_id" in r.json()
