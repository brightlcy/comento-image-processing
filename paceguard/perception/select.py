"""Freeze validation-only selection and bind it to actual checkpoint bytes."""

import argparse
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from .experiment import check_metrics, choose_model
from .protocol import evaluation_protocol


def freeze_selection(receipts, weights):
    if set(receipts) != {"baseline", "resolution640"} or set(weights) != set(receipts):
        raise ValueError("two declared validation arms are required")
    scores = {}
    for arm, r in receipts.items():
        if r.get("execution_status") != "PASS" or r.get("split") != "val":
            raise ValueError("selection requires successful validation receipts")
        canonical = evaluation_protocol()
        diag = {
            k: r.get("fixed_threshold", {}).get(k)
            for k in ("confidence", "matching_iou", "small_gt_area_pixels_less_than")
        }
        expected = {k: canonical["diagnostic"][k] for k in diag}
        if (
            r.get("arm") != arm
            or r.get("evaluation_protocol") != canonical
            or r.get("evaluation_options") != canonical["ap"]
            or diag != expected
            or not r.get("dataset_content_sha256")
        ):
            raise ValueError("canonical evaluation protocol/content/arm required")
        scores[arm] = check_metrics(r["metrics"])["map50_95"]
        if (
            hashlib.sha256(Path(weights[arm]).read_bytes()).hexdigest()
            != r["model_sha256"]
        ):
            raise ValueError("checkpoint bytes do not match the evaluated model")
    a, b = receipts["baseline"], receipts["resolution640"]
    if (
        not a.get("dataset_manifest_sha256")
        or a["dataset_manifest_sha256"] != b["dataset_manifest_sha256"]
        or a["evaluation_options"] != b["evaluation_options"]
        or a["dataset_content_sha256"] != b["dataset_content_sha256"]
    ):
        raise ValueError("data and evaluation conditions must match")
    arm = choose_model(scores)
    return dict(
        schema_version=1,
        selection_source="validation",
        protocol=evaluation_protocol(),
        dataset_content_sha256=a["dataset_content_sha256"],
        selected_arm=arm,
        selected_checkpoint_sha256=receipts[arm]["model_sha256"],
        dataset_manifest_sha256=a["dataset_manifest_sha256"],
        eval_imgsz=a["evaluation_options"]["imgsz"],
        validation_scores=scores,
        frozen_utc=datetime.now(timezone.utc).isoformat(),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evaluation-dir", type=Path, required=True)
    p.add_argument("--weights-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError("frozen selection already exists")
    receipts = {
        arm: json.loads((a.evaluation_dir / (arm + "_val.json")).read_text())
        for arm in ("baseline", "resolution640")
    }
    weights = {arm: a.weights_dir / arm / "weights/last.pt" for arm in receipts}
    decision = freeze_selection(receipts, weights)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(decision, indent=2))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
