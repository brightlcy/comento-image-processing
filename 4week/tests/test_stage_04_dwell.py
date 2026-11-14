import unittest
from storeflow_mvp import Person, Zone, default_zones, parse_zone, zone_at
from gate_runner import evaluate_sample_dwell


class Stage04Dwell(unittest.TestCase):
    def test_left_center_right(self):
        zones = default_zones()
        self.assertEqual(zone_at(0, 100, 600, 400, zones), 'LEFT')
        self.assertEqual(zone_at(300, 100, 600, 400, zones), 'CENTER')
        self.assertEqual(zone_at(599, 100, 600, 400, zones), 'RIGHT')

    def test_custom_zone_and_invalid_coordinates(self):
        z = parse_zone('SEATS:0.1,0.2,0.8,0.9')
        self.assertEqual(z.name, 'SEATS')
        self.assertTrue(z.contains(.3, .5))
        with self.assertRaises(Exception):
            parse_zone('BAD:0.9,0.1,0.3,1.0')

    def test_elapsed_and_observed_time_distinct_with_occlusion(self):
        p = Person(4, 0, 0, (50, 50), 'LEFT', 0)
        p.observe(0, (50, 50), 'LEFT', 640, 480)
        p.observe(29, (60, 50), 'LEFT', 640, 480)
        self.assertAlmostEqual(p.elapsed_seconds(30), 1.0)
        self.assertAlmostEqual(p.detected_frames / 30, 2 / 30)

    def test_zone_transition_and_observed_frame_counts(self):
        p = Person(3, 0, 0, (10, 10), 'LEFT', 0)
        p.observe(0, (10, 10), 'LEFT', 600, 400)
        p.observe(1, (300, 10), 'CENTER', 600, 400)
        p.observe(2, (310, 10), 'CENTER', 600, 400)
        self.assertEqual(p.zone_frames['LEFT'], 1)
        self.assertEqual(p.zone_frames['CENTER'], 2)
        self.assertAlmostEqual(p.current_zone_seconds(30), 2/30)

    def test_real_track_trace_roi_accounting(self):
        observations = [
            {'window': 0, 'frame': 1, 'id': 7, 'x': 20, 'y': 100},
            {'window': 0, 'frame': 2, 'id': 7, 'x': 300, 'y': 100},
            {'window': 1, 'frame': 10, 'id': 7, 'x': 590, 'y': 100},
        ]
        evidence, people = evaluate_sample_dwell(observations,
            {'width': 600, 'height': 400, 'fps': 25}, default_zones())
        self.assertEqual(evidence['track_segments'], 2)  # IDs across windows never merged
        self.assertEqual(evidence['observed_track_points'], 3)
        self.assertEqual(evidence['roi_observed_seconds']['LEFT'], .04)
        self.assertEqual(evidence['roi_observed_seconds']['CENTER'], .04)
        self.assertEqual(evidence['roi_observed_seconds']['RIGHT'], .04)

    def test_zone_outside_returns_other(self):
        self.assertEqual(zone_at(300, 200, 600, 400, [Zone('TOP', 0, 0, 1, .1)]), 'OTHER')
