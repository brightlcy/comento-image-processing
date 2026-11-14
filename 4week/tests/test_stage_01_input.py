import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from gate_runner import GateFailure, assert_video, sampled_indices


class Stage01VideoInput(unittest.TestCase):
    def test_video_metadata_and_three_decodes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'sample.mp4'
            wr = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*'mp4v'), 25.0, (128, 96))
            self.assertTrue(wr.isOpened(), 'OpenCV MP4 codec is required')
            for i in range(20):
                wr.write(np.full((96, 128, 3), (i * 7) % 255, dtype=np.uint8))
            wr.release()
            data = assert_video(p)
            self.assertEqual(data['width'], 128)
            self.assertEqual(data['height'], 96)
            self.assertAlmostEqual(data['fps'], 25, delta=0.1)
            self.assertEqual(data['frames'], 20)

    def test_missing_file_stops(self):
        with self.assertRaisesRegex(GateFailure, '없습니다'):
            assert_video(Path('/missing-storeflow-video-do-not-create.mp4'))

    def test_empty_file_stops(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'empty.mp4'
            p.touch()
            with self.assertRaises(GateFailure):
                assert_video(p)

    def test_sampling_indices_unique_and_in_bounds(self):
        for frames in [1, 2, 3, 20, 100]:
            ids = sampled_indices(frames)
            self.assertEqual(sorted(set(ids)), ids)
            self.assertEqual(ids[0], 0)
            self.assertEqual(ids[-1], frames - 1)
            self.assertTrue(all(0 <= v < frames for v in ids))
