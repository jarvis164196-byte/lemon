"""Isolated LibRaw decoder. Pillow only encodes the developed RGB array as PNG."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageCms

from .imaging import MAX_PIXELS


def run(job):
    import rawpy

    with rawpy.imread(job["input"]) as raw:
        size = raw.sizes
        if size.raw_width * size.raw_height > MAX_PIXELS:
            raise ValueError("Use a RAW photo of at most 32 megapixels (including sensor borders).")
        rgb = raw.postprocess(
            use_camera_wb=True,
            use_auto_wb=False,
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=8,
            gamma=(2.4, 12.92),
            no_auto_bright=False,
        )
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.fromarray(rgb).save(job["output"], icc_profile=profile)
    return {
        "decoder": "LibRaw",
        "libraw_version": list(rawpy.libraw_version),
        "rawpy_version": rawpy.__version__,
        "output": "8-bit sRGB PNG",
        "white_balance": "camera",
        "auto_brightness": True,
        "gamma": [2.4, 12.92],
        "orientation": "camera orientation applied by LibRaw",
        "size": [rgb.shape[1], rgb.shape[0]],
    }


if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        result = {"ok": True, "conversion": run(json.loads(path.read_text()))}
    except ImportError:
        result = {"ok": False, "error": "RAW decoder is unavailable. Install Lemon dependencies (rawpy)."}
    except ValueError as exc:
        result = {"ok": False, "error": str(exc)}
    except Exception:
        result = {
            "ok": False,
            "error": "This RAW file is damaged or its camera/compression is unsupported by LibRaw.",
        }
    path.with_name("result.json").write_text(json.dumps(result))
