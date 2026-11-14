import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
from gate_runner import GateFailure, track_ids, assert_video, smoke_track


class Tensor:
    def __init__(self, values): self.values = values
    def cpu(self): return self
    def int(self): return self
    def tolist(self): return self.values


def pred(ids, coords=None):
    boxes = type('Boxes', (), {
        'id': Tensor(ids) if ids is not None else None,
        'xyxy': Tensor(coords if coords is not None else [[1, 2, 4, 5] for _ in ids or []]),
    })()
    return type('Prediction', (), {'boxes': boxes})()


class Stage03Tracking(unittest.TestCase):
    def test_two_unique_ids(self):
        self.assertEqual(track_ids(pred([5, 9])), [5, 9])

    def test_missing_track_ids_are_not_fabricated(self):
        self.assertEqual(track_ids(pred(None)), [])

    def test_duplicate_track_id_is_rejected(self):
        with self.assertRaisesRegex(GateFailure, '중복'):
            track_ids(pred([1, 1]))

    def test_id_box_count_must_match(self):
        with self.assertRaisesRegex(GateFailure, '일치'):
            track_ids(pred([1, 2], [[1, 1, 5, 5]]))

    def test_negative_id_is_rejected(self):
        with self.assertRaises(GateFailure):
            track_ids(pred([-1]))

    def test_real_frame_window_uses_persist_after_first(self):
        class FakeTracker:
            def __init__(self): self.persist_calls = []
            def track(self, frame, *, persist, **kwargs):
                self.persist_calls.append(persist)
                return [pred([3])]
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'clip.mp4'
            w = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 25, (80, 80))
            self.assertTrue(w.isOpened())
            for _ in range(40):
                w.write(np.zeros((80, 80, 3), dtype=np.uint8))
            w.release()
            model = FakeTracker()
            info = smoke_track(source, assert_video(source), SimpleNamespace(conf=.25, imgsz=640), model)
            self.assertGreater(info['frames_with_ids'], 0)
            self.assertIn(False, model.persist_calls)
            self.assertIn(True, model.persist_calls)
