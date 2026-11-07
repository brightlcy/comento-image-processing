"""OpenCV BGR input and immutable overlays."""

from pathlib import Path
import cv2
import numpy as np
from .geometry import validate_xyxy


def validate_bgr(image):
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or image.size == 0
    ):
        raise ValueError("image must be nonempty HxWx3 uint8 BGR")


def read_bgr(path):
    try:
        image = cv2.imdecode(
            np.frombuffer(Path(path).read_bytes(), np.uint8), cv2.IMREAD_COLOR
        )
    except (OSError, cv2.error) as exc:
        raise ValueError(f"cannot read image: {path}") from exc
    validate_bgr(image)
    return image


def draw_detections(image, detections, names):
    validate_bgr(image)
    out = image.copy()
    h, w = out.shape[:2]
    for d in detections:
        x1, y1, x2, y2 = validate_xyxy(d.box_xyxy, w, h)
        if d.class_id not in names:
            raise ValueError("unknown detection class")
        cv2.rectangle(
            out,
            (int(x1), int(y1)),
            (min(w - 1, int(x2)), min(h - 1, int(y2))),
            (0, 255, 0),
            2,
        )
        label = f"{names[d.class_id]} {d.confidence:.2f} [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]"
        cv2.putText(
            out,
            label,
            (int(x1), max(12, int(y1) - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return out
