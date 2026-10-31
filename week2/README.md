# 코멘토 2주차 | Unit Test와 2D→3D 변환

1주차 이미지 처리 코드는 유지하고, 이미지의 밝기를 가상 높이로 사용하는 2.5D 표현을 추가했습니다. 입력 오류와 좌표 변환은 단위 테스트로 확인했습니다.

## 폴더 구성

| 경로 | 관리하는 내용 |
|---|---|
| `python/image_to_3d.py` | Python 이미지 변환 구현 |
| `python/tests/` | Python 단위 테스트 |
| `cpp/include/`, `cpp/src/`, `cpp/tests/` | C++ 인터페이스·구현·GoogleTest/gMock |
| `tools/` | C++와 Python 비교, 임시 변이 검증 도구 |
| `docs/` | PR 설명, 요구사항 확인표, 실행·리뷰 보고서 |
| `presentation/` | 최종 4장 PPT |
| `results/` | 깊이 맵·포인트 클라우드·멘토 피드백 비교 이미지 |
| `verification/` | 원문 로그·XML·해시·CI·폴더 정리 검증 기록 |
| `requirements.txt` | Python 의존성 설치 목록 |

## 이번 주에 구현한 것

1. `data/originals/sample_02.jpg`를 불러와 Grayscale로 변환하고 0~1로 정규화했습니다.
2. 각 픽셀에 `(x, y, z)` 좌표를 부여했습니다. `z = 40 × gray / 255`이며 실제 거리 단위는 없습니다.
3. `week2/results/depth_map.png`와 `point_cloud.png`를 저장했습니다. 512×512 입력에서 좌표 262,144개를 생성하고, 그림에는 일부 점을 표시했습니다.
4. 1주차 피드백에 따라 회전 경계·Otsu 객체 분리·전처리 순서를 기존 방식과 비교했습니다.

Z는 밝기를 표시한 가상 높이입니다. 단일 RGB 이미지에서 실제 거리를 추정하거나 물리적 깊이를 복원하는 모델은 구현하지 않았습니다.

## 멘토 피드백을 검토한 결과

| 제안 | 확인한 내용 | 결정 |
|---|---|---|
| 회전 경계에 `BORDER_REPLICATE` | 기존 `BORDER_REFLECT_101`과 같은 각도에서 비교했습니다. | 기존 방식을 유지하고 비교 이미지를 저장했습니다. |
| Otsu 자동 이진화 | 빨간색이 없는 합성 객체는 분리했지만, 밝기가 같은 전경·배경은 구분하지 못했습니다. 실제 음식의 정답 마스크는 없습니다. | 보완 실험으로 사용했습니다. 실제 객체 크기 검출의 정확도는 평가하지 않았습니다. |
| 전처리 순서 변경 | 색상 변화·Blur를 앞에 놓은 후보를 비교했습니다. 실행 시간과 출력 픽셀에 차이가 있었습니다. | 기존 순서를 유지했습니다. |

비교 이미지는 `week2/results/rotation_*.png`, `otsu_*.png`, `preprocess_*.png`에서 확인할 수 있습니다. 실행 조건과 수치는 `week2/results/run_summary.json`에 기록했습니다. 시간 측정값은 환경에 따라 달라질 수 있습니다.

## 실행 방법

