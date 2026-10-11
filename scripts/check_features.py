"""Native integration with synthetic textures; no aesthetic quality claims."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from lemon.gimp import GimpAdapter
from lemon.store import Controller, digest

parser = argparse.ArgumentParser(
    description="Native GIMP retouch and export acceptance with synthetic fixtures"
)
parser.add_argument("--workspace", type=Path, required=True)
root = parser.parse_args().workspace.resolve()
root.mkdir(parents=True, exist_ok=True)
y, x = np.mgrid[:600, :800]
rng = np.random.default_rng(5)
a = np.clip(
    np.stack([x % 60 * 3 + 30, y % 60 * 3 + 30, (x + y) % 60 * 3 + 30], axis=-1)
    + rng.normal(0, 8, (600, 800, 3)),
    0,
    255,
).astype("uint8")
source = root / "source.png"
Image.fromarray(a).save(source)
original_hash = digest(source)
c = Controller(root / "projects", GimpAdapter(root / "runtime"))
s = c.create("Retouch acceptance fixture", source, source)
pid = s["id"]
nid = s["working_node_id"]
base = np.asarray(Image.open(c.asset(pid, "preview", nid)).convert("RGB"))
for kind in ["skin", "wrinkles", "reshape"]:
    p = c.retouch_preview(pid, nid, kind, [0.05, 0.1, 0.35, 0.6], 0.6)
    out = np.asarray(Image.open(c.asset(pid, "retouch", p["id"])).convert("RGB"))
    print(kind, "diff pixels", int(np.any(base != out, axis=2).sum()), flush=True)
    assert np.any(base[120:350, 80:270] != out[120:350, 80:270]), kind
    assert np.array_equal(base[:, 600:], out[:, 600:]), "Retouch escaped region"
    assert len(c.history(pid)["nodes"]) == 1
    if kind == "reshape":
        accepted = c.accept_retouch(pid, p["id"])
        assert len(accepted["nodes"]) == 2
print("All retouch previews localized; explicit accept committed", flush=True)
for fmt, quality, compression in [("jpeg", 35, 6), ("jpeg", 95, 6), ("png", 90, 0), ("png", 90, 9)]:
    r = c.export(pid, nid, format=fmt, long_edge=400, quality=quality, compression=compression)
    file = c.asset(pid, "export", r["export_id"])
    with Image.open(file) as im:
        assert im.size == (400, 300)
    print("export", fmt, quality, compression, file.stat().st_size, flush=True)
assert digest(source) == original_hash
print("PASS native retouch and export", flush=True)
