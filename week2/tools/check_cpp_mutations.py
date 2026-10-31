"""Inject six known defects only in temporary copies; require real assertion failures."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def logged(command, path):
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    path.write_text('$ ' + ' '.join(command) + '\n' + run.stdout + f'\nEXIT_CODE={run.returncode}\n')
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('artifacts/cpp-mutations'))
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cpp = Path(__file__).resolve().parents[1] / 'cpp'
    mutations = [
        ('sample_xy_swap', 'src/depth_projection.cpp',
         'const float z=d.intensity[y*d.width+x]*z_scale;',
         'const float z=d.intensity[y*d.width+x]*z_scale;',
         'Sampling.ExactSampleCoordinatesAndHeights'),
        ('bgr_rgb_swap', 'src/opencv_depth_source.cpp',
         'cv::COLOR_BGR2GRAY', 'cv::COLOR_RGB2GRAY',
         'OpenCvAdapter.KnownBlueBgrPixelNotMistakenForRed'),
        ('volume_guard_removed', 'src/opencv_depth_source.cpp',
         'image.dims != 2 || ', '',
         'OpenCvAdapter.RejectsVolumeAndAdditionalChannelTypes'),
        ('loader_always_throws', 'src/opencv_depth_source.cpp',
         'return from_bgr(image);', 'throw std::runtime_error("injected loader failure");',
         'OpenCvAdapter.ActualPngLoadPreservesPixelsAndProjectsCoordinates'),
        ('duplicate_mock_load', 'src/depth_projection.cpp',
         'return DepthProjection::project(source_.load(path),z_scale);',
         '(void)source_.load(path);\n    return DepthProjection::project(source_.load(path),z_scale);',
         'MockSource.LoadsExactlyOnceAndConverts'),
        ('nonfinite_guards_removed', 'src/depth_projection.cpp',
         '!std::isfinite(value) || ', '',
         'Projection.RejectsMissingAndMalformedDepth'),
    ]
    details = []
    with tempfile.TemporaryDirectory(prefix='comento-mutants-') as temp:
        for name, filename, old, new, test in mutations:
            source = Path(temp) / name / 'cpp'
            shutil.copytree(cpp, source)
            target = source / filename
            text = target.read_text()
            if name == 'sample_xy_swap':
                # The second occurrence is the sample() path, not project().
                old = 'points.push_back({static_cast<float>(x),static_cast<float>(y),z});'
                assert text.count(old) == 2
                head, sep, tail = text.rpartition(old)
                text = head + 'points.push_back({static_cast<float>(y),static_cast<float>(x),z});' + tail
            else:
                assert text.count(old) == 1, (name, text.count(old))
                text = text.replace(old, new)
                if name == 'nonfinite_guards_removed':
                    # Removing only the input guard is equivalent: project()
                    # still rejects NaN Z. Remove that redundant guard too to
                    # create an observable invalid-output defect.
                    text = text.replace('if (!std::isfinite(z)) throw std::invalid_argument("Projected z overflows float");', '')
            target.write_text(text)
            build = source.parent / 'build'
            configure = logged(['cmake', '-S', str(source), '-B', str(build),
                                '-DCOMENTO_ENABLE_GOOGLETEST=ON', '-DCOMENTO_REQUIRE_OPENCV_FOR_GTEST=ON'],
                               output / f'{name}-configure.log')
            configure.check_returncode()
            compile_run = logged(['cmake', '--build', str(build), '--target', 'cpp_gtests', '--parallel', '2'],
                                 output / f'{name}-build.log')
            compile_run.check_returncode()
            run = logged([str(build/'cpp_gtests'), '--gtest_filter='+test], output/f'{name}-test.log')
            detected = run.returncode == 1 and ('[  FAILED  ] '+test) in run.stdout
            details.append({'mutation': name, 'filter': test, 'test_exit_code': run.returncode,
                            'detected_by_assertion': detected})
            print(f'{name}: '+('DETECTED (expected RED)' if detected else 'NOT DETECTED'), flush=True)
            if not detected:
                raise AssertionError(f'Mutation did not fail the expected assertion: {name}')
    summary = {'status': 'PASS', 'mutants': len(details),
               'detected': sum(d['detected_by_assertion'] for d in details),
               'production_files_modified': False, 'details': details}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
