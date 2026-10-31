"""Comento Week 2: reproducible *illustrative* 2.5D projection, not metric 3D depth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np

from image_preprocessing import validate_image, change_color, preprocess_image


def make_depth(image: np.ndarray) -> np.ndarray:
    """Normalized grayscale intensity proxy in [0,1], NOT measured physical depth."""
    validate_image(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32) / np.float32(255.)


def _check_depth(depth: np.ndarray) -> None:
    if (not isinstance(depth, np.ndarray) or depth.ndim != 2 or depth.size == 0
            or depth.dtype != np.float32 or not np.isfinite(depth).all()
            or np.any((depth < 0) | (depth > 1))):
        raise ValueError('Depth must be a nonempty finite 2D float32 array in [0, 1].')


def make_points(depth: np.ndarray, *, z_scale: float = 40., max_points: int = 3_000_000) -> np.ndarray:
    """(x, y, z) in image coordinates; z is grayscale intensity times unitless scale."""
    _check_depth(depth)
    if (isinstance(z_scale, bool) or not isinstance(z_scale, (int, float))
            or not np.isfinite(z_scale) or z_scale <= 0
            or z_scale > float(np.finfo(np.float32).max) or np.float32(z_scale) == 0):
        raise ValueError('z_scale must be positive, finite and representable as float32.')
    if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 1 or depth.size > max_points:
        raise ValueError('Depth exceeds configured XYZ point budget.')
    h, w = depth.shape
    x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return np.stack((x, y, depth * np.float32(z_scale)), axis=-1)


def colorize_depth(depth: np.ndarray) -> np.ndarray:
    """Apply JET only to display the proxy; the color map estimates no distance."""
    _check_depth(depth)
    gray = np.rint(depth * 255).astype(np.uint8)
    return cv2.applyColorMap(gray, cv2.COLORMAP_JET)


def rotate_image(image: np.ndarray, *, degrees: float = 15., border: str = 'replicate') -> np.ndarray:
    validate_image(image)
    modes = {'replicate': cv2.BORDER_REPLICATE, 'reflect101': cv2.BORDER_REFLECT_101,
             'constant': cv2.BORDER_CONSTANT}
    if (border not in modes or isinstance(degrees, bool)
            or not isinstance(degrees, (int, float)) or not np.isfinite(degrees)):
        raise ValueError('Unsupported border mode or rotation angle.')
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D(((w-1)/2, (h-1)/2), degrees, 1.0)
    return cv2.warpAffine(image, matrix, (w,h), flags=cv2.INTER_LINEAR,
                          borderMode=modes[border])


def otsu_masks(image: np.ndarray) -> dict[str,np.ndarray]:
    """Both polarities; cannot infer the true foreground from intensity alone."""
    validate_image(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Do not pre-blur by default: it can erode thin/small known object corners.
    _, bright = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    dark = cv2.bitwise_not(bright)
    return {'bright': bright, 'dark': dark}


def foreground_ratio(mask: np.ndarray) -> float:
    """Largest 8-connected mask region area / image area; polarity must be justified."""
    if (not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.size == 0
            or mask.dtype != np.uint8 or not np.isin(mask,[0,255]).all()):
        raise ValueError('Expected nonempty 2D binary uint8 mask (0 or 255).')
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    largest = int(stats[1:,cv2.CC_STAT_AREA].max()) if n > 1 else 0
    return largest / mask.size


def preprocessing_candidate(image: np.ndarray) -> np.ndarray:
    """Compare with Week1 resize→blur→flip→rotate→color; no presumed speedup."""
    validate_image(image)
    resized = cv2.resize(image, (224,224), interpolation=cv2.INTER_AREA)
    color = change_color(resized)
    blurred = cv2.GaussianBlur(color, (5,5), 1.0, borderType=cv2.BORDER_REFLECT_101)
    flipped = cv2.flip(blurred,1)
    rotated = rotate_image(flipped, degrees=15, border='replicate')
    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32) / np.float32(255.)


def _save(path: Path, img: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), img):
        raise OSError(f'Failed to save {path}')
    return str(path)


def _sampling_step(h: int, w: int, max_points: int) -> int:
    """Smallest shared pixel stride guaranteeing <= max_points plotted samples.

    A square-root estimate alone fails for elongated (e.g. 1×100000) images.
    Binary search avoids a potentially huge linear scan for skinny images.
    """
    if h < 1 or w < 1 or isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 1:
        raise ValueError('Invalid image dimensions or positive integer point budget.')

    def count(step: int) -> int:
        return ((h + step - 1) // step) * ((w + step - 1) // step)

    lo, hi = 1, max(h, w)
    while lo < hi:
        mid = (lo + hi) // 2
        if count(mid) <= max_points:
            hi = mid
        else:
            lo = mid + 1
    return lo


def make_visualizations(image: np.ndarray, directory: Path, *, max_points: int = 7000) -> dict[str,str]:
    """Write BGR input, proxy depth colormap, and actual XYZ scatter plot to PNG."""
    validate_image(image)
    if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 1:
        raise ValueError('max_points must be positive integer.')
    directory = Path(directory)
    depth = make_depth(image)
    full_xyz = make_points(depth)  # Materialize all pixel coordinates; scatter is downsampled only for display.
    from matplotlib import pyplot as plt
    paths = {
        'original': _save(directory/'original.png', image),
        'depth_map': _save(directory/'depth_map.png', colorize_depth(depth)),
    }
    h,w = depth.shape
    step = _sampling_step(h, w, max_points)
    sample_xyz = full_xyz[::step,::step].reshape(-1,3)
    sample_colors = cv2.cvtColor(image[::step,::step], cv2.COLOR_BGR2RGB).reshape(-1,3)/255.
    fig = plt.figure(figsize=(8.0,5.2),dpi=135)
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(sample_xyz[:,0], sample_xyz[:,1], sample_xyz[:,2],
               c=sample_colors, s=3.5, alpha=.86, linewidths=0)
    ax.set_xlabel('X / pixel');ax.set_ylabel('Y / pixel');ax.set_zlabel('Z / intensity proxy')
    ax.set_title('Illustrative 2.5D point cloud (not measured depth)',pad=12,fontsize=11)
    ax.set_zlim(0,40)
    ax.view_init(elev=30, azim=-58)
    fig.tight_layout()
    out=directory/'point_cloud.png'
    fig.savefig(out,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    paths['point_cloud'] = str(out)
    return paths


def compare_mentor_feedback(image: np.ndarray, directory: Path) -> dict:
    """Controlled visual comparisons, simple timings; no unsupported quality claims."""
    validate_image(image)
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    reflection = rotate_image(image, border='reflect101')
    replication = rotate_image(image, border='replicate')
    constant = rotate_image(image, border='constant')
    for name, img in [('reflect101',reflection),('replicate',replication),('constant',constant)]:
        _save(directory/f'rotation_{name}.png',img)
    otsu=otsu_masks(image)
    for name, mask in otsu.items():
        _save(directory/f'otsu_{name}.png',mask)
    old=preprocess_image(image)['normalized']
    new=preprocessing_candidate(image)
    _save(directory/'preprocess_week1.png',np.rint(old*255).astype(np.uint8))
    _save(directory/'preprocess_candidate.png',np.rint(new*255).astype(np.uint8))
    # Warm up both paths and then alternate paired trials to reduce ordering bias.
    for _ in range(3):
        preprocess_image(image);preprocessing_candidate(image)
    old_times=[];new_times=[]
    for idx in range(15):
        if idx%2 == 0: jobs=[('old',lambda:preprocess_image(image)),('new',lambda:preprocessing_candidate(image))]
        else: jobs=[('new',lambda:preprocessing_candidate(image)),('old',lambda:preprocess_image(image))]
        for name, fn in jobs:
            t0=time.perf_counter();fn();dt=(time.perf_counter()-t0)*1000
            (old_times if name=='old' else new_times).append(dt)
    return {
        'rotation': {'baseline_border':'BORDER_REFLECT_101','candidate_border':'BORDER_REPLICATE',
                     'mean_absolute_pixel_delta':float(np.mean(np.abs(reflection.astype(np.int16)-replication.astype(np.int16)))),
                     'constant_zero_corner_count':int(np.count_nonzero(np.all(constant==0,axis=2)))},
        'otsu': {'bright_largest_region_ratio':foreground_ratio(otsu['bright']),
                 'dark_largest_region_ratio':foreground_ratio(otsu['dark']),
                 'selected_foreground_polarity':'UNDETERMINED (no ground truth)'},
        'preprocess_order': {'old_median_ms':float(np.median(old_times)),
                             'candidate_median_ms':float(np.median(new_times)),
                             'mean_absolute_normalized_delta':float(np.mean(np.abs(old-new))),
                             'candidate_adopted':False,
                             'reason':'Keep Week1 pipeline unchanged; timing and output both differ; pilot only'},
    }


def main() -> None:
    parser=argparse.ArgumentParser(description='Illustrative 2D→2.5D intensity projection')
    parser.add_argument('--input',default='data/originals/sample_02.jpg')
    parser.add_argument('--output-dir',default='week2/results')
    args=parser.parse_args()
    image=cv2.imread(args.input,cv2.IMREAD_COLOR)
    if image is None:
        parser.error(f'Cannot read {args.input}')
    output=Path(args.output_dir)
    paths=make_visualizations(image,output)
    feedback=compare_mentor_feedback(image,output)
    metrics={'input':args.input,'image_shape':list(image.shape),'depth_type':'normalized grayscale intensity; not physical depth',
             'point_count':int(image.shape[0]*image.shape[1]),'visualizations':{k:Path(p).name for k,p in paths.items()},
             'mentor_comparisons':feedback}
    (output/'run_summary.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(metrics,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
