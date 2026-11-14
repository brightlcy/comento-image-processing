#!/usr/bin/env python3
"""StoreFlow ROI analytics from an existing ByteTrack CSV: no YOLO rerun.

The outputs represent *observed tracked IDs*, not unique customers or verified waits.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
import sys
import traceback

import cv2

REQUIRED = {"time_s", "track_id", "foot_x", "foot_y"}
EVENT_COLUMNS = ["time_s", "track_id", "zone", "event", "evidence"]
TRACK_COLUMNS = ["track_id", "zone", "observed_frames", "observed_s", "first_observed_s", "last_observed_s", "observed_entries", "uncertain_starts", "segments", "last_direction"]
OCC_COLUMNS = ["time_s", "frame", "zone", "observed_ids_in_zone"]


@dataclass(frozen=True)
class Zone:
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, x: int, y: int, width: int, height: int) -> bool:
        nx, ny = x / width, y / height
        return self.x1 <= nx < self.x2 and self.y1 <= ny < self.y2


@dataclass(frozen=True)
class Observation:
    frame: int
    seconds: float
    track_id: int
    x: int
    y: int
    direction: str = "UNKNOWN"


def validate_zones(zones: list[Zone]) -> None:
    if not zones:
        raise ValueError("At least one ROI zone must be configured")
    names: set[str] = set()
    for z in zones:
        if not z.name or not z.name.replace("_", "").isalnum():
            raise ValueError(f"Invalid zone name: {z.name!r}; use letters/numbers/underscore")
        if z.name in names:
            raise ValueError(f"Duplicate ROI name: {z.name}")
        names.add(z.name)
        if not all(math.isfinite(v) for v in (z.x1, z.y1, z.x2, z.y2)):
            raise ValueError(f"ROI non-finite coordinate: {z.name}")
        if not (0 <= z.x1 < z.x2 <= 1 and 0 <= z.y1 < z.y2 <= 1):
            raise ValueError(f"ROI outside 0..1 or inverted: {z.name}")
    for i, a in enumerate(zones):
        for b in zones[i + 1:]:
            horizontal = min(a.x2, b.x2) - max(a.x1, b.x1)
            vertical = min(a.y2, b.y2) - max(a.y1, b.y1)
            if horizontal > 1e-10 and vertical > 1e-10:
                raise ValueError(f"ROI regions overlap: {a.name} and {b.name}; use nonoverlapping standing areas")


def zone_for(x: int, y: int, width: int, height: int, zones: list[Zone]) -> str | None:
    for z in zones:
        if z.contains(x, y, width, height):
            return z.name
    return None


def video_metadata(video: Path) -> dict:
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot decode video: {video}")
    try:
        meta = {"width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": float(cap.get(cv2.CAP_PROP_FPS)),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
        if meta["width"] <= 0 or meta["height"] <= 0 or meta["frame_count"] <= 0:
            raise ValueError(f"Invalid video dimensions/frame count: {meta}")
        if not math.isfinite(meta["fps"]) or not 1 <= meta["fps"] <= 240:
            raise ValueError(f"Invalid video FPS: {meta['fps']}")
        ok, _ = cap.read()
        if not ok:
            raise ValueError("Cannot decode the first video frame")
        return meta
    finally:
        cap.release()


def read_observations(path: Path, meta: dict) -> list[Observation]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    observations: list[Observation] = []
    seen: set[tuple[int, int]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError(f"Required CSV fields: {sorted(REQUIRED)}; got {reader.fieldnames}")
        for row_num, row in enumerate(reader, start=2):
            try:
                seconds = float(row["time_s"])
                if not math.isfinite(seconds) or seconds < 0:
                    raise ValueError("time_s must be finite and nonnegative")
                track_id = int(row["track_id"])
                x, y = int(row["foot_x"]), int(row["foot_y"])
                frame = round(seconds * meta["fps"])
                if track_id < 0 or not (0 <= x < meta["width"] and 0 <= y < meta["height"]):
                    raise ValueError("track_id or foot point outside video bounds")
                if frame < 0 or frame >= meta["frame_count"]:
                    raise ValueError("timestamp outside video frame range")
                if abs(seconds - frame / meta["fps"]) > 0.002:
                    raise ValueError("timestamp is inconsistent with video FPS")
                key = (frame, track_id)
                if key in seen:
                    raise ValueError(f"same track ID appears twice at frame {frame}")
                seen.add(key)
                observations.append(Observation(frame, seconds, track_id, x, y,
                                                (row.get("direction") or "UNKNOWN").strip()))
            except (TypeError, ValueError, OverflowError) as e:
                raise ValueError(f"Invalid row {row_num}: {e}") from e
    if not observations:
        raise ValueError("No tracked observations in CSV")
    return sorted(observations, key=lambda o: (o.frame, o.track_id))


def config_from_path(path: Path, meta: dict) -> list[Zone]:
    if not path.is_file():
        raise FileNotFoundError(f"ROI config not found: {path}. Run the setup command first")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("width") != meta["width"] or cfg.get("height") != meta["height"]:
        raise ValueError("ROI config resolution differs from source video. Run setup with this video")
    if cfg.get("version") != 1:
        raise ValueError("Unsupported ROI config version")
    try:
        zones = [Zone(str(z["name"]), *(float(z[k]) for k in ("x1", "y1", "x2", "y2")))
                 for z in cfg["zones"]]
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("Malformed ROI config") from e
    validate_zones(zones)
    return zones


def compute(observations: list[Observation], zones: list[Zone], meta: dict) -> dict:
    """Pure deterministic analytics. Only observed frames count toward dwell."""
    validate_zones(zones)
    fps, frames = meta["fps"], meta["frame_count"]
    names = [z.name for z in zones]
    by_track: dict[int, list[Observation]] = defaultdict(list)
    frame_points: dict[int, list[tuple[int, int, int, str | None]]] = defaultdict(list)
    occupancy: dict[tuple[int, str], set[int]] = defaultdict(set)
    for obs in observations:
        by_track[obs.track_id].append(obs)
        zone = zone_for(obs.x, obs.y, meta["width"], meta["height"], zones)
        frame_points[obs.frame].append((obs.track_id, obs.x, obs.y, zone))
        if zone is not None:
            occupancy[(obs.frame, zone)].add(obs.track_id)

    events: list[dict] = []
    track_rows: list[dict] = []
    for track_id, samples in sorted(by_track.items()):
        samples.sort(key=lambda o: o.frame)
        counts = defaultdict(int)
        segment_counts = defaultdict(int)
        clear_entries = defaultdict(int)
        uncertain_starts = defaultdict(int)
        first_at: dict[str, float] = {}
        last_at: dict[str, float] = {}
        last_direction: dict[str, str] = {}
        previous_frame: int | None = None
        previous_zone: str | None = None

        def record(frame: int, zone: str, event: str, evidence: str):
            events.append({"time_s": round(frame / fps, 3), "track_id": track_id,
                           "zone": zone, "event": event, "evidence": evidence})

        for obs in samples:
            zone = zone_for(obs.x, obs.y, meta["width"], meta["height"], zones)
            contiguous = previous_frame is not None and obs.frame == previous_frame + 1
            if previous_frame is None:
                if zone:
                    record(obs.frame, zone, "FIRST_OBSERVED_IN_ZONE", "initial observation; entry not proven")
                    segment_counts[zone] += 1
                    uncertain_starts[zone] += 1
            elif not contiguous:
                if previous_zone:
                    record(previous_frame, previous_zone, "OBSERVATION_INTERRUPTED", "missing frames; no exit inferred")
                if zone:
                    record(obs.frame, zone, "REAPPEARED_IN_ZONE", "lost frames; entry not proven")
                    segment_counts[zone] += 1
                    uncertain_starts[zone] += 1
            elif zone != previous_zone:
                if previous_zone:
                    record(obs.frame, previous_zone, "OBSERVED_LEAVE_ZONE", "adjacent-frame zone transition")
                if zone:
                    record(obs.frame, zone, "OBSERVED_ENTER_ZONE", "adjacent-frame zone transition")
                    segment_counts[zone] += 1
                    clear_entries[zone] += 1
            if zone:
                counts[zone] += 1
                first_at.setdefault(zone, obs.frame / fps)
                last_at[zone] = obs.frame / fps
                last_direction[zone] = obs.direction
            previous_frame, previous_zone = obs.frame, zone
        if previous_zone is not None and previous_frame is not None:
            record(previous_frame, previous_zone, "LAST_OBSERVED_IN_ZONE", "recording/track ends; exit not proven")

        for name in names:
            if counts[name] == 0:
                continue
            track_rows.append({"track_id": track_id, "zone": name,
                               "observed_frames": counts[name],
                               "observed_s": round(counts[name] / fps, 3),
                               "first_observed_s": round(first_at[name], 3),
                               "last_observed_s": round(last_at[name], 3),
                               "observed_entries": clear_entries[name],
                               "uncertain_starts": uncertain_starts[name],
                               "segments": segment_counts[name],
                               "last_direction": last_direction[name]})

    occ_rows = [{"time_s": round(frame / fps, 3), "frame": frame, "zone": name,
                 "observed_ids_in_zone": len(occupancy[(frame, name)])}
                for frame in range(frames) for name in names]
    aggregate = {}
    for name in names:
        rows = [r for r in track_rows if r["zone"] == name]
        counts = [len(occupancy[(frame, name)]) for frame in range(frames)]
        aggregate[name] = {
            "observed_track_ids": len(rows),
            "observed_track_seconds": round(sum(r["observed_frames"] for r in rows) / fps, 3),
            "average_observed_occupancy": round(sum(counts) / frames, 3),
            "peak_observed_occupancy": max(counts, default=0),
            "peak_frame_time_s": round(counts.index(max(counts)) / fps, 3) if counts else 0.0,
            "adjacent_frame_enter_events": sum(r["observed_entries"] for r in rows),
            "unconfirmed_segment_starts": sum(r["uncertain_starts"] for r in rows),
        }

    return {"events": events, "tracks": track_rows, "occupancy": occ_rows,
            "aggregate": aggregate, "frame_points": frame_points,
            "observations": len(observations)}


def assert_accounting(result: dict, observations: list[Observation], zones: list[Zone], meta: dict) -> None:
    by_name = {z.name: z for z in zones}
    expected = defaultdict(int)
    for ob in observations:
        z = zone_for(ob.x, ob.y, meta["width"], meta["height"], zones)
        if z is not None:
            expected[z] += 1
    track = defaultdict(int)
    occupancy = defaultdict(int)
    for row in result["tracks"]:
        track[row["zone"]] += row["observed_frames"]
        if abs(float(row["observed_s"]) - row["observed_frames"] / meta["fps"]) > .00051:
            raise ValueError("Track observed seconds mismatch")
    for row in result["occupancy"]:
        occupancy[row["zone"]] += row["observed_ids_in_zone"]
        if row["observed_ids_in_zone"] < 0:
            raise ValueError("Negative occupancy")
    if set(expected) - set(by_name):
        raise ValueError("Unknown zone in count")
    for name in by_name:
        if expected[name] != track[name] or track[name] != occupancy[name]:
            raise ValueError(f"R4 ACCOUNTING FAIL: {name} expected={expected[name]} track={track[name]} occupancy={occupancy[name]}")


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def draw_preview(video: Path, dest: Path, zones: list[Zone], result: dict, meta: dict) -> None:
    cap = cv2.VideoCapture(str(video))
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), meta["fps"],
                             (meta["width"], meta["height"]))
    if not cap.isOpened() or not writer.isOpened():
        cap.release()
        writer.release()
        raise ValueError("Unable to initialize preview video read/write")
    count = 0
    try:
        while count < meta["frame_count"]:
            ok, frame = cap.read()
            if not ok:
                break
            for z in zones:
                p1 = (int(z.x1 * meta["width"]), int(z.y1 * meta["height"]))
                p2 = (int(z.x2 * meta["width"]), int(z.y2 * meta["height"]))
                cv2.rectangle(frame, p1, p2, (0, 200, 255), 2)
                occ = len([p for p in result["frame_points"].get(count, []) if p[3] == z.name])
                cv2.putText(frame, f"{z.name}: {occ} IDs", (p1[0], max(22, p1[1] - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, .50, (0, 255, 255), 2, cv2.LINE_AA)
            for tid, x, y, zone in result["frame_points"].get(count, []):
                cv2.circle(frame, (x, y), 5, (0, 255, 0) if zone else (160, 160, 160), -1)
                cv2.putText(frame, str(tid), (x + 6, y - 5), cv2.FONT_HERSHEY_SIMPLEX,
                            .42, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.rectangle(frame, (0, 0), (meta["width"], 37), (20, 20, 20), -1)
            cv2.putText(frame, f"StoreFlow ROI | {count/meta['fps']:.1f}s | UNVERIFIED DETECTIONS",
                        (10, 26), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 2, cv2.LINE_AA)
            writer.write(frame)
            count += 1
    finally:
        cap.release()
        writer.release()
    if count != meta["frame_count"]:
        raise ValueError(f"Preview decoded {count} frames, expected {meta['frame_count']}")
    check = cv2.VideoCapture(str(dest))
    try:
        if not check.isOpened() or int(check.get(cv2.CAP_PROP_FRAME_COUNT)) < count - 1:
            raise ValueError("Exported ROI video unreadable or missing frames")
    finally:
        check.release()


def analyze(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "roi_validation_report.json"
    gate_names = ["R1_VIDEO_AND_CSV", "R2_ROI_CONFIG", "R3_ROI_EVENTS", "R4_ACCOUNTING", "R5_EXPORT"]
    gates = {k: {"status": "NOT_RUN"} for k in gate_names}

    def step(name, fn):
        print(f"[RUN] {name}", flush=True)
        try:
            value = fn()
            gates[name] = {"status": "PASS"}
            print(f"[PASS] {name}", flush=True)
            return value
        except Exception as exc:
            gates[name] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
            report_path.write_text(json.dumps({"gates": gates, "stopped_at": name,
                            "guidance": "Fix the failed gate; rerun unchanged command. Later gates were not run."},
                            ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[FAIL] {name}: {exc}", file=sys.stderr, flush=True)
            print(f"[REPORT] {report_path}", file=sys.stderr, flush=True)
            raise SystemExit(1) from exc

    def g1():
        meta = video_metadata(Path(args.video))
        observations = read_observations(Path(args.input_csv), meta)
        return meta, observations
    meta, observations = step(gate_names[0], g1)
    zones = step(gate_names[1], lambda: config_from_path(Path(args.config), meta))
    result = step(gate_names[2], lambda: compute(observations, zones, meta))
    step(gate_names[3], lambda: assert_accounting(result, observations, zones, meta))

    def g5():
        write_csv(out / "roi_events.csv", EVENT_COLUMNS, result["events"])
        write_csv(out / "roi_track_summary.csv", TRACK_COLUMNS, result["tracks"])
        write_csv(out / "roi_occupancy.csv", OCC_COLUMNS, result["occupancy"])
        summary = {
            "video": str(args.video), "source_csv": str(args.input_csv), "fps": meta["fps"],
            "frame_count": meta["frame_count"], "duration_s": round(meta["frame_count"] / meta["fps"], 3),
            "analyzed_observations": result["observations"],
            "zone_metrics": result["aggregate"],
            "limitations": [
                "ID count is not the number of distinct customers (ID switches and false detections).",
                "Observed dwell is count of tracked frames divided by FPS, not continuous actual time or confirmed waiting.",
                "No actual store entrance/exit or purchase event can be inferred from these ROIs.",
                "The current source detection has poor preliminary accuracy: do not use for operational decisions."
            ]}
        (out / "roi_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.no_video:
            draw_preview(Path(args.video), out / "roi_preview.mp4", zones, result, meta)
        with (out / "roi_occupancy.csv").open(encoding="utf-8-sig", newline="") as f:
            if sum(1 for _ in csv.DictReader(f)) != meta["frame_count"] * len(zones):
                raise ValueError("Exported occupancy CSV row count does not match video frames")
        return summary
    summary = step(gate_names[4], g5)
    report_path.write_text(json.dumps({"gates": gates, "status": "ALL_COMPUTATION_GATES_PASS",
            "quality_status": "EXPERIMENTAL_NOT_VALIDATED", "summary_file": str(out / "roi_summary.json")},
            ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[ALL COMPUTATION GATES PASS] ROI analysis generated (detection accuracy NOT validated)")
    print("OUTPUT:", out)
    for name, info in result["aggregate"].items():
        print(f"{name}: observed IDs={info['observed_track_ids']}, "
              f"observed track-sec={info['observed_track_seconds']}, "
              f"max concurrent observed IDs={info['peak_observed_occupancy']}")
    print("IMPORTANT: these are tracked-ID observations, not verified customers or real queue durations")


class RectSetup:
    """Mouse-driven area selector for Mac OpenCV, no letter keys needed."""
    def __init__(self, frame, names: list[str], config_path: Path, meta: dict, sec: float):
        self.frame = frame
        self.names = names
        self.config_path = config_path
        self.meta = meta
        self.sec = sec
        self.h, self.w = frame.shape[:2]
        self.index = 0
        self.rects: list[tuple[int,int,int,int] | None] = [None] * len(names)
        self.dragging = False
        self.anchor: tuple[int,int] | None = None
        self.cursor: tuple[int,int] | None = None
        self.done = False
        self.note = "Drag a FLOOR standing zone; click NEXT/SAVE (not the screen or a person)."
        self.buttons = ["PREV", "CLEAR", "NEXT", "SAVE", "QUIT"]
        self.bar = 90
        self.draft_path = config_path.with_suffix(".draft.json")
        self._restore_draft()

    def _restore_draft(self):
        if not self.draft_path.is_file():
            return
        try:
            d = json.loads(self.draft_path.read_text(encoding="utf-8"))
            if d["width"] != self.w or d["height"] != self.h or [z["name"] for z in d["zones"]] != self.names:
                return
            for i,z in enumerate(d["zones"]):
                if z.get("rect"):
                    self.rects[i] = tuple(z["rect"])
            self.note = "Recovered draft selection; SAVE to confirm."
        except (KeyError, json.JSONDecodeError, TypeError):
            pass

    def _write_draft(self):
        d = {"width": self.w, "height": self.h,
             "zones": [{"name": name, "rect": list(r) if r else None}
                       for name, r in zip(self.names, self.rects)]}
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        self.draft_path.write_text(json.dumps(d, indent=2), encoding="utf-8")

    def _click_button(self, name: str):
        if name == "PREV":
            self.index = max(0, self.index - 1)
        elif name == "CLEAR":
            self.rects[self.index] = None
            self._write_draft()
            self.note = f"Cleared {self.names[self.index]}"
        elif name == "NEXT":
            if self.rects[self.index] is None:
                self.note = "Draw a floor-zone rectangle before NEXT."
            else:
                self.index = min(len(self.names)-1, self.index+1)
        elif name == "SAVE":
            if any(r is None for r in self.rects):
                self.note = "Some ROIs missing. Draw all zones before SAVE."
                return
            zs = [Zone(name, r[0]/self.w, r[1]/self.h, r[2]/self.w, r[3]/self.h)
                  for name, r in zip(self.names, self.rects) if r is not None]
            try:
                validate_zones(zs)
            except ValueError as e:
                self.note = str(e)
                return
            cfg = {"version": 1, "width": self.w, "height": self.h,
                   "snapshot_time_s": self.sec, "source_video": "reference video",
                   "zones": [z.__dict__ for z in zs],
                   "method": "Manually drawn standing-floor ROIs; membership uses tracked foot position"}
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            if self.config_path.exists():
                shutil.copy2(self.config_path, self.config_path.with_suffix(".previous.json"))
            self.config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.done = True
            if self.draft_path.is_file():
                self.draft_path.unlink()
            print("[SAVED ROI]", self.config_path, flush=True)
        elif name == "QUIT":
            self._write_draft()
            self.done = True
            print("[QUIT] Draft saved; final ROI config not changed.", flush=True)

    def on_mouse(self, event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            if y >= self.h:
                index = min(4, max(0, x // max(1, self.w // 5)))
                self._click_button(self.buttons[index])
            else:
                self.dragging = True
                self.anchor = (max(0, min(x, self.w-1)), max(0, min(y, self.h-1)))
                self.cursor = self.anchor
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            self.cursor = (max(0, min(x, self.w-1)), max(0, min(y, self.h-1)))
        elif event == cv2.EVENT_LBUTTONUP and self.dragging:
            self.dragging = False
            if self.anchor:
                end = (max(0, min(x, self.w-1)), max(0, min(y, self.h-1)))
                x1,x2 = sorted((self.anchor[0],end[0]))
                y1,y2 = sorted((self.anchor[1],end[1]))
                if x2-x1 >= 12 and y2-y1 >= 12:
                    self.rects[self.index] = (x1,y1,x2,y2)
                    self._write_draft()
                    self.note = f"Set {self.names[self.index]}; click NEXT or SAVE."
                else:
                    self.note = "ROI too small; drag at least 12x12 pixels."
                self.anchor = None
                self.cursor = None

    def render(self):
        import numpy as np
        canvas = np.zeros((self.h + self.bar, self.w, 3), dtype=np.uint8)
        canvas[:self.h] = self.frame
        for i, rect in enumerate(self.rects):
            if rect is None:
                continue
            color = (0, 250, 250) if i == self.index else (0, 190, 0)
            cv2.rectangle(canvas, rect[:2], rect[2:], color, 2)
            cv2.putText(canvas, self.names[i], (rect[0], max(25, rect[1]-6)),
                        cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2, cv2.LINE_AA)
        if self.dragging and self.anchor and self.cursor:
            cv2.rectangle(canvas, self.anchor, self.cursor, (230, 230, 0), 2)
        cv2.rectangle(canvas,(0,self.h),(self.w,self.h+self.bar),(20,20,20),-1)
        cv2.putText(canvas, f"ROI {self.index+1}/{len(self.names)}: {self.names[self.index]} | DRAW STANDING FLOOR AREA",
                    (8, self.h+19), cv2.FONT_HERSHEY_SIMPLEX, .53,(255,255,255),1,cv2.LINE_AA)
        cv2.putText(canvas, self.note[:125], (8,self.h+39),cv2.FONT_HERSHEY_SIMPLEX,.39,(180,230,240),1,cv2.LINE_AA)
        w = self.w // 5
        for i, name in enumerate(self.buttons):
            a = (i*w, self.h+49)
            b = ((i+1)*w if i<4 else self.w-1, self.h+self.bar-3)
            cv2.rectangle(canvas,a,b,(80,80,80),1)
            cv2.putText(canvas,name,(a[0]+13,self.h+72),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1,cv2.LINE_AA)
        return canvas


def setup(args) -> None:
    meta = video_metadata(Path(args.video))
    if args.time < 0 or args.time >= meta["frame_count"] / meta["fps"]:
        raise ValueError("setup --time is outside video duration")
    names = [name.upper() for name in args.names]
    if not names or len(names) > 5 or len(set(names)) != len(names):
        raise ValueError("Use 1-5 unique ROI names")
    cap = cv2.VideoCapture(str(args.video))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(args.time * meta["fps"]))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise ValueError("Cannot read setup reference frame")
    ui = RectSetup(frame, names, Path(args.config), meta, args.time)
    title = "StoreFlow ROI SETUP - mouse buttons"
    try:
        cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(title, ui.on_mouse)
        while not ui.done:
            cv2.imshow(title, ui.render())
            key = cv2.waitKey(50) & 0xFF
            if key == 27:  # optional ESC quit, with draft preserved
                ui._click_button("QUIT")
            if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                ui._click_button("QUIT")
    finally:
        cv2.destroyAllWindows()


def main(argv=None):
    parser = argparse.ArgumentParser(description="StoreFlow ROI dwell and observed occupancy analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup", help="Draw standing-floor ROI(s) on a video frame")
    s.add_argument("--video", default="samples/storeflow_crowd_candidate.mp4")
    s.add_argument("--time", type=float, default=10.6)
    s.add_argument("--names", nargs="+", default=["KIOSK_AREA"])
    s.add_argument("--config", default="outputs/quality_run/roi_zones.json")
    a = sub.add_parser("analyze", help="Analyze existing track CSV without re-running YOLO")
    a.add_argument("--video", default="samples/storeflow_crowd_candidate.mp4")
    a.add_argument("--input-csv", default="outputs/quality_run/storeflow_track_log.csv")
    a.add_argument("--config", default="outputs/quality_run/roi_zones.json")
    a.add_argument("--out", default="outputs/quality_run/roi_insights")
    a.add_argument("--no-video", action="store_true", help="CSV/JSON only, no annotated preview MP4")
    args = parser.parse_args(argv)
    if args.command == "setup":
        setup(args)
    else:
        analyze(args)


if __name__ == "__main__":
    main()
