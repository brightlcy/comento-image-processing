"""Contract/edge-case tests; authored before the week 2 implementation (TDD)."""
import tempfile
import unittest
import warnings
from pathlib import Path

import cv2
import numpy as np

from week2.python.image_to_3d import (make_depth, make_points, colorize_depth, rotate_image,
                              otsu_masks, foreground_ratio, preprocessing_candidate,
                              make_visualizations)


class DepthTests(unittest.TestCase):
    def test_black_white_normalized_depth(self):
        image = np.array([[[0, 0, 0], [255, 255, 255]]], dtype=np.uint8)
        z = make_depth(image)
        np.testing.assert_array_equal(z, [[0., 1.]])
        self.assertEqual(z.dtype, np.float32)

    def test_bgr_to_gray_luminance(self):
        image = np.array([[[255, 0, 0], [0, 0, 255]]], np.uint8)
        expected = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)/255
        np.testing.assert_array_equal(make_depth(image), expected)

    def test_none_and_empty_are_rejected(self):
        for x in [None, np.empty((0, 0, 3), np.uint8)]:
            with self.subTest(x=str(x)):
                with self.assertRaises(ValueError): make_depth(x)

    def test_wrong_dtype_dimension_channels_rejected(self):
        invalid = [np.zeros((4,4), np.uint8), np.zeros((4,4,4), np.uint8),
                   np.zeros((4,4,3), np.float32), np.zeros((4,4,3), np.uint16)]
        for image in invalid:
            with self.subTest(shape=image.shape, dtype=str(image.dtype)):
                with self.assertRaises(ValueError): make_depth(image)

    def test_input_immutable(self):
        a = np.arange(36,dtype=np.uint8).reshape(3,4,3)
        original = a.copy()
        make_depth(a)
        np.testing.assert_array_equal(a, original)


class PointTests(unittest.TestCase):
    def test_xy_z_exact_known_coordinates(self):
        depth = np.array([[0., .5, 1.], [.25, .75, 0.]], np.float32)
        pts = make_points(depth, z_scale=10)
        self.assertEqual(pts.shape, (2,3,3))
        self.assertEqual(pts.dtype, np.float32)
        np.testing.assert_array_equal(pts[0,0], [0,0,0])
        np.testing.assert_array_equal(pts[0,2], [2,0,10])
        np.testing.assert_array_equal(pts[1,1], [1,1,7.5])
        np.testing.assert_array_equal(pts[1,0], [0,1,2.5])

    def test_one_pixel(self):
        pts = make_points(np.array([[.4]],np.float32),z_scale=2)
        np.testing.assert_allclose(pts[0,0], [0,0,.8],rtol=0,atol=1e-7)

    def test_depth_invalid_inputs(self):
        bad = [None, np.empty((0,3),np.float32), np.zeros((2,3,1),np.float32),
               np.zeros((2,3),np.uint8), np.array([[np.nan]],np.float32),
               np.array([[np.inf]],np.float32), np.array([[1.1]],np.float32),
               np.array([[-.1]],np.float32)]
        for depth in bad:
            with self.subTest(depth=str(depth)):
                with self.assertRaises(ValueError): make_points(depth)

    def test_scale_invalid(self):
        d = np.zeros((2,2),np.float32)
        for scale in [0,-1,np.nan,np.inf]:
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError): make_points(d, z_scale=scale)

    def test_memory_budget_rejects_excessive_point_count(self):
        depth = np.zeros((3,3), np.float32)
        with self.assertRaises(ValueError): make_points(depth, max_points=8)

    def test_z_scale_float32_overflow_is_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            with self.assertRaises(ValueError):
                make_points(np.array([[1.]],np.float32), z_scale=1e100)

    def test_color_map_shape_and_input_immutable(self):
        z = np.array([[0, .5, 1]],np.float32)
        cp = z.copy()
        cmap = colorize_depth(z)
        self.assertEqual(cmap.shape, (1,3,3))
        self.assertEqual(cmap.dtype,np.uint8)
        np.testing.assert_array_equal(z,cp)


