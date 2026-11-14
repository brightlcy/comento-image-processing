import unittest
from storeflow_mvp_screenfilter import is_display_only_box

class ScreenFilterTests(unittest.TestCase):
    def test_display_image_person_is_suppressed(self):
        self.assertTrue(is_display_only_box((528, 326, 594, 415)))

    def test_actual_kiosk_user_is_retained(self):
        self.assertFalse(is_display_only_box((386, 220, 440, 415)))

    def test_actual_right_walker_is_retained(self):
        self.assertFalse(is_display_only_box((575, 380, 705, 535)))

    def test_partial_screen_overlap_is_retained(self):
        self.assertFalse(is_display_only_box((535, 260, 605, 460)))

    def test_malformed_bbox_is_retained(self):
        self.assertFalse(is_display_only_box((0, 0, 0, 0)))

if __name__ == '__main__':
    unittest.main()
