"""Run the existing tests and compare a fresh run with every submitted processing output."""

import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    evidence = ROOT / "docs/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    ]
    tested = subprocess.run(commands[0], cwd=ROOT, capture_output=True, text=True)
    transcript = tested.stdout + tested.stderr
    (evidence / "unittest.log").write_text(transcript)
    count = re.search(r"Ran (\d+) tests?", transcript)
    comparisons = []
    with tempfile.TemporaryDirectory(prefix="comento-week1-") as directory:
        command = [sys.executable, "image_preprocessing.py", "--output-dir", directory]
        rerun = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (evidence / "reproduction.log").write_text(rerun.stdout + rerun.stderr)
        if rerun.returncode == 0:
            generated = Path(directory)
            for parent in ["preprocessed_samples", "results"]:
                baseline = {p.relative_to(ROOT) for p in (ROOT / parent).rglob("*") if p.is_file()}
                repeated = {p.relative_to(generated) for p in (generated / parent).rglob("*") if p.is_file()}
                if baseline != repeated:
                    raise RuntimeError(f"Output file lists differ in {parent}")
                for relative in sorted(baseline):
                    first, second = sha256(ROOT / relative), sha256(generated / relative)
                    comparisons.append(dict(file=str(relative), sha256=first, repeated_sha256=second,
                                            identical=first == second))
    report = dict(
        python=platform.python_version(), platform=platform.system(), machine=platform.machine(),
        test_command="python -m unittest discover -s tests -v",
        test_exit_code=tested.returncode, tests_run=int(count.group(1)) if count else 0,
        reproduction_command="python image_preprocessing.py --output-dir <temporary-directory>",
        reproduction_exit_code=rerun.returncode,
        compared_files=len(comparisons), all_files_identical=bool(comparisons) and all(x["identical"] for x in comparisons),
        source_sha256={name: sha256(ROOT / name) for name in [
            "image_preprocessing.py", "scripts/download_samples.py", "scripts/verify_results.py",
            "tests/test_image_preprocessing.py", "requirements.txt", "data/source_manifest.json"]},
        comparisons=comparisons,
    )
    passed = (tested.returncode == 0 and report["tests_run"] > 0
              and rerun.returncode == 0 and report["all_files_identical"])
    report["passed"] = passed
    (evidence / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ["comparisons", "source_sha256"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
