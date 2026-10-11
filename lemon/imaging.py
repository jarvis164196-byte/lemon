"""Read-only input validation and statistics. All output pixels come from GIMP."""

import io
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

MAX_BYTES = 40 * 1024 * 1024
MAX_PIXELS = 32_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def validate_image(path: Path, max_bytes=MAX_BYTES) -> dict:
    try:
        return _validate_image(path, max_bytes)
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError(
            "The image is damaged, too large, or unsupported. Use an 8-bit sRGB JPEG or PNG."
        ) from None


def _validate_image(path: Path, max_bytes) -> dict:
    if path.stat().st_size > max_bytes:
        raise ValueError("Photos must be smaller than 40 MB.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as im:
            if im.format not in {"JPEG", "PNG"} or im.mode not in {"RGB", "RGBA"}:
                raise ValueError(
                    "Use an 8-bit RGB sRGB JPEG or PNG. RAW, grayscale and indexed images are unsupported."
                )
            if im.width * im.height > MAX_PIXELS or getattr(im, "n_frames", 1) != 1:
                raise ValueError("Use a single photo of at most 32 megapixels.")
            with path.open("rb") as header_file:
                header = header_file.read(25)
            if im.format == "PNG" and header[24] != 8:
                raise ValueError("16-bit PNG is not supported yet. Export an 8-bit sRGB copy.")
            if im.getexif().get(274, 1) != 1:
                raise ValueError(
                    "Apply the photo's orientation before importing (export an upright sRGB copy)."
                )
            profile = im.info.get("icc_profile")
            if profile:
                description = ImageCms.getProfileDescription(
                    ImageCms.ImageCmsProfile(io.BytesIO(profile))
                ).strip()
                if "srgb" not in description.lower().replace(" ", ""):
                    raise ValueError(
                        "Only sRGB profiles are supported. Convert a copy to sRGB before importing."
                    )
            else:
                description = "Untagged; interpreted as sRGB"
            if any(k in im.info for k in ("cicp", "hdr")):
                raise ValueError("HDR-tagged inputs are not supported.")
            metadata = {"width": im.width, "height": im.height, "format": im.format, "profile": description}
        with Image.open(path) as verification:
            verification.verify()
    return metadata


def pixels(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        # Sampling for analysis only: no image is written or used as an edited preview.
        im.thumbnail((512, 512))
        values = np.asarray(im.convert("RGBA"), dtype=float).reshape(-1, 4)
        rgb = values[values[:, 3] > 250, :3] / 255
        if len(rgb) < 64:
            raise ValueError("The photo needs at least 64 opaque pixels for reference analysis.")
        return rgb
