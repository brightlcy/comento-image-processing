#!/usr/bin/env python3
"""StoreFlow fail-fast quality gates. One stage passes before the next starts.

Run from the directory containing storeflow_mvp.py:
  python gate_runner.py --input samples/storeflow_crowd_candidate.mp4 --max-frames 150
  python gate_runner.py --input samples/storeflow_crowd_candidate.mp4
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2

import storeflow_mvp as mvp

STAGES = [
    ("01", "영상 입력 / FPS / 디코딩", "tests.test_stage_01_input"),
    ("02", "YOLO 사람 탐지", "tests.test_stage_02_detection"),
    ("03", "ByteTrack ID 추적", "tests.test_stage_03_tracking"),
    ("04", "ROI / 체류시간 계산", "tests.test_stage_04_dwell"),
    ("05", "이동 / 퇴장 방향 추정", "tests.test_stage_05_direction"),
    ("06", "영상 / CSV 저장 검증", "tests.test_stage_06_export"),
]

DIAGNOSIS = {
    "01": ("영상 경로 오타, 손상된 파일, 지원되지 않는 코덱, 비정상 FPS 또는 프레임 누락",
           "--input 경로 및 ffprobe 결과를 확인하고 필요하면 ffmpeg로 CFR MP4로 재인코딩하세요."),
    "02": ("사람이 거의 없는 영상, 너무 작은 사람, 낮은 조도, 탐지 임계값 또는 YOLO 모델 설치 문제",
           "사람이 실제로 나오는 영상인지 확인하세요. 필요하면 --conf 0.15 또는 큰 모델을 사용하세요."),
    "03": ("탐지 결과는 있지만 ID가 생성되지 않음, ByteTrack 의존성/임계값 문제, 장면에 사람이 드묾",
           "ultralytics/lap 설치를 확인하고 연속된 프레임을 확인하세요. --conf 0.15 또는 다른 영상을 시도하세요."),
    "04": ("ROI 영역 중복, 경계 좌표 오류, FPS가 유효하지 않음, 체류시간 계산 회귀",
           "ROI의 0~1 정규화 좌표 및 START/END 기준과 프레임별 관측 시간을 확인하세요."),
    "05": ("좌표 순서/영상 좌표계 혼동, 움직임 임계값, 화면 밖 소실을 실제 퇴장으로 오해",
           "이동 방향은 화면 기준이며 퇴장은 추정치입니다. 경계·이동·소실 조건을 다시 점검하세요."),
    "06": ("동영상 인코더/쓰기 권한/디스크 공간 문제, CSV 포맷 오류, 출력 내용 불일치",
           "출력 폴더 권한·용량을 확인하고 mp4v 인코더 지원 여부를 확인한 후 동일 입력으로 재실행하세요."),
}


class GateFailure(Exception):
    pass


def assert_video(path: Path) -> dict:
    if not path.is_file():
        raise GateFailure(f"영상 파일이 없습니다: {path}")
    if path.stat().st_size <= 0:
        raise GateFailure(f"영상 파일이 비어 있습니다: {path}")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise GateFailure(f"OpenCV에서 영상 열기 실패: {path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or not (1 <= fps <= 240):
            raise GateFailure(f"FPS 범위 오류: {fps}. 시간 결과를 보증할 수 없습니다.")
        if width <= 0 or height <= 0 or frames < 1:
            raise GateFailure(f"영상 메타데이터 오류: {width}x{height}, frames={frames}")
        for index in sorted({0, frames // 2, frames - 1}):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok or frame is None or frame.shape[:2] != (height, width):
                raise GateFailure(f"프레임 디코딩/크기 오류: frame={index}/{frames}")
        return {"width": width, "height": height, "fps": fps, "frames": frames,
                "duration_s": round(frames / fps, 3), "bytes": path.stat().st_size}
    finally:
        cap.release()


def box_count(result, width: int, height: int) -> int:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return 0
    xyxy = getattr(boxes, "xyxy", None)
    if xyxy is None:
        return 0
    coords = xyxy.cpu().tolist()
    count = 0
    for xy in coords:
        if len(xy) != 4 or not all(math.isfinite(float(v)) for v in xy):
            raise GateFailure("YOLO bbox에 NaN/Inf 또는 비정상 좌표가 있습니다")
        x1, y1, x2, y2 = map(float, xy)
        if x2 <= x1 or y2 <= y1 or x2 < 0 or y2 < 0 or x1 > width or y1 > height:
            raise GateFailure(f"YOLO bbox 좌표가 유효하지 않습니다: {xy}")
        count += 1
    return count


def track_ids(result) -> list[int]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or getattr(boxes, "id", None) is None:
        return []
    ids = boxes.id.int().cpu().tolist()
    if any((not isinstance(i, int) or i < 0) for i in ids) or len(set(ids)) != len(ids):
        raise GateFailure(f"ByteTrack 중복/비정상 ID: {ids}")
    coords = boxes.xyxy.cpu().tolist()
    if len(ids) != len(coords):
        raise GateFailure("ByteTrack ID와 bbox 개수가 일치하지 않습니다")
    return ids


def sampled_indices(frames: int, n: int = 20) -> list[int]:
    return sorted({round((frames - 1) * i / (min(n, frames) - 1)) for i in range(min(n, frames))}) if frames > 1 else [0]


def smoke_detect(path: Path, meta: dict, args, model) -> dict:
    cap = cv2.VideoCapture(str(path))
    try:
        indices = sampled_indices(meta["frames"], n=20)
        attempts = [args.conf] + ([0.15] if args.conf > 0.15 else [])
        attempts_metrics = []
        for conf in attempts:
            detected = 0
            frames_with_people = 0
            max_people = 0
            for index in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = cap.read()
                if not ok:
                    raise GateFailure(f"샘플 프레임 읽기 실패: {index}")
                prediction = model.predict(frame, classes=[0], conf=conf, imgsz=args.imgsz, verbose=False)[0]
                n = box_count(prediction, meta["width"], meta["height"])
                detected += n
                frames_with_people += n > 0
                max_people = max(n, max_people)
            attempt = {"conf": conf, "samples": len(indices), "detections": detected,
                       "frames_with_people": frames_with_people, "max_people": max_people}
            attempts_metrics.append(attempt)
            if detected:
                if conf != args.conf:
                    args.conf = conf
                    print(f"  [AUTO-RETRY] 사람 탐지 실패 → conf={conf}로 낮춰 재검사 성공 (오탐 증가 가능)")
                return {"selected_conf": conf, "attempts": attempts_metrics, **attempt}
        raise GateFailure(f"{len(indices)}개 샘플에 사람 탐지가 0건입니다. 시도: {attempts_metrics}")
    finally:
        cap.release()


def smoke_track(path: Path, meta: dict, args, model) -> dict:
    # Tracking requires consecutive frames. Never seek unrelated frames with persist=True.
    cap = cv2.VideoCapture(str(path))
    frames_scanned = 0
    frames_with_ids = 0
    unique_ids: set[int] = set()
    observations: list[dict] = []
    try:
        windows = []
        span = max(12, min(round(meta["fps"] * 1.5), 48))
        for proportion in (0.05, 0.35, 0.65, 0.85):
            start = min(meta["frames"] - 1, round(meta["frames"] * proportion))
            windows.append((start, min(meta["frames"], start + span)))
        for window_id, (start, end) in enumerate(windows):
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            first = True
            for index in range(start, end):
                ok, frame = cap.read()
                if not ok:
                    raise GateFailure(f"연속 프레임 읽기 실패: {index}")
                result = model.track(frame, persist=not first, tracker="bytetrack.yaml",
                                     classes=[0], conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
                first = False
                ids = track_ids(result)
                unique_ids.update(ids)
                if ids:
                    boxes = result.boxes.xyxy.cpu().tolist()
                    for tid, (x1, y1, x2, y2) in zip(ids, boxes):
                        foot_x = max(0, min(meta["width"]-1, int(round((x1+x2)/2))))
                        foot_y = max(0, min(meta["height"]-1, int(round(y2))))
                        observations.append({"window": window_id, "frame": index,
                                             "id": tid, "x": foot_x, "y": foot_y})
                frames_with_ids += bool(ids)
                frames_scanned += 1
        if not unique_ids:
            raise GateFailure(f"연속 {frames_scanned}프레임에서 트래킹 ID를 얻지 못했습니다")
        return {"scanned_frames": frames_scanned, "frames_with_ids": frames_with_ids,
                "unique_ids_within_windows": len(unique_ids), "sampling_windows": windows,
                "note": "서로 다른 샘플 구간의 ID는 같은 사람이 아닐 수 있습니다.",
                "observations": observations}
    finally:
        cap.release()



def evaluate_sample_dwell(observations: list[dict], meta: dict, zones: list[mvp.Zone]) -> tuple[dict, dict]:
    """Evaluate per-frame person/zone accounting on real tracker sample observations."""
    if not observations:
        raise GateFailure("실제 추적 샘플 좌표가 없어 ROI 및 체류 검증을 할 수 없습니다")
    people = {}
    memberships = Counter()
    for item in observations:
        key = (item["window"], item["id"])  # Never combine IDs across disconnected windows.
        frame_idx = item["frame"]
        foot = (item["x"], item["y"])
        z = mvp.zone_at(*foot, meta["width"], meta["height"], zones)
        if z != "OTHER" and z not in {zone.name for zone in zones}:
            raise GateFailure(f"존재하지 않는 ROI 라벨: {z}")
        if key not in people:
            people[key] = mvp.Person(item["id"], frame_idx, frame_idx, foot, z, frame_idx)
        p = people[key]
        if frame_idx < p.last_frame:
            raise GateFailure(f"프레임 시간이 역행합니다: window={key[0]}, ID={key[1]}")
        p.observe(frame_idx, foot, z, meta["width"], meta["height"])
        memberships[z] += 1
    observed_sum = sum(p.detected_frames for p in people.values())
    if observed_sum != len(observations) or sum(memberships.values()) != observed_sum:
        raise GateFailure("ROI 영역/관측 프레임 수 합계 불일치")
    if any(p.elapsed_seconds(meta["fps"]) + 0.001 < p.detected_frames / meta["fps"] for p in people.values()):
        raise GateFailure("샘플에서 최초~최종 관측시간보다 실제 관측시간이 큽니다")
    return ({"observed_track_points": observed_sum,
             "track_segments": len(people),
             "roi_observed_seconds": {z: round(n / meta["fps"], 3) for z, n in memberships.items()},
             "note": "이 값은 연결되지 않은 4개 샘플 구간의 관측시간이며 매장 전체 체류시간이 아닙니다."}, people)


def evaluate_sample_directions(people: dict) -> dict:
    if not people:
        raise GateFailure("이동방향을 검사할 추적 구간이 없습니다")
    directions = Counter(person.direction for person in people.values())
    return {"sample_segment_directions": dict(directions),
            "moving_segments": sum(n for d, n in directions.items() if d != "STILL"),
            "note": "실제 퇴장은 추적 소실과 경계·바깥 방향 조건을 함께 확인해야만 추정합니다."}


def validate_outputs(directory: Path, meta: dict, max_frames: int) -> dict:
    video = directory / "storeflow_mvp.mp4"
    log_path = directory / "storeflow_track_log.csv"
    summary_path = directory / "storeflow_person_summary.csv"
    for f in (video, log_path, summary_path):
        if not f.is_file() or f.stat().st_size == 0:
            raise GateFailure(f"결과 누락 또는 0바이트: {f}")
    with log_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"time_s", "track_id", "foot_x", "foot_y", "zone", "direction", "elapsed_s", "zone_elapsed_s"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise GateFailure(f"추적 CSV 필수 컬럼 누락: {required-set(reader.fieldnames or [])}")
        logs = list(reader)
    with summary_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"track_id", "first_seen_s", "last_seen_s", "elapsed_s", "detected_s", "last_zone", "last_direction", "status"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise GateFailure(f"요약 CSV 필수 컬럼 누락: {required-set(reader.fieldnames or [])}")
        summaries = list(reader)
    if not logs or not summaries:
        raise GateFailure("출력은 존재하지만 추적 인원 0명입니다. 검출·추적 결과를 확인하세요")
    if len({row["track_id"] for row in summaries}) != len(summaries):
        raise GateFailure("summary CSV에 ID 중복이 있습니다")
    summary_ids = {row["track_id"] for row in summaries}
    if {row["track_id"] for row in logs} != summary_ids:
        raise GateFailure("track log와 summary에 기록된 ID 집합이 다릅니다")
    last_time = -1.0
    for r in logs:
        timestamp = float(r["time_s"])
        if timestamp + 0.0001 < last_time:
            raise GateFailure("track log 시간이 역행합니다")
        last_time = timestamp
        x, y = int(r["foot_x"]), int(r["foot_y"])
        if not 0 <= x < meta["width"] or not 0 <= y < meta["height"]:
            raise GateFailure(f"화면 밖 좌표: {x},{y}")
        if float(r["elapsed_s"]) < 0 or float(r["zone_elapsed_s"]) < 0:
            raise GateFailure("음수 체류시간이 있습니다")
        if r["direction"] not in {"LEFT", "RIGHT", "UP", "DOWN", "STILL"}:
            raise GateFailure(f"알 수 없는 방향: {r['direction']}")
    for r in summaries:
        elapsed = float(r["elapsed_s"])
        detected = float(r["detected_s"])
        if detected <= 0 or elapsed + 0.002 < detected:
            raise GateFailure(f"체류시간과 관측시간 불일치: {r}")
        observed_zone_time = sum(float(value) for k, value in r.items()
                                 if k.startswith("zone_") and k.endswith("_observed_s"))
        if abs(observed_zone_time - detected) > max(0.01, len(r) * 0.001):
            raise GateFailure(f"구역별 관측 시간 합계 불일치: ID {r['track_id']}")
        if not (r["status"].startswith("POSSIBLE_EXIT_") or
                r["status"] in {"LOST_INSIDE_OR_OCCLUDED", "VISIBLE_AT_END_OR_RECENTLY_LOST"}):
            raise GateFailure(f"알 수 없는 종료 상태: {r['status']}")
    output_meta = assert_video(video)
    expected_frames = min(meta["frames"], max_frames) if max_frames else meta["frames"]
    if abs(output_meta["frames"] - expected_frames) > 1:
        raise GateFailure(f"결과 영상 프레임 수 오류: 기대 {expected_frames}, 실제 {output_meta['frames']}")
    if abs(output_meta["fps"] - meta["fps"]) > 0.1:
        raise GateFailure(f"입력/출력 FPS 불일치: {meta['fps']} vs {output_meta['fps']}")
    warnings = []
    if len(summaries) < 2:
        warnings.append("사람 ID가 1개뿐입니다. 다중 고객 분석 목적에는 영상 교체가 필요할 수 있습니다.")
    if not any(row["direction"] != "STILL" for row in logs):
        warnings.append("이동 방향이 모두 STILL입니다. 영상 움직임과 탐지 품질을 확인하세요.")
    return {"output_video_frames": output_meta["frames"], "track_log_rows": len(logs),
            "unique_ids": len(summaries), "status_counts": dict(Counter(r["status"] for r in summaries)),
            "output_video": str(video), "track_csv": str(log_path), "summary_csv": str(summary_path),
            "warnings": warnings}


def run_tests(module_name: str) -> dict:
    suite = unittest.defaultTestLoader.loadTestsFromName(module_name)
    if suite.countTestCases() == 0:
        raise GateFailure(f"테스트를 찾지 못했습니다: {module_name}")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise GateFailure(f"{module_name}: fail={len(result.failures)}, error={len(result.errors)}")
    return {"unit_tests_passed": result.testsRun}


def cli():
    parser = argparse.ArgumentParser(description="StoreFlow 단계별 검증 / FAIL-FAST 실행기")
    parser.add_argument("--input", required=True, help="검증할 실제 MP4 경로")
    parser.add_argument("--output-dir", default="outputs/quality_run")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--lost-seconds", type=float, default=1.2)
    parser.add_argument("--max-frames", type=int, default=150,
                        help="검증 시 기본 150프레임; 0이면 전체 영상")
    parser.add_argument("--zone", action="append", type=mvp.parse_zone)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not 0 < args.conf <= 1 or args.imgsz <= 0 or args.lost_seconds <= 0 or args.max_frames < 0:
        parser.error("conf=(0,1], imgsz>0, lost-seconds>0, max-frames>=0 이어야 합니다")
    return args


def main() -> int:
    args = cli()
    target = Path(args.input).expanduser()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "validation_report.json"
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "input": str(target),
              "output": str(output), "model": args.model,
              "stages": [{"stage": number, "title": title, "status": "NOT RUN"}
                         for number, title, _ in STAGES]}
    meta = None
    sampled_observations = None
    sampled_people = None
    failed = False
    for stage_index, (number, title, module) in enumerate(STAGES):
        print(f"\n{'='*65}\n[GATE {number}] {title}\n{'='*65}")
        record = report["stages"][stage_index]
        try:
            record.update(run_tests(module))
            if number == "01":
                meta = assert_video(target)
                record["evidence"] = meta
            elif number == "02":
                try:
                    from ultralytics import YOLO
                except ImportError as exc:
                    raise GateFailure("ultralytics 설치 실패: python -m pip install -U ultralytics") from exc
                model = YOLO(args.model)
                record["evidence"] = smoke_detect(target, meta, args, model)
            elif number == "03":
                from ultralytics import YOLO
                model = YOLO(args.model)
                tracking_evidence = smoke_track(target, meta, args, model)
                sampled_observations = tracking_evidence.pop("observations")
                record["evidence"] = tracking_evidence
            elif number == "04":
                zones = args.zone or mvp.default_zones()
                if len({z.name for z in zones}) != len(zones):
                    raise GateFailure("ROI 구역 이름이 중복입니다")
                for index, zone in enumerate(zones):
                    for other in zones[index + 1:]:
                        if max(zone.x1, other.x1) < min(zone.x2, other.x2) and max(zone.y1, other.y1) < min(zone.y2, other.y2):
                            raise GateFailure(f"서로 겹치는 ROI: {zone.name}, {other.name}")
                real_dwell_evidence, sampled_people = evaluate_sample_dwell(sampled_observations, meta, zones)
                record["evidence"] = {"zones": [z.name for z in zones], "fps": meta["fps"],
                                       **real_dwell_evidence}
            elif number == "05":
                record["evidence"] = evaluate_sample_directions(sampled_people)
            elif number == "06":
                mvp.run(args)
                record["evidence"] = validate_outputs(output, meta, args.max_frames)
            record["status"] = "PASS"
            print(f"[PASS] Gate {number}")
        except Exception as exc:
            failed = True
            cause, remedy = DIAGNOSIS[number]
            record.update({"status": "FAIL", "error": str(exc), "possible_causes": cause,
                           "suggested_fix": remedy, "error_type": type(exc).__name__})
            print(f"\n[FAIL] Gate {number}: {exc}")
            print(f"[원인 후보] {cause}\n[해결 방향] {remedy}")
            if not isinstance(exc, GateFailure):
                traceback.print_exc()
            print("[STOP] 다음 단계는 실행하지 않습니다. 문제 수정 후 같은 명령을 재실행하세요.")
        finally:
            report["selected_conf"] = args.conf
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if failed:
            break
    print(f"\n[REPORT] {report_path}")
    if failed:
        return 1
    print("[ALL GATES PASS] 단계별 검증 통과. 결과 영상은 직접 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
