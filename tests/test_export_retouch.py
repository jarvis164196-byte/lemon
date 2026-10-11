import pytest

from lemon.exporting import export_settings
from lemon.planner import validate_step


def test_export_resize_preserves_aspect_and_never_upscales():
    assert export_settings([3648, 5472], long_edge=2048)["size"] == [1365, 2048]
    assert export_settings([100, 60], long_edge=2048)["size"] == [100, 60]
    for kwargs in [{"format": "webp"}, {"quality": 101}, {"compression": 10}, {"long_edge": True}]:
        with pytest.raises(ValueError):
            export_settings([800, 600], **kwargs)


def test_export_options_and_legacy_assets(controller, project):
    pid, nid = project["id"], project["working_node_id"]
    result = controller.export(pid, nid, format="jpeg", long_edge=64, quality=70)
    assert result["settings"]["size"] == [64, 48]
    assert controller.asset(pid, "export", result["export_id"]).suffix == ".jpg"
    assert controller.history(pid)["working_node_id"] == nid


def test_retouch_preview_is_not_committed_and_accept_is_idempotent(controller, project):
    pid, nid = project["id"], project["working_node_id"]
    preview = controller.retouch_preview(pid, nid, "skin", [0.1, 0.1, 0.3, 0.4], 0.3)
    assert controller.history(pid)["working_node_id"] == nid
    assert len(controller.history(pid)["nodes"]) == 1
    assert controller.asset(pid, "retouch", preview["id"]).is_file()
    accepted = controller.accept_retouch(pid, preview["id"])
    assert len(accepted["nodes"]) == 2
    assert accepted["working_node_id"] != nid
    assert controller.accept_retouch(pid, preview["id"])["working_node_id"] == accepted["working_node_id"]


def test_retouch_rejects_stale_or_corrupted_preview(controller, project):
    pid, nid = project["id"], project["working_node_id"]
    preview = controller.retouch_preview(pid, nid, "wrinkles", [0.1, 0.1, 0.3, 0.4], 0.3)
    controller.restore(pid, nid)
    with pytest.raises(ValueError, match="stale"):
        controller.accept_retouch(pid, preview["id"])
    preview = controller.retouch_preview(pid, nid, "reshape", [0.1, 0.1, 0.3, 0.4], 0.3)
    path = controller.asset(pid, "retouch", preview["id"])
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="changed"):
        controller.accept_retouch(pid, preview["id"])
    assert len(controller.history(pid)["nodes"]) == 1


def test_retouch_bounds_and_failed_preview(controller, project):
    for region in [[-0.1, 0, 0.5, 0.5], [0, 0, 1.2, 0.5], [0, 0, 0, 0.5], [float("nan"), 0, 0.5, 0.5]]:
        with pytest.raises(ValueError):
            validate_step({"tool": "retouch", "arguments": {"kind": "skin", "region": region, "amount": 0.3}})
    controller.adapter.fail = True
    with pytest.raises(RuntimeError):
        controller.retouch_preview(
            project["id"], project["working_node_id"], "skin", [0.1, 0.1, 0.3, 0.4], 0.3
        )
    state = controller.history(project["id"])
    assert len(state["nodes"]) == 1
    assert state["session_status"] == "ready"


def test_feature_api_approval_and_export(tmp_path, pair):
    from conftest import FakeAdapter
    from fastapi.testclient import TestClient

    from lemon.server import create_app

    app = create_app(tmp_path, token="test-secret", adapter=FakeAdapter())
    client = TestClient(app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://127.0.0.1:8765"})
    client.post("/api/session", headers={"Authorization": "Bearer test-secret"})
    project = app.state.controller.create("Feature test", *pair)
    pid, nid = project["id"], project["working_node_id"]
    result = client.post(
        f"/api/projects/{pid}/exports",
        json={"node_id": nid, "format": "jpeg", "long_edge": 64, "quality": 75},
    )
    assert result.status_code == 200, result.text
    asset = client.get(f"/api/projects/{pid}/assets/export", params={"asset_id": result.json()["export_id"]})
    assert asset.headers["content-type"] == "image/jpeg"
    assert "lemon.jpg" in asset.headers["content-disposition"]
    assert (
        client.post(f"/api/projects/{pid}/exports", json={"node_id": nid, "quality": 101}).status_code == 422
    )
    result = client.post(
        f"/api/projects/{pid}/retouches",
        json={"node_id": nid, "kind": "skin", "region": [0.1, 0.1, 0.3, 0.4], "amount": 0.3},
    )
    assert result.status_code == 200, result.text
    candidate_id = result.json()["id"]
    assert (
        client.get(f"/api/projects/{pid}/assets/retouch", params={"asset_id": candidate_id}).status_code
        == 200
    )
    assert len(client.get(f"/api/projects/{pid}").json()["nodes"]) == 1
    accepted = client.post(f"/api/projects/{pid}/retouches/accept", json={"candidate_id": candidate_id})
    assert len(accepted.json()["nodes"]) == 2
