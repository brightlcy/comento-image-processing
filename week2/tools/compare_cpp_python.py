"""Compare real C++ outputs with the preserved Python implementation.

This is a separate integration check; its cases are not GoogleTest or unittest
test counts. Fixtures cover axes, ordering, sampling, scale, and lossless loading.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from week2.image_to_3d import make_depth, make_points, _sampling_step


def read_points(command, payload=None):
    run = subprocess.run(command, input=payload, text=True, capture_output=True, check=True)
    header, rows = run.stdout.split('\n', 1)
    out = np.loadtxt(io.StringIO(rows), dtype=np.float32, ndmin=2)
    if out.shape != (int(header), 3):
        raise AssertionError(f'Output count/shape mismatch: {out.shape}, {header}')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default='build/cpp/cpp_xyz_probe')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    binary = str(Path(args.binary).resolve())
    rng = np.random.default_rng(20261031)
    cases = []
    for h, w in [(1, 1), (1, 101), (101, 1), (3, 5), (17, 29), (11, 7), (32, 13)]:
        depth = rng.integers(0, 256, (h, w)).astype(np.float32) / np.float32(255)
        for scale in [1., 10., 40., 1e-30]:
            full = make_points(depth, z_scale=scale)
            for mode, budget in [('project', 0), ('sample', 1), ('sample', 7), ('sample', 100)]:
                payload = f'{w} {h} {scale:.9g} {budget}\n' + ' '.join(format(float(v), '.9g') for v in depth.flat)
                actual = read_points([binary, mode], payload)
                step = _sampling_step(h, w, budget) if mode == 'sample' else 1
                expected = full[::step, ::step].reshape(-1, 3)
                # Exact float32 comparison, including the tiny-scale cases.
                np.testing.assert_array_equal(actual, expected)
                cases.append({'mode': mode, 'shape': [h, w], 'scale': scale,
                              'budget': budget, 'points': len(actual), 'status': 'PASS'})
    with tempfile.TemporaryDirectory(prefix='comento-diff-') as tmp:
        for h, w in [(3, 5), (17, 29), (1, 101), (101, 1)]:
            gray = rng.integers(0, 256, (h, w), dtype=np.uint8)
            palette = np.array([[0, 0, 0], [255, 255, 255], [255, 0, 0],
                                [0, 255, 0], [0, 0, 255], [51, 51, 51]], np.uint8)
            images = [np.repeat(gray[:, :, None], 3, axis=2),
                      palette[np.arange(h*w).reshape(h, w) % len(palette)]]
            for idx, bgr in enumerate(images):
                image_path = Path(tmp) / f'{h}-{w}-{idx}.png'
                if not cv2.imwrite(str(image_path), bgr):
                    raise OSError(f'Cannot save fixture {image_path}')
                actual = read_points([binary, 'image', str(image_path), '40'])
                expected = make_points(make_depth(bgr)).reshape(-1, 3)
                np.testing.assert_array_equal(actual, expected)
                cases.append({'mode': 'png_load', 'shape': [h, w],
                              'points': len(actual), 'status': 'PASS'})
    summary = {'status': 'PASS', 'seed': 20261031, 'comparison': 'exact float32 XYZ',
               'cases': len(cases), 'compared_point_rows': sum(c['points'] for c in cases),
               'google_test_count': 0, 'details': cases}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='details'}, indent=2))


if __name__ == '__main__':
    main()
