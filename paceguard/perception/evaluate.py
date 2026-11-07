"""Common-condition AP and one-to-one fixed-threshold diagnostics."""

import argparse, csv, hashlib, json, time, math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .geometry import iou, parse_yolo
from .interface import Detection, load_model, predict_image
from .visualize import read_bgr
from .experiment import check_metrics
from .protocol import evaluation_protocol
from paceguard.data.integrity import validate_dataset_spec


def match_detections(
    ground_truth, predictions, conf=0.25, threshold=0.5, small_area=1024
):
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (conf, threshold)):
        raise ValueError("invalid matching confidence/IoU threshold")
    if not math.isfinite(small_area) or small_area <= 0:
        raise ValueError("invalid small-object area")
    if len({d.frame_id for d in (*ground_truth, *predictions)}) > 1:
        raise ValueError("different frames")
    predictions = sorted(
        (d for d in predictions if d.confidence >= conf), key=lambda d: -d.confidence
    )
    matched = set()
    for p in predictions:
        c = [
            (iou(g.box_xyxy, p.box_xyxy), i)
            for i, g in enumerate(ground_truth)
            if i not in matched and g.class_id == p.class_id
        ]
        if c:
            score, index = max(c)
            if score >= threshold:
                matched.add(index)
    small = {
        i
        for i, g in enumerate(ground_truth)
        if (g.box_xyxy[2] - g.box_xyxy[0]) * (g.box_xyxy[3] - g.box_xyxy[1])
        < small_area
    }
    return dict(
        tp=len(matched),
        fp=len(predictions) - len(matched),
        fn=len(ground_truth) - len(matched),
        small_tp=len(small & matched),
        small_fn=len(small - matched),
        large_tp=len(matched - small),
        large_fn=len(ground_truth) - len(small) - len(matched - small),
    )