class FeedbackTests(unittest.TestCase):
    def test_rotation_border_and_zero_degrees(self):
        img = np.full((17,17,3), (130,70,30), dtype=np.uint8)
        a = rotate_image(img, degrees=0, border='replicate')
        np.testing.assert_array_equal(a,img)
        r = rotate_image(img, degrees=15, border='replicate')
        self.assertEqual(r.shape,img.shape)
        np.testing.assert_array_equal(r[0,0],img[0,0])

    def test_rotation_modes_distinguishable(self):
        image = np.zeros((17,17,3),np.uint8)
        image[:,0] = (240,40,40)
        self.assertFalse(np.array_equal(
            rotate_image(image, degrees=30, border='constant'),
            rotate_image(image, degrees=30, border='replicate')))

    def test_rotation_invalid_mode(self):
        with self.assertRaises(ValueError): rotate_image(np.zeros((3,3,3),np.uint8), border='fake')

    def test_otsu_bright_no_red_object_exact_area(self):
        img = np.full((40,40,3), 20, np.uint8)
        img[10:30,10:30] = 220
        masks = otsu_masks(img)
        self.assertEqual(set(masks), {'bright','dark'})
        np.testing.assert_array_equal(masks['bright'][10:30,10:30], 255)
        self.assertEqual(foreground_ratio(masks['bright']), .25)

    def test_otsu_dark_object_reverse_polarity(self):
        img = np.full((40,40,3), 230, np.uint8)
        img[10:30,10:30] = 10
        masks = otsu_masks(img)
        self.assertEqual(foreground_ratio(masks['dark']),.25)
        self.assertGreater(foreground_ratio(masks['bright']),.7)

    def test_otsu_uniform_is_ambiguous_not_object_found(self):
        image = np.full((40,40,3),110,np.uint8)
        masks = otsu_masks(image)
        self.assertEqual(int(masks['bright'].sum()),40*40*255)
        self.assertEqual(int(masks['dark'].sum()),0)

    def test_otsu_same_luminance_cannot_separate(self):
        # Adversarial: a chromatically different object with equal grayscale intensity.
        background = np.array([100, 100, 100], dtype=np.uint8)
        object_bgr = np.array([200, 50, 101], dtype=np.uint8)
        while cv2.cvtColor(object_bgr[None,None], cv2.COLOR_BGR2GRAY)[0,0] != 100:
            object_bgr[2] += (-1 if cv2.cvtColor(object_bgr[None,None], cv2.COLOR_BGR2GRAY)[0,0] > 100 else 1)
        img = np.tile(background, (40,40,1))
        img[10:30,10:30] = object_bgr
        self.assertFalse(np.array_equal(img[0,0], img[20,20]))
        self.assertTrue(np.array_equal(otsu_masks(img)['dark'], np.zeros((40,40),np.uint8)))
        # This is a documented method failure, not a passed detection result.

    def test_noisy_otsu_output_binary_and_bounded(self):
        rng = np.random.default_rng(7)
        img = np.clip(rng.normal(35,8,(80,80,3)),0,255).astype(np.uint8)
        img[15:65,15:65] = np.clip(rng.normal(220,8,(50,50,3)),0,255).astype(np.uint8)
        masks = otsu_masks(img)
        for mask in masks.values():
            self.assertEqual(mask.shape,(80,80))
            self.assertTrue(np.isin(mask,[0,255]).all())
        self.assertGreater(foreground_ratio(masks['bright']),0.35)

    def test_otsu_invalid_mask_rejected(self):
        for m in [None,np.zeros((3,3,3),np.uint8),np.ones((3,3),np.uint8),np.zeros((3,3),np.float32)]:
            with self.assertRaises(ValueError): foreground_ratio(m)

    def test_compare_feedback_reports_both_polarities_and_timing(self):
        from week2.python.image_to_3d import compare_mentor_feedback
        img = np.full((24,24,3), 30,np.uint8)
        img[6:18,6:18] = 210
        with tempfile.TemporaryDirectory() as tmp:
            info=compare_mentor_feedback(img, Path(tmp))
            self.assertEqual(info['rotation']['baseline_border'],'BORDER_REFLECT_101')
            self.assertEqual(info['otsu']['selected_foreground_polarity'],'UNDETERMINED (no ground truth)')
            self.assertGreater(info['preprocess_order']['old_median_ms'],0)
            self.assertGreater(info['preprocess_order']['candidate_median_ms'],0)
            self.assertFalse(info['preprocess_order']['candidate_adopted'])

    def test_make_visualization_invalid_sampling_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                make_visualizations(np.ones((2,2,3),np.uint8),Path(tmp), max_points=0)

    def test_candidate_pipeline_output(self):
        a = np.full((40,60,3), (120,90,180),np.uint8)
        before = a.copy()
        b = preprocessing_candidate(a)
        self.assertEqual(b.shape,(224,224))
        self.assertEqual(b.dtype,np.float32)
        self.assertTrue(np.isfinite(b).all())
        self.assertTrue(np.all((0 <= b)&(b <= 1)))
        np.testing.assert_array_equal(a,before)


