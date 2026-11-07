"""Bind consumed image/label bytes and verify the provider's effective membership."""

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import cv2
import numpy as np
import yaml


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode_yolo(boxes, width, height):
    lines = []
    for cls, (x1, y1, x2, y2) in boxes:
        values = (
            (x1 + x2) / (2 * width),
            (y1 + y2) / (2 * height),
            (x2 - x1) / width,
            (y2 - y1) / height,
        )
        lines.append(str(cls) + " " + " ".join(format(v, ".17g") for v in values))
    return ("\n".join(lines) + ("\n" if lines else "")).encode()


def _snapshot(root):
    root = Path(root).resolve()
    manifest = root / "manifest.json"
    rows = []
    for r in json.loads(manifest.read_text())["records"]:
        row = {"split": r["split"]}
        for key in ("image", "label"):
            p = (root / r[key]).resolve()
            if not p.is_relative_to(root):
                raise ValueError("content integrity path outside dataset")
            row[key] = r[key]
            row[key + "_sha256"] = digest(p)
        rows.append(row)
    return dict(schema_version=1, manifest_sha256=digest(manifest), records=rows)


def write_content_integrity(root):
    """Internal seal for freshly converted, source-verified data, never a repair bypass."""
    p = Path(root) / "content_integrity.json"
    if p.exists():
        raise FileExistsError("content integrity already sealed")
    p.write_text(json.dumps(_snapshot(root), indent=2))
    return digest(p)


def verify_content_integrity(root):
    p = Path(root) / "content_integrity.json"
    if not p.is_file():
        raise ValueError("content integrity missing; prepare or verify originals first")
    if json.loads(p.read_text()) != _snapshot(root):
        raise ValueError("content integrity image/label/manifest mismatch")
    return digest(p)


def verify_source_and_seal(root, archives):
    """Add a sidecar to historical data only after matching the recorded originals."""
    from .audit import read_voc

    root = Path(root)
    records = json.loads((root / "manifest.json").read_text())["records"]
    with ExitStack() as stack:
        sources = {}
        for r in records:
            country = r["country"]
            if country not in sources:
                sources[country] = stack.enter_context(
                    ZipFile(Path(archives) / (country + ".zip"))
                )
            z = sources[country]
            image = z.read(r["source_image"])
            xml = z.read(r["source_xml"])
            if (
                hashlib.sha256(image).hexdigest() != r["sha256"]
                or hashlib.sha256(xml).hexdigest() != r["source_xml_sha256"]
            ):
                raise ValueError("recorded source hash mismatch")
            w, h, boxes = read_voc(xml)
            decoded = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
            if decoded is None or decoded.shape[:2] != (h, w):
                raise ValueError("source XML/image dimension mismatch")
            if (root / r["image"]).read_bytes() != image or (
                root / r["label"]
            ).read_bytes() != encode_yolo(boxes, w, h):
                raise ValueError("converted image/label differs from recorded source")
    p = root / "content_integrity.json"
    sha = (
        verify_content_integrity(root) if p.exists() else write_content_integrity(root)
    )
    return dict(
        source_pairs_verified=len(records),
        source_dimensions_mismatched=0,
        content_sha256=sha,
        manifest_sha256=digest(root / "manifest.json"),
    )


def validate_dataset_spec(data, *, allow_subset=False):
    from .audit import audit_dataset

    cfg = yaml.safe_load(Path(data).read_text())
    root = Path(cfg["path"])
    if not root.is_absolute():
        raise ValueError("absolute data root required; use prepare-generated YAML")
    root = root.resolve()
    names = cfg.get("names")
    if isinstance(names, list):
        names = dict(enumerate(names))
    if names != {0: "pothole"} or cfg.get("nc", 1) != 1:
        raise ValueError("dataset class map must be 0: pothole")
    audit = audit_dataset(root)
    if audit["status"] != "PASS":
        raise ValueError(f"dataset audit/integrity failed: {audit['errors']}")
    content = verify_content_integrity(root)
    records = json.loads((root / "manifest.json").read_text())["records"]
    selected = {}
    counts = {}
    required = {"train", "val"} if allow_subset else {"train", "val", "test"}
    if not required.issubset(cfg):
        raise ValueError("all declared splits required; subset needs explicit opt-in")
    formats = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
        ".dng",
        ".mpo",
        ".pfm",
        ".heic",
        ".avif",
    }
    for split in ("train", "val", "test"):
        if split not in cfg:
            continue
        raw = cfg[split]
        if not isinstance(raw, str):
            raise ValueError("split must be a directory or a .txt list")
        p = (root / raw).resolve()
        if p.is_dir():
            actual = sorted(
                x.resolve()
                for x in p.rglob("*")
                if x.is_file() and x.suffix.lower() in formats
            )
        elif p.is_file() and p.suffix == ".txt":
            actual = []
            for line in p.read_text().splitlines():
                if not line.strip():
                    continue
                q = Path(line.strip())
                if not q.is_absolute():
                    if not line.startswith("./"):
                        raise ValueError(
                            "list images must be absolute or ./ relative to list"
                        )
                    q = p.parent / q
                actual.append(q.resolve())
        else:
            raise ValueError("split image membership path missing")
        expected = {
            str((root / r["image"]).resolve()): r
            for r in records
            if r["split"] == split
        }
        keys = [str(x) for x in actual]
        if not keys or len(set(keys)) != len(keys) or not set(keys).issubset(expected):
            raise ValueError("split image membership mismatch")
        if not allow_subset and (set(keys) != set(expected) or p.is_file()):
            raise ValueError(
                "full split membership required; subset needs explicit opt-in"
            )
        selected[split] = [expected[k] for k in keys]
        counts[split] = len(keys)
    return dict(
        root=root,
        parent_audit=audit,
        consumed_counts=counts,
        records_by_split=selected,
        content_sha256=content,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--archives", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify_source_and_seal(a.root, a.archives)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
