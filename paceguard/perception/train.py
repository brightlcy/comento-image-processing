"""Actual training, fresh initial weights for every arm."""

import argparse, csv, hashlib, json, math, os, platform, time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import yaml
from paceguard.data.integrity import validate_dataset_spec
from .interface import load_model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--project", type=Path, required=True)
    p.add_argument(
        "--allow-subset",
        action="store_true",
        help="explicit smoke subset; never a full-run claim",
    )
    a = p.parse_args()
    cfg = yaml.safe_load(a.config.read_text())
    spec = validate_dataset_spec(a.data, allow_subset=a.allow_subset)
    root = spec["root"]
    audit = spec["parent_audit"]
    if not 1 <= cfg["epochs"] <= 10:
        raise ValueError("1..10 epochs only")
    out = a.project.resolve() / cfg["name"]
    out.mkdir(parents=True, exist_ok=False)
    import torch

    torch.set_num_threads(4)
    receipt = dict(
        status="RUNNING",
        started_utc=datetime.now(timezone.utc).isoformat(),
        config=cfg,
        dataset_manifest_sha256=hashlib.sha256(
            (root / "manifest.json").read_bytes()
        ).hexdigest(),
        initial_weight_sha256=hashlib.sha256(a.weights.read_bytes()).hexdigest(),
        packages={
            x: version(x)
            for x in (
                "torch",
                "torchvision",
                "ultralytics",
                "opencv-python",
                "numpy",
                "matplotlib",
            )
        },
        hardware=dict(
            platform=platform.platform(),
            cpu_count=os.cpu_count(),
            threads=torch.get_num_threads(),
            cuda_available=torch.cuda.is_available(),
            mps_available=torch.backends.mps.is_available(),
        ),
        split_counts={s: spec["consumed_counts"][s] for s in ("train", "val")},
        effective_split_counts=spec["consumed_counts"],
        parent_audit_split_counts=audit["split_counts"],
        consumed_images={
            s: [r["image"] for r in rows]
            for s, rows in spec["records_by_split"].items()
            if s in ("train", "val")
        },
        dataset_content_sha256=spec["content_sha256"],
    )
    target = out / "receipt.json"
    target.write_text(json.dumps(receipt, indent=2))
    t = time.perf_counter()
    try:
        model = load_model(a.weights)
        model.train(
            data=str(a.data.resolve()),
            project=str(a.project.resolve()),
            exist_ok=True,
            **cfg,
        )
        rows = list(csv.DictReader((out / "results.csv").open()))
        if len(rows) != cfg["epochs"] or not all(
            math.isfinite(float(v)) for row in rows for v in row.values()
        ):
            raise ValueError("missing epochs or non-finite CSV")
        checkpoints = {
            n: dict(
                path=str(out / "weights" / n),
                sha256=hashlib.sha256((out / "weights" / n).read_bytes()).hexdigest(),
            )
            for n in ("last.pt", "best.pt")
        }
        receipt.update(
            status="PASS", epochs_completed=len(rows), checkpoints=checkpoints
        )
        receipt["actual_optimizer"] = type(model.trainer.optimizer).__name__
        steps = [
            float(state["step"])
            for state in model.trainer.optimizer.state.values()
            if "step" in state
        ]
        receipt["optimizer_steps_max_recorded"] = max(steps) if steps else None
    except Exception as exc:
        receipt.update(status="FAIL", error=repr(exc))
        raise
    finally:
        receipt.update(
            duration_s=time.perf_counter() - t,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        target.write_text(json.dumps(receipt, indent=2))
        print("TRAIN_RECEIPT", json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
