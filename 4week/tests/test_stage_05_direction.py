import unittest
from storeflow_mvp import Person, movement_direction, possible_exit
from gate_runner import evaluate_sample_directions


class Stage05Direction(unittest.TestCase):
    def test_four_directions(self):
        samples = [([(100, 50), (220, 50)], 'RIGHT'),
                   ([(220, 50), (100, 50)], 'LEFT'),
                   ([(50, 100), (50, 220)], 'DOWN'),
                   ([(50, 220), (50, 100)], 'UP')]
        for positions, label in samples:
            with self.subTest(label=label):
                self.assertEqual(movement_direction(positions, 640, 480), label)

    def test_small_jitter_is_still(self):
        self.assertEqual(movement_direction([(1, 1), (3, 2)], 640, 480), 'STILL')

    def test_boundary_outward_is_possible_exit(self):
        p = Person(1, 0, 0, (0, 200), 'LEFT', 0)
        p.observe(0, (75, 200), 'LEFT', 640, 480)
        p.observe(1, (8, 200), 'LEFT', 640, 480)
        self.assertEqual(possible_exit(p, 640, 480), 'POSSIBLE_EXIT_LEFT')

    def test_missing_center_is_not_exit(self):
        p = Person(1, 0, 0, (0, 200), 'CENTER', 0)
        p.observe(0, (260, 200), 'CENTER', 640, 480)
        p.observe(1, (330, 200), 'CENTER', 640, 480)
        self.assertEqual(possible_exit(p, 640, 480), 'LOST_INSIDE_OR_OCCLUDED')

    def test_sample_direction_evaluation(self):
        p = Person(4, 0, 0, (10, 10), 'LEFT', 0)
        p.observe(0, (10, 10), 'LEFT', 640, 480)
        p.observe(1, (90, 10), 'LEFT', 640, 480)
        result = evaluate_sample_directions({(0, 4): p})
        self.assertEqual(result['sample_segment_directions']['RIGHT'], 1)

    def test_edge_movement_inward_is_not_exit(self):
        p = Person(1, 0, 0, (0, 200), 'LEFT', 0)
        p.observe(0, (5, 200), 'LEFT', 640, 480)
        p.observe(1, (45, 200), 'LEFT', 640, 480)
        self.assertEqual(possible_exit(p, 640, 480), 'LOST_INSIDE_OR_OCCLUDED')
