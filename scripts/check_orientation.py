"""Real GIMP orientation regression using synthetic corner-color fixtures."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from lemon.gimp import GimpAdapter

parser = argparse.ArgumentParser(description="Check all eight EXIF transforms against native GIMP output.")
parser.add_argument("--workspace", type=Path, required=True)
root = parser.parse_args().workspace.resolve()
root.mkdir(parents=True, exist_ok=True)
a = GimpAdapter(root / "runtime")
arr = np.zeros((60, 100, 3), dtype="uint8")
arr[:30, :50] = [255, 0, 0]
arr[:30, 50:] = [0, 255, 0]
arr[30:, :50] = [0, 0, 255]
arr[30:, 50:] = [255, 255, 0]
for orientation in range(1, 9):
    source = root / f"in-{orientation}.png"
    dest = root / f"out-{orientation}.png"
    exif = Image.Exif()
    exif[274] = orientation
    Image.fromarray(arr).save(source, exif=exif)
    a.call({"action": "thumbnail", "input": str(source), "output": str(dest), "orientation": orientation})
    with Image.open(source) as im:
        expected = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
    with Image.open(dest) as im:
        actual = np.asarray(im.convert("RGB"))
    assert actual.shape == expected.shape, (orientation, actual.shape, expected.shape)
    assert np.max(np.abs(actual.astype(int) - expected.astype(int))) <= 1, orientation
    print("PASS native EXIF orientation", orientation, flush=True)
