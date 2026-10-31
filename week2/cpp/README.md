# 2주차 C++ GoogleTest/gMock 보완

## 목적과 범위

GoogleTest/gMock 실행 요청에 맞춰 C++ 테스트를 별도로 작성했습니다. 1주차 Python 코드는 유지했습니다.

- `src/depth_projection.cpp`: 행/열 기반 XYZ 좌표, 입력 검증, 그림용 점 샘플링을 구현했습니다. Z는 명암 기반 가상 높이입니다.
- `src/opencv_depth_source.cpp`: C++ OpenCV로 BGR 이미지를 읽고 `COLOR_BGR2GRAY`로 변환해 `float` [0, 1] 깊이 입력을 만들었습니다.
- `tests/test_depth_projection.cpp`: GoogleTest로 좌표·크기·범위·예외·샘플링을 검증했습니다.
- `MockDepthSource` / `tests/test_depth_projection.cpp`: gMock의 `MOCK_METHOD`·`EXPECT_CALL`로 이미지 로드 성공·실패·잘못된 형상을 검증했습니다. 실제 좌표 계산에는 생산 코드를 사용했습니다.
- `tests/test_opencv_adapter.cpp`: C++ OpenCV 채널 순서·그레이스케일·HSV·Otsu 픽셀 동작 검증.
- `tests/core_smoke.cpp`: GoogleTest 의존성 없이 컴파일되는 별도 16조건 검사입니다. GoogleTest 실행으로 집계하지 않았습니다.
- `.github/workflows/comento-week2-cpp.yml`: Push/PR 시 필요한 개발 패키지를 설치해 GoogleTest/gMock과 C++ OpenCV 실제 빌드·테스트를 수행하도록 구성한 워크플로.

## Linux/CI — GoogleTest/gMock 실제 실행

```bash
sudo apt-get update
sudo apt-get install -y g++ cmake libopencv-dev libgtest-dev libgmock-dev
cmake -S week2/cpp -B build/cpp -DCOMENTO_ENABLE_GOOGLETEST=ON
cmake --build build/cpp --parallel 2
ctest --test-dir build/cpp --output-on-failure
./build/cpp/cpp_depth_demo data/originals/sample_02.jpg build/cpp/depth_cpp.png
```

macOS 예시 (Homebrew): `brew install cmake opencv googletest`. CMake에서 패키지를 찾지 못하면 `CMAKE_PREFIX_PATH`에 설치 경로를 지정합니다. `COMENTO_FETCH_GOOGLETEST=ON` 옵션은 패키지가 없을 때 GoogleTest v1.18.0 소스를 다운로드하므로 네트워크가 필요합니다. 이 macOS 명령은 이번 검증에서 실행하지 않았습니다.

GoogleTest가 켜진 상태에서 OpenCV 테스트가 제외되지 않도록 CMake는 기본적으로 OpenCV 개발 패키지를 필수로 확인합니다 (`COMENTO_REQUIRE_OPENCV_FOR_GTEST=ON`).

`COMENTO_ENABLE_GOOGLETEST=OFF`는 오프라인에서 C++ 계산 부분만 빌드·검증하는 옵션입니다. 이 결과는 GoogleTest/gMock 실행 결과와 구분합니다.

## 오프라인 검사 (GoogleTest 미설치 시)

```bash
cmake -S week2/cpp -B build/cpp-offline -DCOMENTO_ENABLE_GOOGLETEST=OFF
cmake --build build/cpp-offline --parallel 2
ctest --test-dir build/cpp-offline --output-on-failure
```

## 이번 검증 결과와 미수행

2026-10-31 Ubuntu 24.04.3에서 실제 C++ OpenCV 4.6.0·GoogleTest/gMock 1.14.0을 연결하여 실행했습니다.

- GoogleTest: **31개 발견·31개 실행·31개 PASS**, 실패·건너뛰기·비활성 0개입니다. 기존 21개와 경계 검증 10개를 포함합니다.
- gMock: **4개 PASS**이며 GoogleTest 31개 안에 포함됩니다. `--gmock_verbose=info`에서 경로 인자와 실제 `EXPECT_CALL` 일치를 확인했습니다. 이를 위해 gMock 플래그를 초기화하는 `GTest::gmock_main`으로 연결했습니다.
- CTest: **32/32 PASS**, Exit 0입니다. GoogleTest 31개와 독립 smoke 1회이며, smoke의 16조건을 GoogleTest로 계산하지 않았습니다.
- C++ OpenCV 어댑터와 실제 512×512 이미지 데모가 빌드·실행되었습니다. 깊이 PNG는 Python 결과와 픽셀이 완전히 일치했습니다.
- ASan/UBSan: 별도 빌드의 CTest **32/32 PASS**입니다. Work의 프로세스 접근 제한 때문에 `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1`을 사용하였고 LeakSanitizer는 **NOT RUN**입니다.
- Python 회귀: **67/67 PASS**입니다. XYZ 비교 도구는 **120조건·7,660개 좌표를 float32 완전 일치**로 확인했습니다. 서로 다른 테스트 종류를 합산하지 않았습니다.
- 임시 복사본에서 C++ 결함 **6/6을 실제 assertion 실패로 검출**하였으며, 원본 CTest를 다시 통과시켰습니다. 생산 코드의 알고리즘은 변경하지 않았습니다.
- GitHub Actions 두 Job은 **NOT RUN**이며 Push 승인 후 실제 결과를 확인해야 합니다.

원문 로그·XML·실패 원인·정확한 실행 조건은 [`../verification/EXECUTION_STATUS.md`](../verification/EXECUTION_STATUS.md)에 있습니다. 전체 완료는 CI의 성공을 확인할 때까지 보류합니다. macOS의 과거 픽셀 일치 실패 역시 미해결 상태입니다.

```bash
./build/cpp/cpp_gtests --gtest_list_tests
./build/cpp/cpp_gtests --gtest_output=xml:build/cpp/gtest.xml
./build/cpp/cpp_gtests --gmock_verbose=info --gtest_filter='MockSource.*'
python week2/tools/compare_cpp_python.py --binary build/cpp/cpp_xyz_probe
python week2/tools/check_cpp_mutations.py
```

`tests/xyz_probe.cpp`는 언어 간 비교를 위한 테스트 보조 실행 파일이며 신규 제품 기능이 아닙니다. `tools/check_cpp_mutations.py`는 임시 복사본만 수정하며 원본 소스를 덮어쓰지 않습니다.

## 관련 GitHub 원문

- [GoogleTest 공식](https://github.com/google/googletest)
- [GoogleMock 공식](https://github.com/google/googletest/tree/main/googlemock)
- [test-driven-development](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md)
- [verification-before-completion](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md)
