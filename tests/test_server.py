from conftest import FakeAdapter
from fastapi.testclient import TestClient

from lemon.server import create_app


def test_auth_origin_host_and_path_boundaries(tmp_path):
    app = create_app(tmp_path, token="test-secret", adapter=FakeAdapter())
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects", headers={"Host": "evil.test"}).status_code == 403
    assert client.post("/api/session", headers={"Authorization": "Bearer test-secret"}).status_code == 403
    assert (
        client.post(
            "/api/session", headers={"Authorization": "Bearer test-secret", "Origin": "http://evil.test"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/session", headers={"Authorization": "Bearer test-secret", "Origin": "http://127.0.0.1:8765"}
        ).status_code
        == 200
    )
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/projects", headers={"Origin": "http://evil.test"}).status_code == 403
    assert client.get("/api/projects/invalid").status_code == 400
    assert client.get("/").headers["content-security-policy"].find("frame-ancestors 'none'") >= 0


def test_upload_plan_and_explicit_approval(tmp_path, pair):
    app = create_app(tmp_path / "data", token="test-secret", adapter=FakeAdapter())
    client = TestClient(app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://127.0.0.1:8765"})
    client.post("/api/session", headers={"Authorization": "Bearer test-secret"})
    with pair[0].open("rb") as source, pair[1].open("rb") as reference:
        response = client.post(
            "/api/projects",
            data={"name": "My study"},
            files={"source": ("a.png", source, "image/png"), "reference": ("b.png", reference, "image/png")},
        )
    assert response.status_code == 200, response.text
    state = response.json()
    pid = state["id"]
    plan = client.post(f"/api/projects/{pid}/plans", json={"strength": 0.5}).json()
    assert len(client.get(f"/api/projects/{pid}").json()["nodes"]) == 1
    assert (
        client.post(
            f"/api/projects/{pid}/run",
            json={"plan_id": plan["id"], "plan_hash": "bad", "step_index": 0, "request_id": "a" * 32},
        ).status_code
        == 400
    )
