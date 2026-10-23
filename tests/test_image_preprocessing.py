"""Small known-answer checks for the assignment; no external test framework."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

from image_preprocessing import (
    ROOT, analyze_pixels, change_color, detect_red, evaluate_outlier,
    largest_red_ratio, load_image, make_outlier_examples, preprocess_image,
    run, save_image, threshold_brightness, validate_image,
)


class InputTests(unittest.TestCase):
    def test_valid_file_loads_as_bgr(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "red.png"
            save_image(path, np.full((8, 9, 3), (0, 0, 255), np.uint8))
            image = load_image(path)
            self.assertEqual(image.shape, (8, 9, 3))
            self.assertEqual(image[0, 0].tolist(), [0, 0, 255])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_image(Path(directory) / "missing.png")

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.png"
            path.touch()
            with self.assertRaisesRegex(ValueError, "Empty"):
                load_image(path)

    def test_corrupt_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.jpg"
            path.write_text("this is not an image")
            with self.assertRaisesRegex(ValueError, "decode"):
                load_image(path)

    def test_invalid_arrays(self):
        for image in [None, [], np.empty((0, 2, 3), np.uint8), np.zeros((5, 5), np.uint8),
                      np.zeros((2, 2, 4), np.uint8), np.zeros((5, 5, 3), np.float32)]:
            with self.subTest(shape=getattr(image, "shape", None)):
                with self.assertRaises(ValueError):
                    validate_image(image)

    def test_cli_missing_input_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "image_preprocessing.py"),
                                     "--input-dir", str(Path(directory) / "missing"),
                                     "--output-dir", directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)


class PixelTests(unittest.TestCase):
    def test_pixel_statistics_known_bgr(self):
        image = np.full((2, 3, 3), (10, 20, 30), np.uint8)
        stats = analyze_pixels(image)
        self.assertEqual(stats["mean_bgr"], [10.0, 20.0, 30.0])
        self.assertEqual(stats["center_bgr"], [10, 20, 30])

    def test_red_hue_boundaries(self):
        hues = [0, 10, 11, 169, 170, 179]
        hsv = np.array([[[h, 255, 255] for h in hues]], np.uint8)
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        mask, result = detect_red(bgr)
        self.assertEqual(mask[0].tolist(), [255, 255, 0, 0, 255, 255])
        np.testing.assert_array_equal(result[mask == 255], bgr[mask == 255])
        self.assertTrue(np.all(result[mask == 0] == 0))

    def test_saturation_and_value_boundaries(self):
        hsv = np.array([[[0, 119, 255], [0, 120, 255], [0, 255, 69], [0, 255, 70]]], np.uint8)
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        mask, _ = detect_red(bgr)
        self.assertEqual(mask[0].tolist(), [0, 255, 0, 255])

    def test_red_and_blue_are_not_swapped(self):
        bgr = np.array([[[0, 0, 255], [255, 0, 0], [0, 255, 0], [255, 255, 255]]], np.uint8)
        mask, _ = detect_red(bgr)
        self.assertEqual(mask[0].tolist(), [255, 0, 0, 0])

    def test_threshold_is_strictly_greater_than_127(self):
        image = np.array([[[126] * 3, [127] * 3, [128] * 3]], np.uint8)
        self.assertEqual(threshold_brightness(image)[0].tolist(), [0, 0, 255])

    def test_threshold_is_not_a_red_mask(self):
        image = np.array([[[0, 0, 255], [255, 255, 255]]], np.uint8)
        red, _ = detect_red(image)
        bright = threshold_brightness(image)
        self.assertEqual(red[0].tolist(), [255, 0])
        self.assertEqual(bright[0].tolist(), [0, 255])


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        yy, xx = np.indices((224, 224))
        self.image = np.stack([xx, yy, (xx + yy) % 256], axis=-1).astype(np.uint8)
        self.stages = preprocess_image(self.image)

    def test_dimensions_dtype_and_channels(self):
        for name, array in self.stages.items():
            self.assertEqual(array.shape[:2], (224, 224), name)
            if name in ["grayscale", "normalized"]:
                self.assertEqual(array.ndim, 2, name)
            else:
                self.assertEqual(array.shape[2], 3, name)
        self.assertEqual(self.stages["grayscale"].dtype, np.uint8)
        self.assertEqual(self.stages["normalized"].dtype, np.float32)

    def test_normalization_numeric_contract(self):
        normalized, gray = self.stages["normalized"], self.stages["grayscale"]
        self.assertTrue(np.isfinite(normalized).all())
        self.assertGreaterEqual(float(normalized.min()), 0)
        self.assertLessEqual(float(normalized.max()), 1)
        np.testing.assert_allclose(normalized * 255, gray, atol=2e-5)
        black = preprocess_image(np.zeros((224, 224, 3), np.uint8))["normalized"]
        white = preprocess_image(np.full((224, 224, 3), 255, np.uint8))["normalized"]
        self.assertEqual(float(black.min()), 0.0)
        self.assertEqual(float(white.max()), 1.0)

    def test_blur_spreads_impulse_and_reduces_peak(self):
        impulse = np.zeros((224, 224, 3), np.uint8)
        impulse[112, 112] = 255
        blurred = preprocess_image(impulse)["blurred"]
        self.assertGreater(int(blurred[112, 112, 0]), 0)
        self.assertLess(int(blurred[112, 112, 0]), 255)
        self.assertGreater(int(blurred[112, 113, 0]), 0)
        self.assertEqual(int(blurred[100, 100, 0]), 0)

    def test_flip_reverses_columns(self):
        np.testing.assert_array_equal(self.stages["flipped"], self.stages["blurred"][:, ::-1])

    def test_rotation_moves_known_marker_counterclockwise(self):
        image = np.zeros((224, 224, 3), np.uint8)
        image[107:117, 175:185] = 255
        rotated = preprocess_image(image)["rotated"][:, :, 0]
        yy, xx = np.indices(rotated.shape)
        x = float((xx * rotated).sum() / rotated.sum())
        y = float((yy * rotated).sum() / rotated.sum())
        self.assertAlmostEqual(x, 45.82, delta=0.6)
        self.assertAlmostEqual(y, 129.1, delta=0.6)

    def test_color_change_preserves_hue_changes_sv(self):
        color = np.full((10, 10, 3), (100, 50, 150), np.uint8)
        result = change_color(color)
        before = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)[0, 0]
        after = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)[0, 0]
        self.assertLessEqual(abs(int(before[0]) - int(after[0])), 1)
        self.assertGreater(int(after[1]), int(before[1]))
        self.assertEqual(int(after[2]), 165)
        self.assertFalse(np.array_equal(color, result))
        self.assertFalse(np.all(result[:, :, 0] == result[:, :, 1]))

    def test_pipeline_is_deterministic(self):
        repeated = preprocess_image(self.image)
        for name, array in self.stages.items():
            np.testing.assert_array_equal(array, repeated[name])


class OutlierTests(unittest.TestCase):
    def test_known_normal_dark_small(self):
        examples = make_outlier_examples()
        normal = evaluate_outlier(examples["normal"])
        dark = evaluate_outlier(examples["dark"])
        small = evaluate_outlier(examples["small"])
        self.assertFalse(normal["rejected"])
        self.assertEqual(normal["largest_red_ratio"], 0.25)
        self.assertTrue(dark["too_dark"])
        self.assertTrue(small["too_small_red_region"])
        self.assertEqual(small["largest_red_ratio"], 0.01)

    def test_brightness_below_equal_above_threshold(self):
        for value, expected in [(49, True), (50, False), (51, False)]:
            with self.subTest(value=value):
                decision = evaluate_outlier(np.full((10, 10, 3), value, np.uint8))
                self.assertEqual(decision["too_dark"], expected)

    def test_area_below_equal_above_threshold(self):
        for area, expected in [(499, True), (500, False), (501, False)]:
            with self.subTest(area=area):
                image = np.full((100, 100, 3), 180, np.uint8)
                image.reshape(-1, 3)[:area] = (0, 0, 255)
                self.assertEqual(evaluate_outlier(image)["too_small_red_region"], expected)

    def test_largest_component_not_total_or_bounding_box(self):
        mask = np.zeros((100, 100), np.uint8)
        mask[10:20, 10:20] = 255
        mask[70:80, 70:80] = 255
        self.assertEqual(largest_red_ratio(mask), 0.01)

    def test_no_red_region_is_zero(self):
        self.assertEqual(largest_red_ratio(np.zeros((10, 10), np.uint8)), 0)

    def test_invalid_thresholds_are_rejected(self):
        image = make_outlier_examples()["normal"]
        for bright, ratio in [(-1, .05), (256, .05), (50, -0.1), (50, 1.1), (float("nan"), .05)]:
            with self.subTest(bright=bright, ratio=ratio):
                with self.assertRaises(ValueError):
                    evaluate_outlier(image, bright, ratio)

    def test_invalid_mask_is_rejected(self):
        for mask in [None, np.empty((0, 0), np.uint8), np.zeros((2, 2, 3), np.uint8)]:
            with self.assertRaises(ValueError):
                largest_red_ratio(mask)


class ArtifactTests(unittest.TestCase):
    def test_source_hashes_and_five_final_arrays(self):
        manifest = json.loads((ROOT / "data/source_manifest.json").read_text())
        self.assertEqual(len(manifest["samples"]), 5)
        paths = sorted((ROOT / "preprocessed_samples").glob("*.png"))
        self.assertEqual(len(paths), 5)
        for entry, path in zip(manifest["samples"], paths):
            self.assertEqual(hashlib.sha256((ROOT / entry["file"]).read_bytes()).hexdigest(), entry["sha256"])
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            self.assertEqual(image.shape, (224, 224))
            normalized = np.load(ROOT / "results/normalized" / f"{path.stem}.npy", allow_pickle=False)
            self.assertEqual(normalized.dtype, np.float32)
            np.testing.assert_array_equal(image, np.rint(normalized * 255).astype(np.uint8))

    def test_output_directory_has_no_unrelated_images(self):
        with tempfile.TemporaryDirectory() as directory:
            samples = Path(directory) / "preprocessed_samples"
            samples.mkdir()
            (samples / "unrelated.png").write_bytes(b"keep me")
            with self.assertRaisesRegex(ValueError, "unrelated"):
                run(ROOT / "data/originals", Path(directory), ROOT / "data/source_manifest.json")
            self.assertEqual((samples / "unrelated.png").read_bytes(), b"keep me")

    def test_admission_files_match_filter_decisions(self):
        decisions = json.loads((ROOT / "results/outlier_decisions.json").read_text())["photographs"]
        for decision in decisions:
            exists = (ROOT / "results/accepted" / f"{decision['sample']}.npy").exists()
            self.assertEqual(exists, not decision["rejected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