저장소 최상위 폴더에서 실행합니다. 샘플 이미지는 1주차 `data/`를 그대로 사용합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r week2/requirements.txt
python -m week2.python.image_to_3d --input data/originals/sample_02.jpg --output-dir week2/results
python -m unittest discover -s . -p 'test*.py' -v
python -m pytest week2/python/tests/test_image_to_3d.py -q --cov=week2.python.image_to_3d --cov-report=term-missing
```

| 파일 | 역할 |
|---|---|
| `week2/python/image_to_3d.py` | 가상 깊이, XYZ 좌표, PNG 시각화, 멘토 피드백 비교 |
| `week2/python/tests/test_image_to_3d.py` | 2주차 단위 테스트 |
| `week2/results/` | 원본·깊이 맵·3D 시각화와 비교 결과 |
| `week2/presentation/comento_week2.ppt` | 최종 수정본을 그대로 반영한 멘토 제출용 4장 발표 자료 |
| `week2/cpp/` | C++ XYZ 구현, GoogleTest/gMock 테스트, CMake 및 오프라인 검사 |

## 테스트 결과와 남은 한계

2026-10-31에 Ubuntu 24.04.3 x86_64에서 C++ OpenCV와 실제 GoogleTest/gMock을 빌드하고 실행했습니다. C++은 GCC 13.3.0·CMake 3.28.3·OpenCV 4.6.0·GoogleTest/gMock 1.14.0을 사용했습니다. Python은 3.12.14·OpenCV 4.11.0·NumPy 2.2.6을 사용했습니다.

| 검증 | 실제 결과 | 증거 |
|---|---|---|
| C++ OpenCV | 어댑터·테스트·데모 컴파일 및 실행 PASS | `verification/logs/G2_build_baseline.log`, `G4_cpp_demo_final.log` |
| GoogleTest | 발견 31, 실행 31, PASS 31, FAIL 0, 건너뛰기 0, 비활성 0 | `verification/gtest_final.xml`, `verification/logs/G2_gtest_final.log` |
| gMock | 정상 로딩·로딩 실패·잘못된 형상·NaN 입력 4개 PASS | `verification/logs/G2_gmock_final.log`의 실제 `EXPECT_CALL` 일치 기록 |
| CTest | 32/32 PASS, Exit 0 | `verification/logs/G2_ctest_final.log` |
| ASan + UBSan | 별도 빌드 CTest 32/32 PASS, Exit 0 | `verification/logs/G3_ctest_sanitized.log` |
| Python 회귀 | 1주차 29 + 2주차 38 = 67/67 PASS | `verification/logs/G4_unittest_final.log` |
| 2주차 Python 커버리지 | 38 PASS, 39 subtest PASS, 141/142 문장 = 99.30% (화면 반올림 99%) | `verification/logs/G4_coverage.log`, `verification/coverage.json` |
| C++↔Python XYZ | 합성 및 PNG 120조건, 좌표 7,660개 float32 완전 일치 | `verification/differential.json` |
| C++ 변이 검증 | 임시 복사본의 의도적 결함 6/6 검출, 이후 원본 CTest PASS | `verification/mutations-final/summary.json` |
| 원본 보존 | 폴더 정리 전 28개 SHA256 일치; 정리 후 27개 바이트 동일·Python 테스트 1개는 import 경로만 수정 | `verification/preserved_after.json` |
| GitHub Actions | `cpp-google-test`, `python-regression` 모두 **PASS** | [GitHub Actions 실행 결과](https://github.com/brightlcy/comento-image-processing/actions/runs/41206106529) |

gMock 4개는 GoogleTest 31개에 포함됩니다. CTest 32개는 GoogleTest 31개와 독립 smoke 실행 1개입니다. smoke 내부의 16개 조건은 GoogleTest로 집계하지 않았습니다.

리뷰에서 샘플링 좌표를 개수만으로 검증하던 한계를 확인하여 정확한 XYZ 값, 비연속 ROI, 실제 PNG 로딩, 빈 파일·손상 파일, 채널·차원, 극단적 수치 조건 등 10개 GoogleTest를 추가했습니다. 기존 기대값을 완화하지 않았습니다. 극소 float의 경우 `EXPECT_FLOAT_EQ`가 0을 허용할 수 있어 정확한 동일성과 양수 조건도 함께 검증했습니다.

로컬 ASan/UBSan은 서버의 `/proc` 접근 제한으로 LeakSanitizer를 끈 `detect_leaks=0` 조건에서 통과했습니다. GitHub Actions에서는 누수 검사를 켠 `detect_leaks=1` 조건으로 CTest 32개를 실행해 모두 통과했습니다. 두 실행 환경의 조건을 구분해 기록했습니다.

**환경별 차이:** [1주차 PR #1](https://github.com/brightlcy/comento-image-processing/pull/1)의 macOS PNG 픽셀 일치 실패는 미해결입니다. 이번 Linux PASS를 macOS 문제 해결의 근거로 사용하지 않았습니다. 기존 결과 PNG 10장을 보존하였고 별도 폴더에서 재생성했습니다. 9장은 파일 바이트까지 일치하였으며, 산점도 PNG는 현재 matplotlib 렌더링에서 크기가 달라졌습니다. 이는 XYZ 일치 검증과 구분하여 기록했습니다.

이전 Debian 검증 기록은 `verification/previous_20261031_debian_evidence.zip`에 별도로 보존했습니다. 과거 150조건 교차검증 및 이전 Python 변이 검증 수치를 이번 실행 개수와 합산하지 않았습니다.

## C++ 검증 재실행

일반 Ubuntu 24.04 환경에서는 다음 명령을 사용합니다. 이번 Work에서는 시스템 패키지 경로의 권한 문제를 확인한 뒤, 동일 Ubuntu `.deb`를 작업 폴더로 다운로드·추출하여 실제 빌드에 사용했습니다. 자세한 환경 경로와 오류 원문은 [실행 기록](docs/EXECUTION_STATUS.md)에 있습니다.

```bash
sudo apt-get update
sudo apt-get install -y g++ cmake ninja-build libopencv-dev libgtest-dev libgmock-dev
cmake -S week2/cpp -B build/cpp \
  -DCOMENTO_ENABLE_GOOGLETEST=ON \
  -DCOMENTO_REQUIRE_OPENCV_FOR_GTEST=ON