class VisualTests(unittest.TestCase):
    def test_saved_images_are_readable(self):
        image = np.full((13,17,3), 100,np.uint8)
        image[4:9,5:12] = (20,70,220)
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_visualizations(image, Path(tmp), max_points=100)
            self.assertEqual(set(paths),{'original','depth_map','point_cloud'})
            for p in paths.values():
                self.assertTrue(Path(p).is_file())
                self.assertIsNotNone(cv2.imread(str(p)))



class HardeningTests(unittest.TestCase):
    """Adversarial tests for sampling, numeric edge cases and real CLI artifacts."""

    def test_sampling_budget_across_extreme_aspect_ratios(self):
        from week2.python.image_to_3d import _sampling_step
        for h, w, budget in [(1, 101, 4), (1, 500000, 500),
                             (512, 512, 7000), (8, 75000, 100),
                             (4096, 1, 1), (33, 47, 1549)]:
            with self.subTest(h=h, w=w, budget=budget):
                step = _sampling_step(h, w, budget)
                self.assertGreaterEqual(step, 1)
                actual = ((h+step-1)//step) * ((w+step-1)//step)
                self.assertLessEqual(actual, budget)
                if step > 1:
                    prev = ((h+step-2)//(step-1))*((w+step-2)//(step-1))
                    self.assertGreater(prev, budget, 'Do not discard points unnecessarily')

    def test_plot_point_budget_must_be_strict_integer(self):
        img = np.zeros((2, 2, 3), np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            for val in [True, 0, -1, 1.5, float('inf')]:
                with self.subTest(val=val), self.assertRaises(ValueError):
                    make_visualizations(img, Path(tmp), max_points=val)

    def test_z_scale_cannot_silently_underflow(self):
        from week2.python.image_to_3d import make_points
        depth = np.array([[1]], np.float32)
        for val in [True, 1e-99]:
            with self.subTest(val=val), self.assertRaises(ValueError):
                make_points(depth, z_scale=val)

    def test_rotation_rejects_non_numeric_angle_without_leaking_type_error(self):
        img = np.zeros((2,2,3), np.uint8)
        for degrees in ['fifteen', None, float('nan')]:
            with self.subTest(degrees=degrees), self.assertRaises(ValueError):
                rotate_image(img, degrees=degrees)

    def test_actual_cli_writes_valid_json_and_corresponding_images(self):
        import json
        from unittest.mock import patch
        from week2.python.image_to_3d import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root/'sample.png'
            bgr = np.full((16,24,3), (40,70,140), np.uint8)
            bgr[4:12,6:18] = (190,130,40)
            self.assertTrue(cv2.imwrite(str(src), bgr))
            output = root/'out'
            with patch('sys.argv', ['-m', '--input', str(src), '--output-dir', str(output)]):
                main()
            info = json.loads((output/'run_summary.json').read_text(encoding='utf-8'))
            self.assertEqual(info['point_count'], 16*24)
            self.assertEqual(info['image_shape'], [16,24,3])
            self.assertIn('not physical depth', info['depth_type'])
            for key in ['original','depth_map','point_cloud']:
                self.assertEqual(info['visualizations'][key], f'{key}.png')
                file = output/f'{key}.png'
                self.assertTrue(file.is_file() and file.stat().st_size > 0)
                self.assertIsNotNone(cv2.imread(str(file)))
            self.assertEqual(cv2.imread(str(output/'depth_map.png')).shape, (16,24,3))

    def test_cli_bad_input_uses_diagnostic_error(self):
        from unittest.mock import patch
        from week2.python.image_to_3d import main
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv', ['-m','--input',str(Path(tmp)/'does_not_exist.png')]):
                with self.assertRaises(SystemExit) as ex:
                    main()
                self.assertEqual(ex.exception.code,2)

    def test_otsu_largest_component_not_total_bright_area(self):
        # Two separate 2×2 islands: largest area=4/100, sum=8/100.
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[1:3,1:3] = 255
        mask[7:9,7:9] = 255
        self.assertAlmostEqual(foreground_ratio(mask), .04)

    def test_otsu_diagonal_pixels_use_eight_connectivity(self):
        mask = np.zeros((9, 9), dtype=np.uint8)
        mask[1,1] = mask[2,2] = mask[3,3] = 255
        self.assertAlmostEqual(foreground_ratio(mask), 3 / 81)

    def test_colormap_is_jet_not_three_copies_of_gray(self):
        from week2.python.image_to_3d import colorize_depth
        proxy = np.array([[0., .5, 1.]], np.float32)
        expected = cv2.applyColorMap(np.rint(proxy*255).astype(np.uint8), cv2.COLORMAP_JET)
        np.testing.assert_array_equal(colorize_depth(proxy), expected)

    def test_actual_plot_respects_limit_for_extreme_aspect_ratio(self):
        from unittest.mock import patch
        from mpl_toolkits.mplot3d.axes3d import Axes3D
        real_scatter = Axes3D.scatter
        seen = []
        def spy(axes, xs, ys, zs=0, *args, **kwargs):
            seen.append(len(xs))
            return real_scatter(axes, xs, ys, zs, *args, **kwargs)
        image = np.full((1,101,3),120,np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Axes3D, 'scatter', spy):
                paths = make_visualizations(image, Path(tmp), max_points=4)
        self.assertEqual(len(paths), 3)
        self.assertEqual(len(seen), 1)
        self.assertLessEqual(seen[0], 4)

    def test_points_reject_boolean_budget(self):
        from week2.python.image_to_3d import make_points
        with self.assertRaises(ValueError):
            make_points(np.array([[.5]],np.float32),max_points=True)


    def test_invalid_sampler_dimensions_and_budget(self):
        from week2.python.image_to_3d import _sampling_step
        for h,w,k in [(0,10,4),(-1,10,4),(10,0,4),(2,2,True),(2,2,0)]:
            with self.subTest(h=h,w=w,k=k), self.assertRaises(ValueError):
                _sampling_step(h,w,k)

    def test_image_write_error_is_not_silent(self):
        from unittest.mock import patch
        from week2.python.image_to_3d import _save
        with tempfile.TemporaryDirectory() as tmp:
            with patch('week2.python.image_to_3d.cv2.imwrite', return_value=False):
                with self.assertRaises(OSError):
                    _save(Path(tmp)/'bad.png', np.zeros((2,2,3),np.uint8))


if __name__=='__main__':
    unittest.main()
