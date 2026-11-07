"""Reusable image inference. Video scheduling is deferred to Week 4."""

from dataclasses import dataclass
import math
from pathlib import Path
import numpy as np
from .geometry import validate_xyxy
from .visualize import validate_bgr


@dataclass(frozen=True)
class Detection:
    box_xyxy: tuple[float, float, float, float]
    class_id: int
    confidence: float
    frame_id: int

    def __post_init__(self):
        validate_xyxy(self.box_xyxy)
        if (
            type(self.class_id) is not int
            or self.class_id < 0
            or type(self.frame_id) is not int
            or self.frame_id < 0
        ):
            raise ValueError("nonnegative integer identifiers required")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("invalid confidence")


@dataclass(frozen=True)
class Frame:
    frame_id: int
    capture_ts: float
    image: np.ndarray

    def __post_init__(self):
        validate_bgr(self.image)
        if (
            type(self.frame_id) is not int
            or self.frame_id < 0
            or not math.isfinite(self.capture_ts)
            or self.capture_ts < 0
        ):
            raise ValueError("invalid capture timestamp/frame")


@dataclass(frozen=True)
class RiskAssessment:
    status: str
    reasons: tuple[str, ...]
    assumptions: tuple[str, ...] = ()


def assess_without_calibration(detections):
    reasons = ["metric_distance_unavailable", "camera_and_path_calibration_unavailable"]
    if not detections:
        reasons.append("no_detection_is_not_safety_evidence")
    return RiskAssessment("UNKNOWN", tuple(reasons))


def load_model(weights):
    weights = Path(weights)
    if not weights.is_file():
        raise FileNotFoundError(weights)
    from ultralytics import YOLO

    return YOLO(str(weights))


def predict_image(model, image, *, frame_id=0, imgsz=640, conf=0.25, device="cpu"):
    validate_bgr(image)
    if type(frame_id) is not int or frame_id < 0:
        raise ValueError("invalid frame id")
    if (
        type(imgsz) is not int
        or imgsz <= 0
        or not math.isfinite(conf)
        or not 0 <= conf <= 1
    ):
        raise ValueError("invalid prediction arguments")
    results = model.predict(
        source=image,
        imgsz=imgsz,
        conf=conf,
        iou=0.7,
        max_det=300,
        rect=False,
        device=device,
        verbose=False,
        half=False,
        augment=False,
    )
    ds = []
    for r in results:
        if r.boxes is None:
            continue
        for box, cls, c in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf, strict=True):
            box = tuple(float(v) for v in box)
            validate_xyxy(box, image.shape[1], image.shape[0])
            ds.append(Detection(box, int(cls), float(c), frame_id))
    return tuple(ds)
