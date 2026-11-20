"""Deterministic country-held-out RDD2022 D40-only subset."""

import argparse
from collections import Counter
import hashlib, json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import yaml
import cv2
import numpy as np
from .integrity import encode_yolo, write_content_integrity
from .audit import read_voc


def prepare_dataset(archives, root, quotas, seed=42):
    root = Path(root)
    if root.exists():
        raise FileExistsError("use a new immutable dataset directory")
    records = []
    excluded = []
    source_counts = {}
    for split, archive in archives.items():
        country = Path(archive).stem
        buckets = {"positive": [], "other_damage": [], "no_annotated_damage": []}
        classes = Counter()
        with ZipFile(archive) as z:
            names = set(z.namelist())
            for name in sorted(names):
                if not name.endswith(".xml") or "/train/" not in name:
                    continue
                raw = z.read(name)
                try:
                    doc = ET.fromstring(raw)
                    classes.update(o.findtext("name") for o in doc.findall("object"))
                    w, h, boxes = read_voc(raw)
                    image_name = f"{country}/train/images/{Path(name).stem}.jpg"
                    if image_name not in names:
                        raise ValueError("paired image missing")
                    bucket = (
                        "positive"
                        if boxes
                        else (
                            "other_damage"
                            if doc.findall("object")
                            else "no_annotated_damage"
                        )
                    )
                    buckets[bucket].append(
                        dict(
                            xml=name,
                            image_name=image_name,
                            w=w,
                            h=h,
                            boxes=boxes,
                            bucket=bucket,
                        )
                    )
                except ValueError as exc:
                    excluded.append(dict(country=country, xml=name, reason=str(exc)))
            source_counts[country] = dict(
                usable={k: len(v) for k, v in buckets.items()},
                original_classes=dict(classes),
            )
            chosen = []
            for (bucket, pool), quota in zip(
                buckets.items(), quotas[split], strict=True
            ):
                if len(pool) < quota:
                    raise ValueError(
                        f"{country} {bucket}: needs {quota}, has {len(pool)}"
                    )
                pool.sort(
                    key=lambda r: hashlib.sha256(
                        f"{seed}/{r['image_name']}".encode()
                    ).hexdigest()
                )
                chosen.extend(pool[:quota])
            (root / split / "images").mkdir(parents=True)
            (root / split / "labels").mkdir()
            for r in chosen:
                stem = Path(r["image_name"]).stem
                image = f"{split}/images/{stem}.jpg"
                label = f"{split}/labels/{stem}.txt"
                raw = z.read(r["image_name"])
                decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if decoded is None or decoded.shape[:2] != (r["h"], r["w"]):
                    raise ValueError("XML/image dimension mismatch")
                (root / image).write_bytes(raw)
                (root / label).write_bytes(encode_yolo(r["boxes"], r["w"], r["h"]))
                records.append(
                    dict(
                        split=split,
                        group=country,
                        country=country,
                        image=image,
                        label=label,
                        source_image=r["image_name"],
                        source_xml=r["xml"],
                        stratum=r["bucket"],
                        sha256=hashlib.sha256(raw).hexdigest(),
                        source_xml_sha256=hashlib.sha256(z.read(r["xml"])).hexdigest(),
                    )
                )
    manifest = dict(
        dataset="RDD2022 v1 country-held-out limited subset",
        seed=seed,
        class_map={"0": "pothole (D40)"},
        group_policy="one country per split; only official annotated train partitions",
        records=records,
    )
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (root / "source_audit.json").write_text(
        json.dumps(
            dict(
                source_counts=source_counts,
                excluded=excluded,
                policy="quarantine additional/invalid labels without editing originals",
            ),
            indent=2,
        )
    )
    (root / "data.yaml").write_text(
        yaml.safe_dump(
            dict(
                path=str(root.resolve()),
                train="train/images",
                val="val/images",
                test="test/images",
                names={0: "pothole"},
            )
        )
    )
    write_content_integrity(root)
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archives", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--split-config", type=Path)
    a = p.parse_args()
    if a.split_config:
        config = yaml.safe_load(a.split_config.read_text())
        declared = config["splits"]
        if set(declared) != {"train", "val", "test"}:
            raise ValueError("train, val and test must be declared")
        archives = {
            s: a.archives / (r["country"] + ".zip") for s, r in declared.items()
        }
        quotas = {
            s: tuple(
                int(r[k]) for k in ("positive", "other_damage", "no_annotated_damage")
            )
            for s, r in declared.items()
        }
        seed = int(config["seed"])
    else:
        archives = {
            s: a.archives / (c + ".zip")
            for s, c in [
                ("train", "India"),
                ("val", "China_MotorBike"),
                ("test", "Czech"),
            ]
        }
        quotas = dict(train=(160, 40, 40), val=(60, 30, 0), test=(60, 15, 15))
        seed = 42
    m = prepare_dataset(
        archives,
        a.output,
        quotas,
        seed=seed,
    )
    print(json.dumps(dict(images=len(m["records"]), output=str(a.output))))


if __name__ == "__main__":
    main()
