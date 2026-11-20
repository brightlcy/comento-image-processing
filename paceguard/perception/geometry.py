"""Validated normalized xywh and half-open pixel xyxy."""

import math


def validate_xyxy(box, width=None, height=None):
    if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
        raise ValueError("four finite coordinates required")
    x1, y1, x2, y2 = map(float, box)
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("invalid positive-area box")
    if width is not None and (x2 > width or y2 > height):
        raise ValueError("box outside image")
    return x1, y1, x2, y2


def bbox_xywh_to_xyxy(box, width, height):
    if not all(math.isfinite(float(v)) and v > 0 for v in (width, height)):
        raise ValueError("invalid image size")
    if len(box) != 4 or not all(math.isfinite(float(v)) and 0 <= v <= 1 for v in box):
        raise ValueError("invalid normalized xywh")
    x, y, w, h = map(float, box)
    return validate_xyxy(
        (
            (x - w / 2) * width,
            (y - h / 2) * height,
            (x + w / 2) * width,
            (y + h / 2) * height,
        ),
        width,
        height,
    )


def parse_yolo(line, nc, width, height):
    f = line.split()
    if len(f) != 5:
        raise ValueError("class and four xywh values required")
    c = int(f[0])
    if not 0 <= c < nc:
        raise ValueError("class outside class map")
    return c, bbox_xywh_to_xyxy(tuple(map(float, f[1:])), width, height)


def iou(a, b):
    ax, ay, az, at = validate_xyxy(a)
    bx, by, bz, bt = validate_xyxy(b)
    overlap = max(0, min(az, bz) - max(ax, bx)) * max(0, min(at, bt) - max(ay, by))
    area_a = (az - ax) * (at - ay)
    area_b = (bz - bx) * (bt - by)
    union = area_a + area_b - overlap
    if (
        not all(math.isfinite(v) for v in (area_a, area_b, overlap, union))
        or union <= 0
    ):
        raise ValueError("box area overflows or underflows floating-point range")
    return overlap / union
