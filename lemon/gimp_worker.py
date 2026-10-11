"""Trusted batch worker. Invoked only by the controller in an isolated GIMP process."""

import json
import os
import traceback
from pathlib import Path

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio  # noqa: E402


def discover():
    names = [
        "gimp-xcf-save",
        "file-png-export",
        "gimp-drawable-curves-explicit",
        "gimp-drawable-color-balance",
        "gimp-drawable-hue-saturation",
    ]
    schemas = {}
    for name in names:
        proc = Gimp.get_pdb().lookup_procedure(name)
        if proc is None:
            raise RuntimeError("Required GIMP procedure unavailable: " + name)
        schemas[name] = [
            {"name": p.name, "type": p.value_type.name} for p in proc.create_config().list_properties()
        ]
    return {
        "version": Gimp.version(),
        "procedures": schemas,
        "signatures": {
            name: getattr(Gimp.Drawable, name).__doc__
            for name in ["curves_explicit", "color_balance", "hue_saturation"]
        },
    }


def load(path):
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(str(path)))
    if image is None:
        raise RuntimeError("GIMP could not load the image.")
    return image


def save(image, path):
    if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(str(path)), None):
        raise RuntimeError("GIMP could not save the image.")


def export_png(image, path):
    proc = Gimp.get_pdb().lookup_procedure("file-png-export")
    config = proc.create_config()
    for key, value in {
        "run-mode": Gimp.RunMode.NONINTERACTIVE,
        "image": image,
        "file": Gio.File.new_for_path(str(path)),
        "include-exif": False,
        "include-iptc": False,
        "include-xmp": False,
        "include-thumbnail": False,
        "include-comment": False,
        "include-color-profile": True,
    }.items():
        config.set_property(key, value)
    result = proc.run(config)
    if result.index(0) != Gimp.PDBStatusType.SUCCESS:
        raise RuntimeError("GIMP PNG export failed.")


def identity(image, token):
    parasite = image.get_parasite("lemon-identity")
    if parasite is None or bytes(parasite.get_data()).decode() != token:
        raise RuntimeError("Checkpoint document identity does not match this project.")
    layers = image.get_layers()
    if len(layers) != 1 or layers[0].get_name() != "Lemon working layer":
        raise RuntimeError("Managed layer is missing or ambiguous.")
    return layers[0]


def run(job):
    environment = discover()
    if job["action"] == "discover":
        return environment
    image = load(job["input"])
    if job["action"] == "thumbnail":
        width, height = image.get_width(), image.get_height()
        ratio = min(1, 1400 / max(width, height))
        if ratio < 1:
            image.scale(round(width * ratio), round(height * ratio))
        export_png(image, job["output"])
        image.delete()
        return {"environment": environment, "thumbnail": True}
    if job["action"] == "root":
        if len(image.get_layers()) != 1:
            raise RuntimeError("Only single-layer photos are supported.")
        image.get_layers()[0].set_name("Lemon working layer")
        image.attach_parasite(Gimp.Parasite.new("lemon-identity", 1, job["identity"].encode()))
    layer = identity(image, job["identity"])
    size = [image.get_width(), image.get_height()]
    if size != job["size"]:
        raise RuntimeError("Checkpoint dimensions do not match the source.")
    if job["action"] == "edit":
        step = job["step"]
        args = step["arguments"]
        if step["tool"] == "curves":
            ok = layer.curves_explicit(Gimp.HistogramChannel.VALUE, args["values"])
        elif step["tool"] == "color_balance":
            ok = layer.color_balance(
                Gimp.TransferMode.MIDTONES, True, args["cyan_red"], args["magenta_green"], args["yellow_blue"]
            )
        elif step["tool"] == "saturation":
            ok = layer.hue_saturation(Gimp.HueRange.ALL, 0, 0, args["amount"], 0)
        else:
            raise RuntimeError("Native operation is not allowlisted.")
        if not ok:
            raise RuntimeError("Native adjustment failed.")
    if job["action"] in {"root", "edit"}:
        save(image, job["checkpoint"])
        image.delete()
        # Rebind by durable identity; never reuse a runtime image/layer ID.
        image = load(job["checkpoint"])
        identity(image, job["identity"])
        if [image.get_width(), image.get_height()] != size:
            raise RuntimeError("Saved checkpoint dimensions changed.")
        preview = image.duplicate()
        width, height = size
        ratio = min(1, 1400 / max(size))
        if ratio < 1:
            preview.scale(round(width * ratio), round(height * ratio))
        export_png(preview, job["preview"])
        preview.delete()
    elif job["action"] == "export":
        export_png(image, job["output"])
    elif job["action"] != "verify":
        raise RuntimeError("Unknown worker action.")
    image.delete()
    return {"environment": environment, "size": size, "identity": job["identity"], "reopened": True}


if __name__ == "__main__":
    job_path = Path(os.environ["LEMON_JOB"])
    result_path = job_path.with_name("result.json")
    try:
        result = {"ok": True, "result": run(json.loads(job_path.read_text()))}
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
    result_path.write_text(json.dumps(result))
