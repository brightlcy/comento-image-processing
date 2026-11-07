"""Single-variable comparisons and finite metrics."""

import math


def validate_pair(a, b):
    d = {
        k: [a.get(k), b.get(k)]
        for k in a.keys() | b.keys()
        if k != "name" and a.get(k) != b.get(k)
    }
    if set(d) != {"imgsz"}:
        raise ValueError(f"only imgsz may differ: {d}")
    return d


def check_metrics(m):
    keys = ("precision", "recall", "map50", "map50_95")
    if any(k not in m or not math.isfinite(m[k]) or not 0 <= m[k] <= 1 for k in keys):
        raise ValueError("missing or invalid metric")
    return {k: float(m[k]) for k in keys}


def choose_model(scores):
    if set(scores) != {"baseline", "resolution640"} or not all(
        math.isfinite(v) and 0 <= v <= 1 for v in scores.values()
    ):
        raise ValueError("two validation scores required")
    return (
        "resolution640"
        if scores["resolution640"] > scores["baseline"] + 1e-6
        else "baseline"
    )
