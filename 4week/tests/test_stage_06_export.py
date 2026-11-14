import argparse
import csv
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from gate_runner import GateFailure, assert_video, validate_outputs
from storeflow_mvp import run


class Tensor:
    def __init__(self, values): self.values = values
    def int(self): return self
    def cpu(self): return self
    def tolist(self): return self.values


class FakeYOLO:
    def __init__(self, model): self.count = 0
    def track(self, frame, **kwargs):
        self.count += 1
        if self.count <= 24:
            x1 = int(20 + (self.count - 1) * 12)
            ids, boxes = [2], [[x1, 50, x1 + 40, 180]]
        else:
            ids, boxes = [], []
        result = types.SimpleNamespace(boxes=types.SimpleNamespace(
            id=Tensor(ids) if ids else None, xyxy=Tensor(boxes)))
        return [result]


class Stage06Export(unittest.TestCase):
    def test_missing_files_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GateFailure):
                validate_outputs(Path(td), dict(frames=50, fps=25, width=320, height=240), 0)

    def test_full_video_csv_roundtrip_with_fake_tracker(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'synthetic.mp4'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 25, (320, 240))
            self.assertTrue(writer.isOpened())
            for _ in range(70):
                writer.write(np.full((240, 320, 3), 100, dtype=np.uint8))
            writer.release()
            out = Path(td) / 'output'
            args = argparse.Namespace(input=str(source), output_dir=str(out), zone=None,
                                      model='fake', conf=.25, imgsz=640, lost_seconds=.8,
                                      max_frames=0, show=False)
            with patch.dict(sys.modules, {'ultralytics': types.SimpleNamespace(YOLO=FakeYOLO)}):
                run(args)
            info = validate_outputs(out, assert_video(source), 0)
            self.assertEqual(info['unique_ids'], 1)
            self.assertEqual(info['track_log_rows'], 24)
            self.assertEqual(info['output_video_frames'], 70)
            with (out / 'storeflow_person_summary.csv').open(encoding='utf-8-sig', newline='') as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row['status'], 'POSSIBLE_EXIT_RIGHT')
            self.assertAlmostEqual(float(row['detected_s']), 24/25)
