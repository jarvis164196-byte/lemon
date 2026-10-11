import shutil

import pytest
from conftest import FakeAdapter
from fastapi.testclient import TestClient

from lemon.raw import develop
from lemon.server import create_app
from lemon.store import digest


def fake_developer(source, directory):
    directory.mkdir()
    copied = directory / ("input" + source.suffix.lower())
    shutil.copyfile(source, copied)
    output = directory / "developed.png"
    from PIL import Image

    Image.new("RGB", (64, 48), (90, 110, 120)).save(output)
    return output, {"decoder": "test-double", "output": "8-bit sRGB PNG"}


@pytest.mark.parametrize("role", ["source", "reference"])
def test_raw_upload_preserves_original_and_provenance(tmp_path, pair, monkeypatch, role):
    monkeypatch.setattr("lemon.store.develop", fake_developer)
    app = create_app(tmp_path / "data", token="secret", adapter=FakeAdapter())
    client = TestClient(app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://127.0.0.1:8765"})
    client.post("/api/session", headers={"Authorization": "Bearer secret"})
    files = {"source": ("source.png", pair[0].read_bytes()), "reference": ("ref.png", pair[1].read_bytes())}
    files[role] = ("../../private.CR2", b"fake RAW fixture")
    response = client.post("/api/projects", data={"name": "RAW test"}, files=files)
    assert response.status_code == 200, response.text
    state = response.json()
    record = state["inputs"][role]
    folder = app.state.controller.project(state["id"])
    original = folder / "inputs" / record["raw_original"]["file"]
    assert original.read_bytes() == b"fake RAW fixture"
    assert digest(original) == record["raw_original"]["sha256"]
    assert record["conversion"]["decoder"] == "test-double"
    assert record["orientation"] == 1
    assert state["nodes"][state["working_node_id"]]["healthy"]
    original.chmod(0o600)
    original.write_bytes(b"changed")
    with pytest.raises(ValueError, match="preserved input"):
        app.state.controller.verify_inputs(folder, state)


def test_invalid_raw_is_rejected_without_touching_input(tmp_path):
    source = tmp_path / "invalid.cr2"
    source.write_bytes(b"not raw data")
    with pytest.raises(ValueError, match="unsupported|damaged"):
        develop(source, tmp_path / "job")
    assert source.read_bytes() == b"not raw data"


def test_raw_failure_does_not_publish_project(controller, pair, monkeypatch):
    source = pair[0].with_suffix(".cr2")
    source.write_bytes(b"invalid")

    def fail(*args):
        raise ValueError("unsupported camera")

    monkeypatch.setattr("lemon.store.develop", fail)
    with pytest.raises(ValueError, match="unsupported"):
        controller.create("RAW fail", source, pair[1])
    assert controller.list_projects() == []


def test_raw_timeout_stops_and_reaps_private_process(tmp_path, monkeypatch):
    import signal
    import subprocess

    import lemon.raw as raw_module

    source = tmp_path / "input.cr2"
    source.write_bytes(b"fixture")
    calls = []

    class Process:
        pid = 12345

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired("decoder", timeout)
            return -9

    def spawn(*args, **kwargs):
        assert kwargs["start_new_session"] is True
        return Process()

    monkeypatch.setattr(raw_module.subprocess, "Popen", spawn)
    monkeypatch.setattr(raw_module.os, "killpg", lambda pid, sig: calls.append(("kill", pid, sig)))
    with pytest.raises(ValueError, match="stopped"):
        develop(source, tmp_path / "job", timeout=1)
    assert calls == [("wait", 1), ("kill", 12345, signal.SIGKILL), ("wait", None)]
    assert source.read_bytes() == b"fixture"
