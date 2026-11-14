import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
from gate_runner import GateFailure, box_count, assert_video, smoke_detect


class Tensor:
    def __init__(self, values): self.values = values
    def cpu(self): return self
    def tolist(self): return self.values


class Prediction:
    def __init__(self, coords):
        self.boxes = type('Boxes', (), {'xyxy': Tensor(coords)})()


class Stage02Detection(unittest.TestCase):
    def test_two_person_boxes(self):
        result = Prediction([[5, 10, 50, 100], [100, 5, 190, 90]])
        self.assertEqual(box_count(result, 320, 240), 2)

    def test_zero_detections_allowed_in_single_frame(self):
        self.assertEqual(box_count(Prediction([]), 320, 240), 0)

    def test_bad_geometry_must_fail(self):
        for coords in ([[20, 20, 10, 80]], [[0, 0, float('nan'), 20]], [[400, 1, 500, 50]]):
            with self.subTest(coords=coords), self.assertRaises(GateFailure):
                box_count(Prediction(coords), 320, 240)

    def test_missing_boxes_allowed(self):
        self.assertEqual(box_count(type('Prediction', (), {'boxes': None})(), 320, 240), 0)

    def test_zero_people_retry_with_lower_conf(self):
        class ConfAwareModel:
            def predict(self, frame, *, conf, **kwargs):
                return [Prediction([[1, 1, 25, 40]] if conf <= 0.15 else [])]
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'clip.mp4'
            w = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 25, (80, 80))
            self.assertTrue(w.isOpened())
            for _ in range(25):
                w.write(np.zeros((80, 80, 3), dtype=np.uint8))
            w.release()
            args = SimpleNamespace(conf=.25, imgsz=640)
            info = smoke_detect(source, assert_video(source), args, ConfAwareModel())
            self.assertEqual(len(info['attempts']), 2)
            self.assertEqual(args.conf, .15)
            self.assertGreater(info['detections'], 0)

    def test_zero_people_even_after_retry_stops(self):
        class EmptyModel:
            def predict(self, frame, **kwargs): return [Prediction([])]
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'clip.mp4'
            w = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 25, (80, 80))
            self.assertTrue(w.isOpened())
            for _ in range(25):
                w.write(np.zeros((80, 80, 3), dtype=np.uint8))
            w.release()
            args = SimpleNamespace(conf=.25, imgsz=640)
            with self.assertRaisesRegex(GateFailure, '0건'):
                smoke_detect(source, assert_video(source), args, EmptyModel())
