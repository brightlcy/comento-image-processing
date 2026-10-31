# 2주차 과제: 단위 테스트와 이미지의 2.5D 변환

이미지의 픽셀 밝기를 가상 높이로 바꾸고, 변환 결과를 단위 테스트로 확인했습니다. 1주차 코드와 결과 이미지는 유지하고 2주차 작업을 `week2/`에 정리했습니다.

## 구현 내용

512×512 BGR 이미지를 그레이스케일로 변환한 뒤 0~1로 정규화했습니다. 각 픽셀에 `(x=열, y=행, z=40×밝기)` 좌표를 부여해 총 262,144개의 점을 만들었습니다. 깊이 맵과 3차원 산점도를 저장했고, 산점도에는 가독성을 위해 일부 점을 표시했습니다. Z는 밝기를 표시한 가상 높이이므로 실제 거리 단위는 없습니다.

1주차 피드백에 따라 회전 경계 처리, Otsu 이진화, 전처리 순서를 비교했습니다. 회전 경계는 기존 `BORDER_REFLECT_101`과 `BORDER_REPLICATE`를 같은 각도에서 확인했습니다. Otsu는 밝은 영역과 어두운 영역을 각각 살펴봤고, 밝기만으로 객체를 구분하기 어려운 경우도 확인했습니다. 전처리 순서를 바꾸면 출력값도 달라져 기존 설정을 유지했습니다.

## 테스트 결과

Ubuntu 24.04에서 C++ OpenCV 4.6.0과 GoogleTest/gMock 1.14.0을 연결해 빌드하고 실행했습니다. Python은 3.12.14, OpenCV 4.11.0, NumPy 2.2.6을 사용했습니다.

| 검증 | 결과 |
|---|---|
| Python 회귀 테스트 | 67개 통과: 1주차 29개, 2주차 38개 |
| 2주차 Python 라인 커버리지 | 141/142개 문장, 약 99% |
| GoogleTest | 발견·실행 31개, 모두 통과, 실패·건너뛰기·비활성 0개 |
| gMock | 파일 경로와 호출 횟수를 확인한 4개 테스트 통과 |
| CTest | 32개 통과 |
| AddressSanitizer·UndefinedBehaviorSanitizer | 별도 빌드의 CTest 32개 통과 |
| C++와 Python 좌표 비교 | 120조건의 XYZ 좌표 7,660개가 float32 값으로 정확히 일치 |
| 의도적 결함 검사 | 임시 복사본에 넣은 결함 6건을 모두 검출 |

gMock 4개는 GoogleTest 31개에 포함됩니다. CTest 32개는 GoogleTest 31개와 독립 smoke 실행 1개를 합친 수입니다.

빈 이미지, 잘못된 채널과 자료형, X/Y 좌표 순서, NaN/Inf, 길쭉한 이미지의 점 개수 제한을 확인했습니다. 샘플링 테스트에는 실제 좌표와 높이를 비교하는 검증을 추가했고, 비연속 ROI와 실제 PNG 파일의 로딩도 확인했습니다. 극소 float 값은 0으로 잘못 통과하지 않도록 정확한 값과 양수 조건을 함께 검사했습니다.

## 제출 자료

- [발표 자료 4장: comento_week2.ppt](https://github.com/brightlcy/comento-image-processing/blob/feature/week2-final-execution-20261031/week2/comento_week2.ppt)
- [가상 깊이 맵](https://github.com/brightlcy/comento-image-processing/blob/feature/week2-final-execution-20261031/week2/results/depth_map.png)
- [3차원 점 시각화](https://github.com/brightlcy/comento-image-processing/blob/feature/week2-final-execution-20261031/week2/results/point_cloud.png)
- [실행 기록과 로그](https://github.com/brightlcy/comento-image-processing/tree/feature/week2-final-execution-20261031/week2/verification)

발표 자료는 최종 수정한 `comento_week2.ppt`를 사용했습니다.

## 실행 방법

저장소 루트에서 실행합니다. C++ 빌드에는 OpenCV와 GoogleTest/gMock 개발 패키지가 필요합니다.

```bash
python -m pip install -r week2/requirements.txt
python -m unittest discover -s . -p 'test*.py' -v
cmake -S week2/cpp -B build/cpp -DCOMENTO_ENABLE_GOOGLETEST=ON -DCOMENTO_REQUIRE_OPENCV_FOR_GTEST=ON
cmake --build build/cpp --parallel 2
ctest --test-dir build/cpp --output-on-failure
./build/cpp/cpp_gtests --gtest_list_tests
./build/cpp/cpp_gtests --gmock_verbose=info --gtest_filter='MockSource.*'
python week2/tools/compare_cpp_python.py --binary build/cpp/cpp_xyz_probe
```

## 남은 확인 사항

GitHub Actions의 `cpp-google-test`와 `python-regression`은 아직 실행하지 않았습니다. 위 테스트 수치는 Ubuntu 작업 환경에서 확인한 결과이며, 원격 실행 후 실제 결과와 실행 링크를 반영할 예정입니다.

sanitizer 실행에서는 서버의 프로세스 접근 제한 때문에 LeakSanitizer를 껐습니다. 따라서 메모리 누수 검사는 미검증입니다. 1주차 PR #1에 기록한 macOS의 PNG 픽셀 일치 실패도 남아 있어, 이번 Linux 결과와 구분했습니다.

가상 깊이와 XYZ 변환 방식, 오류 입력에 대한 테스트 구성을 확인 부탁드립니다.