cmake --build build/cpp --parallel 2
ctest --test-dir build/cpp --output-on-failure
./build/cpp/cpp_gtests --gtest_list_tests
./build/cpp/cpp_gtests
./build/cpp/cpp_gtests --gmock_verbose=info --gtest_filter='MockSource.*'
python week2/tools/compare_cpp_python.py --binary build/cpp/cpp_xyz_probe
python week2/tools/check_cpp_mutations.py
```

## Git 및 제출 상태

로컬 브랜치는 `feature/week2-final-execution-20261031`입니다. 원격의 1주차 커밋 `ea19e846`을 로컬 병합하여 이력을 보존했습니다. 이번 2주차 작업에서는 main에 직접 Push하거나 PR을 병합하지 않았습니다. 사용자가 검토한 코드와 최종 PPT를 새 원격 브랜치에 반영했고, 두 CI Job의 성공을 확인했습니다.

1주차 PR #1의 병합을 확인해 2주차 PR의 base를 `main`으로 정했습니다. 1주차 변경과 구분해 2주차 구현·검증·수정 PPT를 검토할 수 있도록 제출합니다. 1주차 브랜치를 덮어쓰지 않았습니다. [과제 확인표](docs/REQUIREMENTS_CHECK.md)와 [Push 검토 자료](docs/PUSH_PLAN.md)에 완료 항목과 남은 절차를 구분했습니다.

## 폴더 정리 후 검증

Python 구현과 테스트를 `python/`으로, 제출 문서를 `docs/`로, 최종 PPT를 `presentation/`으로 옮겼습니다. C++의 `include/src/tests` 구조와 기존 결과 이미지는 유지했습니다. 구현의 계산 방식과 테스트 기대값은 바꾸지 않았습니다. 경로 변경에 맞춰 import·mock 대상·실행 명령·CI를 수정했으며, 검증 기록은 `verification/layout/`에 있습니다. 정리 전 CI 성공과 정리 후 검증 상태를 구분해 기록합니다.
