"""Explicit reproducible smoke membership; not another independent experiment."""

import argparse, json
from pathlib import Path
import yaml
from .integrity import validate_dataset_spec


def make_smoke(data, output, train_count=20, val_count=10):
    spec = validate_dataset_spec(data)
    root = spec["root"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cfg = {"path": str(root), "names": {0: "pothole"}}
    membership = {}
    manifest = json.loads((root / "manifest.json").read_text())["records"]
    for split, count in [("train", train_count), ("val", val_count)]:
        rows = [r for r in manifest if r["split"] == split]
        if type(count) is not int or count < 1 or len(rows) < count:
            raise ValueError("invalid smoke count")
        rows = rows[:count]
        p = output / (split + ".txt")
        p.write_text("".join(str(root / r["image"]) + "\n" for r in rows))
        cfg[split] = str(p.resolve())
        membership[split] = [r["image"] for r in rows]
    (output / "membership.json").write_text(json.dumps(membership, indent=2))
    p = output / "data.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(make_smoke(a.data, a.output))


if __name__ == "__main__":
    main()
