"""Bounded export options shared by the controller and tests."""


def export_settings(size, format="png", long_edge=None, quality=90, compression=6):
    if format not in {"png", "jpeg"}:
        raise ValueError("Choose PNG or JPEG.")
    if type(quality) is not int or not 1 <= quality <= 100:
        raise ValueError("JPEG quality must be 1–100.")
    if type(compression) is not int or not 0 <= compression <= 9:
        raise ValueError("PNG compression must be 0–9.")
    if long_edge is not None and (type(long_edge) is not int or not 64 <= long_edge <= 20000):
        raise ValueError("Long edge must be 64–20000 pixels.")
    ratio = min(1, long_edge / max(size)) if long_edge else 1
    return {
        "format": format,
        "size": [max(1, round(x * ratio)) for x in size],
        "quality": quality,
        "compression": compression,
    }
