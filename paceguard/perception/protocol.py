"""One explicit protocol for validation, selection and final test authorization."""


def evaluation_protocol():
    return {
        "schema_version": 1,
        "ap": dict(
            imgsz=640,
            batch=8,
            conf=0.001,
            iou=0.7,
            max_det=300,
            device="cpu",
            workers=0,
            rect=False,
            half=False,
            augment=False,
            plots=True,
            save_json=False,
        ),
        "diagnostic": dict(
            imgsz=640,
            confidence=0.25,
            matching_iou=0.5,
            small_gt_area_pixels_less_than=1024,
            device="cpu",
            iou=0.7,
            max_det=300,
            rect=False,
            half=False,
            augment=False,
        ),
    }
