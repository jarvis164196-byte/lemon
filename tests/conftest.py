import json
from pathlib import Path

import pytest
from PIL import Image

from lemon.store import Controller


class FakeAdapter:
    """Controller test double only. Its bytes are not real GIMP integration evidence."""

    executable = "test-double"
    environment = None

    def __init__(self):
        self.calls = []
        self.fail = False

    def call(self, job):
        self.calls.append(job)
        if self.fail:
            raise RuntimeError("Injected save failure")
        if job["action"] == "discover":
            return {"version": "test-double"}
        if job["action"] in {"root", "edit"}:
            Path(job["checkpoint"]).write_text(json.dumps(job))
            Image.new("RGB", tuple(job["size"]), (90, 120, 140)).save(job["preview"])
        if job["action"] == "export":
            Image.new("RGB", tuple(job["size"]), (90, 120, 140)).save(job["output"])
        return {
            "reopened": True,
            "identity": job["identity"],
            "size": job["size"],
            "environment": {"version": "test-double"},
        }


@pytest.fixture
def pair(tmp_path):
    source, reference = tmp_path / "source.png", tmp_path / "reference.png"
    Image.new("RGB", (64, 48), (80, 110, 140)).save(source)
    Image.new("RGB", (64, 48), (130, 100, 70)).save(reference)
    return source, reference


@pytest.fixture
def controller(tmp_path):
    return Controller(tmp_path / "projects", FakeAdapter())


@pytest.fixture
def project(controller, pair):
    return controller.create("Test study", *pair)
