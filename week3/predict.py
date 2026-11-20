"""Predict potholes in one image and draw bounding boxes with OpenCV."""
import argparse
from pathlib import Path

import cv2

from paceguard.perception.interface import load_model, predict_image
from paceguard.perception.visualize import draw_detections, read_bgr


def main():
    parser = argparse.ArgumentParser(description="YOLO26n pothole image prediction")
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    frame = read_bgr(args.image)
    model = load_model(args.weights)
    detections = predict_image(
        model, frame, conf=args.conf, imgsz=args.imgsz, device=args.device
    )
    annotated = draw_detections(frame, detections, {0: "pothole"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), annotated):
        raise OSError(f"failed to write {args.output}")
    print(f"detections={len(detections)} saved={args.output}")


if __name__ == "__main__":
    main()
