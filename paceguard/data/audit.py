"""Fail-closed image, label and cross-split identity/group audit."""

import argparse
from collections import Counter
import hashlib, json
from pathlib import Path
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from paceguard.perception.geometry import parse_yolo, validate_xyxy


def read_voc(raw):
    try:
        doc = ET.fromstring(raw)
        w = int(doc.findtext("size/width"))
        h = int(doc.findtext("size/height"))
        if min(w, h) <= 0:
            raise ValueError("nonpositive image size")
        boxes = []
        for obj in doc.findall("object"):
            name = obj.findtext("name")
            if name not in {"D00", "D10", "D20", "D40"}:
                raise ValueError(f"unsupported RDD damage class: {name}")
            box = validate_xyxy(
                tuple(
                    float(obj.findtext("bndbox/" + k))
                    for k in ("xmin", "ymin", "xmax", "ymax")
                ),
                w,
                h,
            )
            if name == "D40":
                boxes.append((0, box))
        return w, h, boxes
    except (ET.ParseError, TypeError, OverflowError) as exc:
        raise ValueError("invalid VOC annotation") from exc


def _dhash(im):
    g = cv2.resize(
        cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA
    )
    return int.from_bytes(np.packbits(g[:, 1:] > g[:, :-1]).tobytes(), "big")


def audit_dataset(root):
    root = Path(root).resolve()
    errors = []
    from .integrity import verify_content_integrity

    try:
        content_sha256 = verify_content_integrity(root)
    except (OSError, ValueError) as exc:
        content_sha256 = None
        errors.append(f"content integrity: {exc}")
    files = []
    counts = Counter()
    boxes = Counter()
    negatives = Counter()
    groups = {}
    images = set()
    labels = set()
    for r in json.loads((root / "manifest.json").read_text())["records"]:
        s = r["split"]
        try:
            if s not in {"train", "val", "test"} or not r.get("group"):
                raise ValueError("missing group or invalid split")
            if r["group"] in groups and groups[r["group"]] != s:
                raise ValueError("source group crosses splits")
            groups[r["group"]] = s
            impath = (root / r["image"]).resolve()
            lab = (root / r["label"]).resolve()
            if (
                impath.parent != root / s / "images"
                or lab.parent != root / s / "labels"
                or impath.stem != lab.stem
            ):
                raise ValueError("path/pair mismatch")
            if impath in images:
                raise ValueError("duplicate manifest image")
            images.add(impath)
            labels.add(lab)
            raw = impath.read_bytes()
            if not raw:
                raise ValueError("empty image file")
            im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if im is None or im.size == 0:
                raise ValueError("image decode failed")
            h, w = im.shape[:2]
            ann = [
                parse_yolo(line, 1, w, h)
                for line in lab.read_text().splitlines()
                if line.strip()
            ]
            if r.get("stratum") == "positive" and not ann:
                raise ValueError("positive stratum has no target annotation")
            sha = hashlib.sha256(raw).hexdigest()
            if r.get("sha256") and r["sha256"] != sha:
                raise ValueError("image SHA256 mismatch")
            counts[s] += 1
            boxes[s] += len(ann)
            negatives[s] += not ann
            files.append(
                dict(
                    image=r["image"],
                    split=s,
                    group=r["group"],
                    width=w,
                    height=h,
                    sha256=sha,
                    pixel_sha256=hashlib.sha256(
                        str(im.shape).encode() + im.tobytes()
                    ).hexdigest(),
                    dhash=f"{_dhash(im):016x}",
                    boxes=len(ann),
                )
            )
        except (OSError, ValueError, cv2.error) as exc:
            errors.append(f"{r.get('image')}: {exc}")
    for s in ("train", "val", "test"):
        actual = {p.resolve() for p in (root / s / "images").glob("*") if p.is_file()}
        if actual != {p for p in images if p.parent == root / s / "images"}:
            errors.append(f"{s}: image manifest mismatch")
        actual = {p.resolve() for p in (root / s / "labels").glob("*.txt")}
        if actual != {p for p in labels if p.parent == root / s / "labels"}:
            errors.append(f"{s}: orphan or missing label")
        if counts[s] == 0:
            errors.append(f"{s}: no valid images")
    for i, a in enumerate(files):
        for b in files[i + 1 :]:
            if a["split"] == b["split"]:
                continue
            if a["sha256"] == b["sha256"] or a["pixel_sha256"] == b["pixel_sha256"]:
                errors.append(f"cross-split duplicate: {a['image']} / {b['image']}")
            elif (int(a["dhash"], 16) ^ int(b["dhash"], 16)).bit_count() <= 2:
                errors.append(
                    f"cross-split near duplicate dHash<=2: {a['image']} / {b['image']}"
                )
    return dict(
        status="FAIL" if errors else "PASS",
        errors=errors,
        content_sha256=content_sha256,
        split_counts=dict(counts),
        box_counts=dict(boxes),
        negative_counts=dict(negatives),
        files=files,
        source_groups=groups,
        near_duplicate_policy="cross-split dHash Hamming <=2 blocks training",
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    r = audit_dataset(a.root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(r, indent=2))
    print(
        json.dumps(
            {k: v for k, v in r.items() if k not in {"files", "source_groups"}},
            indent=2,
        )
    )
    raise SystemExit(0 if r["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
