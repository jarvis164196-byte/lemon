"""Trusted batch worker. Invoked only by the controller in an isolated GIMP process."""

import json
import os
import traceback
from pathlib import Path

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, Gimp, Gio  # noqa: E402


def discover():
    names = [
        "gimp-xcf-save",
        "file-png-export",
        "file-jpeg-export",
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
        "orientation_api": {
            "rotate": Gimp.Image.rotate.__doc__,
            "flip": Gimp.Image.flip.__doc__,
            "enums": {
                name: str(getattr(Gimp, name).__enum_values__)
                for name in dir(Gimp)
                if name in {"RotationType", "OrientationType"}
            },
        },
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


def export_png(image, path, options=None):
    options = options or {"format": "png", "compression": 6}
    proc = Gimp.get_pdb().lookup_procedure(
        "file-jpeg-export" if options["format"] == "jpeg" else "file-png-export"
    )
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
    if options["format"] == "jpeg":
        config.set_property("quality", options["quality"] / 100)
    else:
        config.set_property("compression", options["compression"])
    result = proc.run(config)
    if result.index(0) != Gimp.PDBStatusType.SUCCESS:
        raise RuntimeError("GIMP image export failed.")


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
    if job["action"] in {"root", "thumbnail"}:
        # GIMP noninteractive loads retain the stored pixel orientation. Apply EXIF once.
        orientation = job.get("orientation", 1)
        if orientation not in range(1, 9):
            raise RuntimeError("Invalid input orientation.")
        if orientation in {2, 5, 7}:
            if not image.flip(Gimp.OrientationType(0)):
                raise RuntimeError("Native orientation flip failed.")
        elif orientation == 4:
            if not image.flip(Gimp.OrientationType(1)):
                raise RuntimeError("Native orientation flip failed.")
        rotation = {3: 1, 5: 2, 6: 0, 7: 0, 8: 2}.get(orientation)
        if rotation is not None and not image.rotate(Gimp.RotationType(rotation)):
            raise RuntimeError("Native orientation rotation failed.")
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
        if step["tool"] == "retouch":
            x, y, w, h = args["region"]
            x, w = x * size[0], w * size[0]
            y, h = y * size[1], h * size[1]
            image.select_ellipse(Gimp.ChannelOps.REPLACE, x, y, w, h)
            Gimp.Selection.feather(image, max(1, min(w, h) * 0.12))
            amount = args["amount"]
            if args["kind"] == "skin":
                op, params = (
                    "gegl:bilateral-filter",
                    {"blur-radius": 2 + 12 * amount, "edge-preservation": 8.0},
                )
            elif args["kind"] == "wrinkles":
                op, params = "gegl:gaussian-blur", {"std-dev-x": 2 + 8 * amount, "std-dev-y": 2 + 8 * amount}
            else:
                op, params = "gegl:whirl-pinch", {"whirl": 0.0, "pinch": amount * 0.4, "radius": 1.0}
            effect = Gimp.DrawableFilter.new(layer, op, step["label"])
            config = effect.get_config()
            for key, value in params.items():
                config.set_property(key, value)
            effect.set_opacity(1.0 if args["kind"] == "reshape" else amount)
            effect.update()
            layer.merge_filter(effect)
            Gimp.Selection.none(image)
            ok = True
        elif step["tool"] == "curves":
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
        options = job.get("export", {"format": "png", "size": size, "compression": 6})
        if options["size"] != size:
            image.scale(*options["size"])
        if options["format"] == "jpeg":
            Gimp.context_set_background(Gegl.Color.new("white"))
            image.flatten()
        export_png(image, job["output"], options)
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
