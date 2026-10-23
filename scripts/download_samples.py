"""Download exactly five Food101 images through the public HF Dataset Viewer API."""

import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATASET = "ethz/food101"
EXPECTED_REVISION = "83488de741c1bd1ce27aa6a2b33e19c7bdf92ca9"
ROWS_URL = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(
    dict(dataset=DATASET, config="default", split="train", offset=0, length=5)
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "comento-week1/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    metadata = json.loads(fetch(f"https://huggingface.co/api/datasets/{DATASET}"))
    if metadata["sha"] != EXPECTED_REVISION:
        raise RuntimeError("Dataset revision changed; use the bundled originals for exact reproduction.")
    response = json.loads(fetch(ROWS_URL))
    rows = response["rows"]
    if len(rows) != 5 or [r["row_idx"] for r in rows] != list(range(5)):
        raise RuntimeError("Expected train row indices 0–4.")
    label_names = next(f["type"]["names"] for f in response["features"] if f["name"] == "label")
    samples = []
    original_dir = ROOT / "data" / "originals"
    original_dir.mkdir(parents=True, exist_ok=True)
    # Download/validate all bytes before replacing any bundled image.
    pending = []
    for item in rows:
        index, row = item["row_idx"], item["row"]
        url = row["image"]["src"]
        if f"/--/{EXPECTED_REVISION}/--/" not in url:
            raise RuntimeError("Viewer cache revision does not match the pinned dataset.")
        content = fetch(url)
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Row {index} did not decode to an image.")
        filename = f"sample_{index + 1:02}.jpg"
        samples.append(dict(
            file=f"data/originals/{filename}", row_index=index,
            label_id=row["label"], label=label_names[row["label"]],
            sha256=hashlib.sha256(content).hexdigest(),
            shape=list(image.shape),
        ))
        pending.append((original_dir / filename, content))
    manifest = dict(dataset=DATASET, revision=EXPECTED_REVISION, split="train",
                    config="default", rows_url=ROWS_URL,
                    source="HF Dataset Viewer cached image bytes; no JPEG re-encoding",
                    samples=samples)
    old_path = ROOT / "data" / "source_manifest.json"
    if old_path.exists():
        previous = json.loads(old_path.read_text())
        if [s["sha256"] for s in previous["samples"]] != [s["sha256"] for s in samples]:
            raise RuntimeError("Source bytes changed; bundled originals were not overwritten.")
    for path, content in pending:
        path.write_bytes(content)
    old_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Downloaded and verified 5 Food101 images at", EXPECTED_REVISION)


if __name__ == "__main__":
    main()