def authorize_test(s, wsha, dsha, *, arm, content_sha256):
    if (
        s.get("schema_version") != 1
        or s.get("selection_source") != "validation"
        or s.get("selected_checkpoint_sha256") != wsha
        or s.get("dataset_manifest_sha256") != dsha
        or s.get("dataset_content_sha256") != content_sha256
        or not content_sha256
        or s.get("eval_imgsz") != evaluation_protocol()["ap"]["imgsz"]
        or s.get("selected_arm") != arm
        or s.get("protocol") != evaluation_protocol()
    ):
        raise ValueError("frozen validation selection/protocol/content/arm mismatch")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--split", choices=["val", "test"], required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--selection", type=Path)
    a = p.parse_args()
    spec = validate_dataset_spec(a.data)
    root = spec["root"]
    wsha = hashlib.sha256(a.weights.read_bytes()).hexdigest()
    dsha = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    target = a.output_dir / f"{a.name}_{a.split}.json"
    if target.exists():
        raise FileExistsError("evaluation exists; use new output directory")
    if a.split == "test":
        if a.selection is None:
            raise ValueError("selection required")
        authorize_test(
            json.loads(a.selection.read_text()),
            wsha,
            dsha,
            arm=a.name,
            content_sha256=spec["content_sha256"],
        )
        with (a.output_dir / "test_access.jsonl").open("x") as f:
            f.write(
                json.dumps(
                    dict(
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        weight_sha256=wsha,
                        manifest_sha256=dsha,
                        content_sha256=spec["content_sha256"],
                        protocol=evaluation_protocol(),
                        arm=a.name,
                        purpose="one final test session: AP and fixed-threshold diagnostics",
                    )
                )
                + "\n"
            )
    import torch

    torch.set_num_threads(4)
    model = load_model(a.weights)
    protocol = evaluation_protocol()
    opts = protocol["ap"]
    t = time.perf_counter()
    m = model.val(
        data=str(a.data.resolve()),
        split=a.split,
        project=str((a.output_dir / "native").resolve()),
        name=f"{a.name}_{a.split}",
        **opts,
    )
    numbers = check_metrics(
        dict(
            precision=float(m.box.mp),
            recall=float(m.box.mr),
            map50=float(m.box.map50),
            map50_95=float(m.box.map),
        )
    )
    receipt = dict(
        execution_status="PASS",
        split=a.split,
        arm=a.name,
        metrics=numbers,
        model_sha256=wsha,
        dataset_manifest_sha256=dsha,
        evaluation_options=opts,
        evaluation_protocol=protocol,
        dataset_content_sha256=spec["content_sha256"],
        consumed_images=[r["image"] for r in spec["records_by_split"][a.split]],
        ap_evaluation_wall_s=time.perf_counter() - t,
        library_speed_ms=m.speed,
        per_class=[
            dict(
                class_id=int(c),
                name=m.names[int(c)],
                precision=float(m.box.p[i]),
                recall=float(m.box.r[i]),
                ap50=float(m.box.ap50[i]),
                ap50_95=float(m.box.ap[i]),
            )
            for i, c in enumerate(m.box.ap_class_index)
        ],
    )
    records = spec["records_by_split"][a.split]
    diag = protocol["diagnostic"]
    rows = []
    t = time.perf_counter()
    for frame_id, r in enumerate(records):
        im = read_bgr(root / r["image"])
        h, w = im.shape[:2]
        gt = [
            Detection(b, c, 1.0, frame_id)
            for line in (root / r["label"]).read_text().splitlines()
            for c, b in [parse_yolo(line, 1, w, h)]
        ]
        ds = predict_image(
            model,
            im,
            frame_id=frame_id,
            imgsz=diag["imgsz"],
            conf=diag["confidence"],
            device=diag["device"],
        )
        counts = match_detections(
            gt,
            ds,
            conf=diag["confidence"],
            threshold=diag["matching_iou"],
            small_area=diag["small_gt_area_pixels_less_than"],
        )
        rows.append(
            dict(
                image=r["image"],
                stratum=r["stratum"],
                ground_truth=[asdict(d) for d in gt],
                predictions=[asdict(d) for d in ds],
                counts=counts,
            )
        )
    total = {
        k: sum(r["counts"][k] for r in rows)
        for k in ("tp", "fp", "fn", "small_tp", "small_fn", "large_tp", "large_fn")
    }
    neg = [r for r in rows if not r["ground_truth"]]
    total.update(
        confidence=diag["confidence"],
        matching_iou=diag["matching_iou"],
        small_gt_area_pixels_less_than=diag["small_gt_area_pixels_less_than"],
        small_recall=(
            total["small_tp"] / (total["small_tp"] + total["small_fn"])
            if total["small_tp"] + total["small_fn"]
            else None
        ),
        negative_images=len(neg),
        negative_images_with_fp=sum(r["counts"]["fp"] > 0 for r in neg),
        precision=(
            total["tp"] / (total["tp"] + total["fp"])
            if total["tp"] + total["fp"]
            else 0.0
        ),
        recall=(
            total["tp"] / (total["tp"] + total["fn"])
            if total["tp"] + total["fn"]
            else 0.0
        ),
    )
    receipt.update(
        fixed_threshold=total,
        diagnostic_wall_s=time.perf_counter() - t,
        images=len(rows),
        finished_utc=datetime.now(timezone.utc).isoformat(),
        warning="annotation agreement only; no distance/frame-age/driving-safety claim",
    )
    target.write_text(json.dumps(receipt, indent=2))
    (a.output_dir / f"{a.name}_{a.split}_detections.json").write_text(
        json.dumps(rows, indent=2)
    )
    with (a.output_dir / f"{a.name}_{a.split}_counts.csv").open("w") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image",
                "stratum",
                "tp",
                "fp",
                "fn",
                "small_tp",
                "small_fn",
                "large_tp",
                "large_fn",
            ],
        )
        writer.writeheader()
        writer.writerows(
            dict(image=r["image"], stratum=r["stratum"], **r["counts"]) for r in rows
        )
    print("EVALUATION_RECEIPT", json.dumps(receipt))


if __name__ == "__main__":
    main()
