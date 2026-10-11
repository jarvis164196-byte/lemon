from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from lemon.vision import VisionPlanner


class FakeVision:
    available = True
    model = "test-only"

    def __init__(self):
        self.calls = 0

    def propose(self, source, reference, strength, instruction):
        self.calls += 1
        from lemon.planner import propose

        return propose(source, reference, strength)


def test_no_vision_call_without_project_consent(controller, project):
    controller.vision = FakeVision()
    with pytest.raises(ValueError, match="permission"):
        controller.plan(project["id"], 0.5, "openai")
    assert controller.vision.calls == 0
    assert len(controller.history(project["id"])["nodes"]) == 1


def test_consent_is_project_scoped_and_revocable(controller, project, pair):
    other = controller.create("Other project", *pair)
    controller.vision = FakeVision()
    controller.consent(project["id"], True)
    with pytest.raises(ValueError, match="permission"):
        controller.plan(other["id"], 0.5, "openai")
    controller.consent(project["id"], False)
    with pytest.raises(ValueError, match="permission"):
        controller.plan(project["id"], 0.5, "openai")
    assert controller.vision.calls == 0


def test_approved_vision_records_submission_and_still_requires_edit_approval(controller, project):
    controller.vision = FakeVision()
    original_call = controller.adapter.call

    def call(job):
        if job["action"] == "thumbnail":
            Image.new("RGB", (64, 48), (150, 100, 70)).save(job["output"])
            return {"thumbnail": True}
        return original_call(job)

    controller.adapter.call = call
    controller.consent(project["id"], True)
    plan = controller.plan(project["id"], 0.5, "openai", "Warm sunset")
    assert plan["planner"] == "openai:test-only"
    assert controller.vision.calls == 1
    state = controller.history(project["id"])
    assert len(state["nodes"]) == 1
    assert state["vision_submissions"][0]["status"] == "completed"
    assert len(state["consent_events"]) == 1


def recipe():
    return {
        "tone": np.linspace(0, 1, 7).tolist(),
        "cyan_red": 5,
        "magenta_green": 0,
        "yellow_blue": -5,
        "saturation": -5,
        "tone_explanation": "Keep detail.",
        "color_explanation": "Warm midtones.",
        "saturation_explanation": "Soften color.",
    }


def install_response(monkeypatch, value, capture, status=200):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            capture.update(url=url, payload=json)
            return SimpleNamespace(
                status_code=status,
                json=lambda: {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": __import__("json").dumps(value)}],
                        }
                    ],
                },
            )

    monkeypatch.setattr("lemon.vision.httpx.Client", Client)


def test_provider_contract_is_bounded_no_store_and_fixed_destination(monkeypatch, pair):
    captured = {}
    install_response(monkeypatch, recipe(), captured)
    steps = VisionPlanner(api_key="test-key").propose(*pair, 0.5, "Gentle warmth")
    assert len(steps) == 3
    assert steps[1]["arguments"]["cyan_red"] == 2.5
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["payload"]["store"] is False
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert sum(p["type"] == "input_image" for p in captured["payload"]["input"][0]["content"]) == 2


def test_invalid_model_output_cannot_become_native_operation(monkeypatch, pair):
    for bad in [
        dict(recipe(), cyan_red=100),
        dict(recipe(), tone=[1, 0, 0, 0, 0, 0, 0]),
        dict(recipe(), code="exec"),
    ]:
        install_response(monkeypatch, bad, {})
        with pytest.raises(ValueError):
            VisionPlanner(api_key="test-key").propose(*pair, 0.5, "")


def test_provider_error_does_not_echo_secrets(monkeypatch, pair):
    install_response(monkeypatch, {}, {}, status=401)
    with pytest.raises(ValueError, match="HTTP 401") as error:
        VisionPlanner(api_key="sensitive-test-key").propose(*pair, 0.5, "")
    assert "sensitive-test-key" not in str(error.value)
