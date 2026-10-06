from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_reports_ok_and_synthetic_mode() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "synthetic"


def test_cors_allows_local_web_origin() -> None:
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin() -> None:
    res = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers
