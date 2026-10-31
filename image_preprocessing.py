"""Comento Week 1: pixel processing, deterministic preprocessing and outlier filtering."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
DARK_THRESHOLD = 50.0  # arithmetic mean of 8-bit BGR→GRAY pixels; reject strictly below
MIN_RED_RATIO = 0.05  # largest 8-connected red region pixels / total pixels
PARAMETERS = dict(size=[224, 224], blur_kernel=[5, 5], blur_sigma=1.0,
                  rotation_degrees=15.0, saturation_factor=1.25, value_factor=1.10,
                  dark_threshold=DARK_THRESHOLD, min_red_ratio=MIN_RED_RATIO)


def validate_image(image: np.ndarray) -> None:
    """Require a nonempty uint8 H×W×3 BGR image."""
    if (not isinstance(image, np.ndarray) or image.size == 0 or image.ndim != 3
            or image.shape[2] != 3 or image.dtype != np.uint8):
        raise ValueError("Expected a nonempty uint8 BGR image with shape (H, W, 3).")


def load_image(path: str | Path) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Empty image file: {path}")
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode image file: {path}")
    validate_image(image)
    return image


def analyze_pixels(image: np.ndarray) -> dict:
    validate_image(image)
    height, width = image.shape[:2]
    return dict(shape=list(image.shape), dtype=str(image.dtype),
                mean_bgr=[float(x) for x in image.mean(axis=(0, 1))],
                center_bgr=image[height // 2, width // 2].tolist(),
                minimum=int(image.min()), maximum=int(image.max()))


def detect_red(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """HSV 8-bit H:0–179. Include both red hue ends, S>=120, V>=70."""
    validate_image(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    low = cv2.inRange(hsv, (0, 120, 70), (10, 255, 255))
    high = cv2.inRange(hsv, (170, 120, 70), (179, 255, 255))
    mask = cv2.bitwise_or(low, high)
    filtered = cv2.bitwise_and(image, image, mask=mask)
    return mask, filtered


def threshold_brightness(image: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Binary grayscale intensity threshold; a different question from color detection."""
    validate_image(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return binary


def largest_red_ratio(mask: np.ndarray) -> float:
    """Count actual connected foreground pixels, rather than enclosing rectangle area."""
    if (not isinstance(mask, np.ndarray) or mask.size == 0 or mask.ndim != 2
            or mask.dtype != np.uint8):
        raise ValueError("Expected a nonempty uint8 2D mask.")
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    largest = int(stats[1:, cv2.CC_STAT_AREA].max()) if count > 1 else 0
    return largest / mask.size


def evaluate_outlier(image: np.ndarray, dark_threshold: float = DARK_THRESHOLD,
                     min_red_ratio: float = MIN_RED_RATIO) -> dict:
    """Red-target demonstration only: red region size is not general object detection."""
    validate_image(image)
    if not (np.isfinite(dark_threshold) and 0 <= dark_threshold <= 255
            and np.isfinite(min_red_ratio) and 0 <= min_red_ratio <= 1):
        raise ValueError("Brightness threshold must be 0–255 and area ratio must be 0–1.")
    brightness = float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).mean())
    mask, _ = detect_red(image)
    ratio = largest_red_ratio(mask)
    too_dark, too_small = brightness < dark_threshold, ratio < min_red_ratio
    reasons = []
    if too_dark:
        reasons.append("too_dark")
    if too_small:
        reasons.append("small_red_region")
    return dict(mean_brightness=brightness, largest_red_ratio=ratio,
                dark_threshold=dark_threshold, min_red_ratio=min_red_ratio,
                too_dark=too_dark, too_small_red_region=too_small,
                rejected=bool(reasons), reasons=reasons)


def change_color(image: np.ndarray) -> np.ndarray:
    validate_image(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    adjusted = hsv.astype(np.float32)
    adjusted[:, :, 1] *= PARAMETERS["saturation_factor"]
    adjusted[:, :, 2] *= PARAMETERS["value_factor"]
    adjusted = np.rint(np.clip(adjusted, 0, 255)).astype(np.uint8)
    return cv2.cvtColor(adjusted, cv2.COLOR_HSV2BGR)


def preprocess_image(image: np.ndarray) -> dict[str, np.ndarray]:
    """A single sequential pipeline; color augmentation precedes grayscale."""
    validate_image(image)
    resized = cv2.resize(image, (224, 224), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(resized, (5, 5), 1.0, borderType=cv2.BORDER_REFLECT_101)
    flipped = cv2.flip(blurred, 1)
    matrix = cv2.getRotationMatrix2D((111.5, 111.5), PARAMETERS["rotation_degrees"], 1.0)
    rotated = cv2.warpAffine(flipped, matrix, (224, 224), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT_101)
    color_changed = change_color(rotated)
    grayscale = cv2.cvtColor(color_changed, cv2.COLOR_BGR2GRAY)
    normalized = grayscale.astype(np.float32) / np.float32(255.0)
    return dict(resized=resized, blurred=blurred, flipped=flipped,
                rotated=rotated, color_changed=color_changed,
                grayscale=grayscale, normalized=normalized)


def make_outlier_examples() -> dict[str, np.ndarray]:
    """Synthetic inputs with known answers, not mislabeled photographs."""
    normal = np.full((100, 100, 3), 180, np.uint8)
    normal[25:75, 25:75] = (0, 0, 255)  # 25% red connected region
    dark = np.rint(normal.astype(np.float32) * 0.1).astype(np.uint8)
    small = np.full_like(normal, 180)
    small[45:55, 45:55] = (0, 0, 255)  # 1% red connected region
    return dict(normal=normal, dark=dark, small=small)


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not save image: {path}")


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def run(input_dir: Path, output_dir: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    files = sorted(input_dir.glob("*.jpg"))
    expected = manifest["samples"]
    if len(files) != 5 or [p.name for p in files] != [Path(x["file"]).name for x in expected]:
        raise ValueError("Expected exactly five source JPEGs matching source_manifest.json.")
    # Fail before generating outputs if any source is corrupt or has changed.
    images = []
    for path, entry in zip(files, expected):
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Source SHA256 mismatch: {path.name}")
        images.append(load_image(path))
    samples_dir = output_dir / "preprocessed_samples"
    if samples_dir.exists() and any(p.suffix != ".png" or p.stem not in {f"sample_{i:02}" for i in range(1, 6)}
                                    for p in samples_dir.iterdir()):
        raise ValueError("Output samples directory contains unrelated files; use a clean output directory.")
    results_dir = output_dir / "results"
    metrics, decisions = [], []
    for path, source, entry in zip(files, images, expected):
        stem = path.stem
        stages = preprocess_image(source)
        mask, filtered = detect_red(source)
        decision = evaluate_outlier(source)  # original resolution, before augmentations
        normalized_path = results_dir / "normalized" / f"{stem}.npy"
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(normalized_path, stages["normalized"], allow_pickle=False)
        preview = np.rint(stages["normalized"] * np.float32(255.0)).astype(np.uint8)
        save_image(samples_dir / f"{stem}.png", preview)
        for name, array in dict(original=source, mask=mask, red_filtered=filtered,
                                brightness_threshold=threshold_brightness(source)).items():
            save_image(results_dir / "color_detection" / f"{stem}_{name}.png", array)
        if stem == "sample_01":
            for name, array in stages.items():
                if name != "normalized":
                    save_image(results_dir / "demo" / f"{name}.png", array)
        # Keep demonstration outputs for all 5; training admission is explicitly separate.
        accepted_path = results_dir / "accepted" / f"{stem}.npy"
        if not decision["rejected"]:
            accepted_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(accepted_path, stages["normalized"], allow_pickle=False)
        elif accepted_path.exists():
            accepted_path.unlink()  # remove only a known obsolete generated admission
        metrics.append(dict(sample=stem, label=entry["label"], source=analyze_pixels(source),
                            normalized_shape=list(stages["normalized"].shape),
                            normalized_dtype=str(stages["normalized"].dtype),
                            normalized_min=float(stages["normalized"].min()),
                            normalized_max=float(stages["normalized"].max()),
                            red_pixels=int(np.count_nonzero(mask)),
                            blur_mean_absolute_change=float(np.abs(stages["blurred"].astype(float)
                                                                  - stages["resized"].astype(float)).mean()),
                            preview_sha256=hashlib.sha256((samples_dir / f"{stem}.png").read_bytes()).hexdigest()))
        decisions.append(dict(sample=stem, kind="Food101 photograph", **decision))
    synthetic = []
    for name, image in make_outlier_examples().items():
        decision = evaluate_outlier(image)
        synthetic.append(dict(sample=name, kind="synthetic known-answer fixture", **decision))
        save_image(results_dir / "outlier_examples" / f"{name}.png", image)
    write_json(results_dir / "metrics.json", metrics)
    write_json(results_dir / "outlier_decisions.json", dict(photographs=decisions, synthetic=synthetic))
    summary = dict(python=platform.python_version(), opencv=cv2.__version__, numpy=np.__version__,
                   parameters=PARAMETERS, input_count=len(files), demonstration_png_count=5,
                   accepted_count=sum(not d["rejected"] for d in decisions),
                   rejected_count=sum(d["rejected"] for d in decisions),
                   normalization="float32 gray / 255.0; NPY holds numeric data; PNG is uint8 preview",
                   note="Red-region admission is a limited red-target example, not a Food101 quality classifier.")
    write_json(results_dir / "run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data" / "originals")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "source_manifest.json")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.input_dir, args.output_dir, args.manifest), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, cv2.error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
