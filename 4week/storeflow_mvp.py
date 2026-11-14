#!/usr/bin/env python3
"""StoreFlow MVP: people tracking, zone dwell, movement direction, possible exits.

Usage (from the project root):
    python storeflow_mvp.py
    python storeflow_mvp.py --input samples/storeflow_crowd_candidate.mp4
    python storeflow_mvp.py --input samples/input.mp4 --zone 'COUNTER:0.05,0.1,0.45,0.9' --zone 'SEATS:0.5,0.1,0.95,0.9'

Important: directions and exits are estimations, not validated entry/exit events.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2


DEFAULT_INPUTS = (
    "samples/storeflow_crowd_candidate.mp4",
    "samples/storeflow_retail_candidate.mp4",
    "samples/retail_site03/preview/C0001056_v2.mp4",
    "samples/storeflow_shop.mp4",
    "outputs/storeflow_mall.mp4",
)


@dataclass(frozen=True)
class Zone:
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, nx: float, ny: float) -> bool:
        return self.x1 <= nx < self.x2 and self.y1 <= ny < self.y2


def parse_zone(spec: str) -> Zone:
    try:
        name, coords = spec.split(":", 1)
        parts = [float(part) for part in coords.split(",")]
        if not name.strip() or len(parts) != 4:
            raise ValueError
        x1, y1, x2, y2 = parts
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError
        return Zone(name.strip().upper(), x1, y1, x2, y2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "구역 형식: NAME:x1,y1,x2,y2 (0~1), 예: COUNTER:0.1,0.2,0.4,0.8"
        ) from exc


def default_zones() -> list[Zone]:
    # Temporary spatial regions; NOT actual counter/seating/entrance labels.
    return [
        Zone("LEFT", 0.0, 0.0, 1 / 3, 1.0),
        Zone("CENTER", 1 / 3, 0.0, 2 / 3, 1.0),
        Zone("RIGHT", 2 / 3, 0.0, 1.0, 1.0),
    ]


def zone_at(x: int, y: int, width: int, height: int, zones: list[Zone]) -> str:
    nx = min(0.999999, max(0.0, x / width))
    ny = min(0.999999, max(0.0, y / height))
    return next((zone.name for zone in zones if zone.contains(nx, ny)), "OTHER")


def movement_direction(points: deque[tuple[int, int]] | list[tuple[int, int]], width: int, height: int) -> str:
    if len(points) < 2:
        return "STILL"
    # Compare positions across recent observations to reduce box jitter.
    x0, y0 = points[0]
    x1, y1 = points[-1]
    dx, dy = x1 - x0, y1 - y0
    threshold = max(10.0, min(width, height) * 0.025)
    if (dx * dx + dy * dy) ** 0.5 < threshold:
        return "STILL"
    # Dominant axis, using pixel displacement (direction in the image plane).
    if abs(dx) >= abs(dy):
        return "RIGHT" if dx > 0 else "LEFT"
    return "DOWN" if dy > 0 else "UP"


@dataclass
class Person:
    track_id: int
    first_frame: int
    last_frame: int
    foot: tuple[int, int]
    current_zone: str
    zone_enter_frame: int
    direction: str = "STILL"
    detected_frames: int = 0
    zone_frames: Counter = field(default_factory=Counter)
    trail: deque[tuple[int, int]] = field(default_factory=lambda: deque(maxlen=36))
    status: str = "ACTIVE"
    closed: bool = False

    def observe(self, frame_number: int, foot: tuple[int, int], zone: str, width: int, height: int) -> None:
        if zone != self.current_zone:
            self.zone_enter_frame = frame_number
            self.current_zone = zone
        self.last_frame = frame_number
        self.foot = foot
        self.detected_frames += 1
        self.zone_frames[zone] += 1
        self.trail.append(foot)
        self.direction = movement_direction(self.trail, width, height)
        self.status = "ACTIVE"
        self.closed = False

    def elapsed_seconds(self, fps: float) -> float:
        # First-to-last detection: includes short occlusion gaps.
        return (self.last_frame - self.first_frame + 1) / fps

    def current_zone_seconds(self, fps: float) -> float:
        return (self.last_frame - self.zone_enter_frame + 1) / fps


def possible_exit(person: Person, width: int, height: int, edge_fraction: float = 0.09) -> str:
    """Conservative estimate. Lost mid-scene is NOT labelled an exit."""
    x, y = person.foot
    normalized_x = x / width
    normalized_y = y / height
    outward = {
        "LEFT": normalized_x <= edge_fraction,
        "RIGHT": normalized_x >= 1 - edge_fraction,
        "UP": normalized_y <= edge_fraction,
        "DOWN": normalized_y >= 1 - edge_fraction,
    }
    direction = person.direction
    if direction in outward and outward[direction]:
        return f"POSSIBLE_EXIT_{direction}"
    return "LOST_INSIDE_OR_OCCLUDED"


def resolve_input(provided: str | None) -> Path:
    if provided:
        path = Path(provided).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {path}")
        return path
    for candidate in DEFAULT_INPUTS:
        path = Path(candidate)
        if path.is_file():
            return path
    raise FileNotFoundError(
        "입력 영상이 없습니다. --input samples/영상이름.mp4 로 지정하세요."
    )


def draw_regions(frame, zones: list[Zone]) -> None:
    height, width = frame.shape[:2]
    for zone in zones:
        x1, y1 = int(zone.x1 * width), int(zone.y1 * height)
        x2, y2 = int(zone.x2 * width), int(zone.y2 * height)
        cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), (130, 130, 130), 1)
        cv2.putText(frame, zone.name, (x1 + 8, max(65, y1 + 24)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (250, 230, 100), 2, cv2.LINE_AA)


def annotate_person(frame, person: Person, box: tuple[int, int, int, int], fps: float) -> None:
    x1, y1, x2, y2 = box
    color = (40, 220, 90)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    pts = list(person.trail)
    for start, end in zip(pts, pts[1:]):
        cv2.line(frame, start, end, (0, 175, 255), 2, cv2.LINE_AA)
    if len(pts) >= 2:
        cv2.arrowedLine(frame, pts[-2], pts[-1], (0, 175, 255), 2, tipLength=0.4)
    label = (f"ID {person.track_id} | SPAN {person.elapsed_seconds(fps):.1f}s | "
             f"{person.current_zone} {person.current_zone_seconds(fps):.1f}s | {person.direction}")
    font_scale = 0.49
    (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
    label_x = max(0, min(x1, frame.shape[1] - text_w - 10))
    label_y = max(22, y1 - 7)
    cv2.rectangle(frame, (label_x, label_y - text_h - 7),
                  (label_x + text_w + 8, label_y + 5), (17, 17, 17), -1)
    cv2.putText(frame, label, (label_x + 4, label_y),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)


def run(args: argparse.Namespace) -> None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("먼저 설치하세요: python -m pip install ultralytics") from exc

    source = resolve_input(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    zones = args.zone or default_zones()
    if len({zone.name for zone in zones}) != len(zones):
        raise ValueError("구역 이름은 중복되면 안 됩니다.")
    for i, z in enumerate(zones):
        for other in zones[i+1:]:
            if max(z.x1, other.x1) < min(z.x2, other.x2) and max(z.y1, other.y1) < min(z.y2, other.y2):
                raise ValueError(f"ROI 구역이 겹칩니다: {z.name}, {other.name}")

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"영상 열기 실패: {source}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not 1 <= fps <= 240:
        cap.release()
        raise RuntimeError(f"유효하지 않은 입력 FPS={fps}. 시간 측정 신뢰성을 위해 원본 영상의 FPS를 확인하세요.")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("영상 해상도를 읽을 수 없습니다.")

    video_path = output_dir / "storeflow_mvp.mp4"
    history_path = output_dir / "storeflow_track_log.csv"
    summary_path = output_dir / "storeflow_person_summary.csv"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"결과 영상 생성 실패: {video_path}")

    model = YOLO(args.model)
    people: dict[int, Person] = {}
    grace_frames = max(1, round(args.lost_seconds * fps))
    frame_number = 0
    print(f"[INPUT] {source} | {width}x{height} @ {fps:.2f} FPS")
    print(f"[ZONES] {', '.join(z.name for z in zones)}")

    columns = ["time_s", "track_id", "foot_x", "foot_y", "zone", "direction", "elapsed_s", "zone_elapsed_s"]
    try:
        with history_path.open("w", newline="", encoding="utf-8-sig") as file:
            log = csv.DictWriter(file, fieldnames=columns)
            log.writeheader()
            while True:
                ok, frame = cap.read()
                if not ok or (args.max_frames and frame_number >= args.max_frames):
                    break

                prediction = model.track(
                    frame, persist=True, tracker="bytetrack.yaml", classes=[0],
                    conf=args.conf, imgsz=args.imgsz, verbose=False,
                )[0]
                seen: set[int] = set()
                annotated: list[tuple[Person, tuple[int, int, int, int]]] = []
                boxes = prediction.boxes
                if boxes is not None and boxes.id is not None:
                    ids = boxes.id.int().cpu().tolist()
                    coordinates = boxes.xyxy.cpu().tolist()
                    for track_id, coords in zip(ids, coordinates):
                        x1, y1, x2, y2 = [int(round(v)) for v in coords]
                        x1, x2 = max(0, x1), min(width - 1, x2)
                        y1, y2 = max(0, y1), min(height - 1, y2)
                        foot = ((x1 + x2) // 2, y2)  # bottom-center is better for zone membership
                        zone = zone_at(*foot, width, height, zones)
                        if track_id not in people:
                            people[track_id] = Person(track_id, frame_number, frame_number, foot, zone, frame_number)
                        person = people[track_id]
                        person.observe(frame_number, foot, zone, width, height)
                        seen.add(track_id)
                        annotated.append((person, (x1, y1, x2, y2)))
                        log.writerow({
                            "time_s": f"{frame_number / fps:.3f}",
                            "track_id": track_id, "foot_x": foot[0], "foot_y": foot[1],
                            "zone": zone, "direction": person.direction,
                            "elapsed_s": f"{person.elapsed_seconds(fps):.3f}",
                            "zone_elapsed_s": f"{person.current_zone_seconds(fps):.3f}",
                        })

                for person in people.values():
                    if person.track_id not in seen and not person.closed:
                        if frame_number - person.last_frame > grace_frames:
                            person.status = possible_exit(person, width, height)
                            person.closed = True

                draw_regions(frame, zones)
                for person, box in annotated:
                    annotate_person(frame, person, box, fps)

                possible_exits = sum(p.status.startswith("POSSIBLE_EXIT_") for p in people.values())
                cv2.rectangle(frame, (0, 0), (width, 43), (15, 15, 15), -1)
                header = (f"StoreFlow | {frame_number/fps:.1f}s | IN VIEW: {len(seen)} | "
                          f"UNIQUE TRACK IDs: {len(people)} | POSSIBLE EXITS: {possible_exits}")
                cv2.putText(frame, header, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                            0.57, (255, 255, 255), 2, cv2.LINE_AA)
                writer.write(frame)

                if args.show:
                    cv2.imshow("StoreFlow MVP (ESC to stop)", frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        frame_number += 1
                        break
                frame_number += 1
                if frame_number % max(1, round(fps * 5)) == 0:
                    print(f"  ... {frame_number / fps:.0f}s processed / {len(people)} IDs")
    finally:
        cap.release()
        writer.release()
        if args.show:
            cv2.destroyAllWindows()

    summary_columns = [
        "track_id", "first_seen_s", "last_seen_s", "elapsed_s", "detected_s",
        "last_zone", "last_direction", "status",
        *[f"zone_{zone.name}_observed_s" for zone in zones],
    ]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as file:
        summary = csv.DictWriter(file, fieldnames=summary_columns)
        summary.writeheader()
        for person in sorted(people.values(), key=lambda p: p.track_id):
            # The end of a recording is not an observed exit.
            if not person.closed:
                person.status = "VISIBLE_AT_END_OR_RECENTLY_LOST"
            record = {
                "track_id": person.track_id,
                "first_seen_s": round(person.first_frame / fps, 3),
                "last_seen_s": round(person.last_frame / fps, 3),
                "elapsed_s": round(person.elapsed_seconds(fps), 3),
                "detected_s": round(person.detected_frames / fps, 3),
                "last_zone": person.current_zone,
                "last_direction": person.direction,
                "status": person.status,
            }
            record.update({
                f"zone_{zone.name}_observed_s": round(person.zone_frames[zone.name] / fps, 3)
                for zone in zones
            })
            summary.writerow(record)

    print("\n=== DONE ===")
    print(f"Frames: {frame_number}, track IDs: {len(people)}")
    print(f"Video:   {video_path}")
    print(f"Timeline:{history_path}")
    print(f"Summary: {summary_path}")
    print("NOTE: Exit direction is a possibility inferred from disappearance near the edge, not proof.")
    print("NOTE: A tracker may switch IDs; use elapsed time as an estimate.")


def main() -> None:
    parser = argparse.ArgumentParser(description="StoreFlow YOLO + ByteTrack MVP")
    parser.add_argument("--input", help="Input video; defaults to the first existing project candidate")
    parser.add_argument("--output-dir", default="outputs", help="Output folder")
    parser.add_argument("--model", default="yolov8n.pt", help="Ultralytics YOLO model")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--lost-seconds", type=float, default=1.2)
    parser.add_argument("--zone", type=parse_zone, action="append", help="e.g. COUNTER:0.1,0.2,0.4,0.8 (repeatable)")
    parser.add_argument("--max-frames", type=int, default=0, help="Optional limit for quick testing")
    parser.add_argument("--show", action="store_true", help="Display during processing (requires GUI)")
    args = parser.parse_args()
    if not 0 < args.conf <= 1 or args.lost_seconds <= 0 or args.imgsz <= 0 or args.max_frames < 0:
        parser.error("conf=(0,1], lost-seconds>0, imgsz>0, max-frames>=0 이어야 합니다.")
    run(args)


if __name__ == "__main__":
    main()
