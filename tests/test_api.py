from fastapi.testclient import TestClient

from llm_output_contract.api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "moderation" in body["contracts"]


def test_repair_endpoint_recovers():
    resp = client.post(
        "/repair",
        json={
            "contract": "moderation",
            "raw": "{'label': 'blocked', 'confidence': '0.8', 'reasons': []}",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["repaired_ok"] is True
    assert body["obj"]["label"] == "block"


def test_repair_unknown_contract_404():
    resp = client.post("/repair", json={"contract": "nope", "raw": "{}"})
    assert resp.status_code == 404
