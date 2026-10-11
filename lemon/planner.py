"""A deterministic local planner, not a vision-language model or aesthetic score."""

import math

import numpy as np

from .imaging import pixels


def validate_step(step: dict) -> dict:
    tool, args = step.get("tool"), step.get("arguments", {})
    if tool == "curves":
        if set(args) != {"channel", "values"} or args["channel"] != "VALUE":
            raise ValueError("Only a value curve is supported.")
        values = args["values"]
        if not isinstance(values, list) or len(values) != 256:
            raise ValueError("A curve must contain 256 values.")
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in values):
            raise ValueError("Invalid curve values.")
        if any(a > b for a, b in zip(values, values[1:])):
            raise ValueError("Tone curves must be monotonic.")
    elif tool == "color_balance":
        if set(args) != {"cyan_red", "magenta_green", "yellow_blue"}:
            raise ValueError("Invalid color balance parameters.")
        if any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 20 for x in args.values()):
            raise ValueError("Color balance is limited to ±20.")
    elif tool == "saturation":
        value = args.get("amount")
        if (
            set(args) != {"amount"}
            or type(value) not in (int, float)
            or not math.isfinite(value)
            or abs(value) > 30
        ):
            raise ValueError("Saturation is limited to ±30.")
    else:
        raise ValueError("Unsupported native operation.")
    return step


def propose(source, reference, strength=0.55):
    if not math.isfinite(strength) or not 0.05 <= strength <= 1:
        raise ValueError("Strength must be between 0.05 and 1.")
    src, ref = pixels(source), pixels(reference)
    q = np.linspace(0.03, 0.97, 17)
    a, b = np.quantile(src.max(axis=1), q), np.quantile(ref.max(axis=1), q)
    x, index = np.unique(np.r_[0, a, 1], return_index=True)
    target = np.r_[0, b, 1][index]
    grid = np.linspace(0, 1, 256)
    target_curve = np.interp(grid, x, target)
    # Bound tonal movement to preserve detail on dissimilar scenes.
    curve = np.maximum.accumulate(grid + strength * np.clip(target_curve - grid, -0.18, 0.18))
    chroma_src = src - src.mean(axis=1, keepdims=True)
    chroma_ref = ref - ref.mean(axis=1, keepdims=True)
    shift = np.clip((np.median(chroma_ref, axis=0) - np.median(chroma_src, axis=0)) * 100 * strength, -20, 20)

    def saturation(rgb):
        return np.median((rgb.max(axis=1) - rgb.min(axis=1)) / np.maximum(rgb.max(axis=1), 0.01))

    sat = round(float(np.clip((saturation(ref) - saturation(src)) * 70 * strength, -30, 30)), 3)
    steps = [
        {
            "label": "Match light & contrast",
            "tool": "curves",
            "arguments": {"channel": "VALUE", "values": np.round(curve, 6).tolist()},
            "explanation": "Move the brightness distribution toward the reference with a bounded, monotonic tone curve.",
        },
        {
            "label": "Borrow the color mood",
            "tool": "color_balance",
            "arguments": dict(zip(["cyan_red", "magenta_green", "yellow_blue"], np.round(shift, 3).tolist())),
            "explanation": "Nudge midtone warmth and tint toward the reference while preserving luminosity.",
        },
        {
            "label": "Balance color intensity",
            "tool": "saturation",
            "arguments": {"amount": sat},
            "explanation": "Adjust global saturation toward the reference; review skin and clothing colors yourself.",
        },
    ]
    return [validate_step(step) for step in steps]
