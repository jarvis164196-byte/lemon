import numpy as np
import pytest
from PIL import Image, ImageCms

from lemon.imaging import validate_image
from lemon.planner import propose, validate_step


def test_curves_are_monotonic_and_bounded(pair):
    plan = propose(*pair, 1)
    values = np.array(plan[0]["arguments"]["values"])
    assert np.all(np.diff(values) >= 0)
    assert np.max(np.abs(values - np.linspace(0, 1, 256))) <= 0.180001
    assert len(plan) == 3
    for step in plan:
        validate_step(step)


def test_strength_and_parameters_reject_nan_and_arbitrary_tools(pair):
    for strength in [float("nan"), float("inf"), -1, 2]:
        with pytest.raises(ValueError):
            propose(*pair, strength)
    for step in [
        {"tool": "exec", "arguments": {"code": "print(1)"}},
        {"tool": "saturation", "arguments": {"amount": float("nan")}},
        {"tool": "color_balance", "arguments": {"cyan_red": 100, "magenta_green": 0, "yellow_blue": 0}},
    ]:
        with pytest.raises(ValueError):
            validate_step(step)


def test_identity_reference_proposes_identity_curve(pair):
    plan = propose(pair[0], pair[0], 0.5)
    assert np.allclose(plan[0]["arguments"]["values"], np.linspace(0, 1, 256), atol=1e-6)
    assert all(v == 0 for v in plan[1]["arguments"].values())
    assert plan[2]["arguments"]["amount"] == 0


def test_rejects_unsupported_input_modes(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (64, 64)).save(path)
    with pytest.raises(ValueError, match="8-bit RGB"):
        validate_image(path)


def test_accepts_explicit_srgb_profile(tmp_path):
    path = tmp_path / "srgb.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (64, 64)).save(path, icc_profile=profile)
    assert "sRGB" in validate_image(path)["profile"]


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientation_reports_upright_size_without_changing_input(tmp_path, orientation):
    path = tmp_path / "camera.jpg"
    exif = Image.Exif()
    exif[274] = orientation
    Image.new("RGB", (120, 80)).save(path, exif=exif)
    before = path.read_bytes()
    metadata = validate_image(path)
    assert (metadata["width"], metadata["height"]) == ((80, 120) if orientation >= 5 else (120, 80))
    assert metadata["orientation"] == orientation
    assert path.read_bytes() == before
