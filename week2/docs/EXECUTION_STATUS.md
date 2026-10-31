# 코멘토 2주차 — GoogleTest/gMock 최종 실행 검증

검증일은 2026-10-31(KST)입니다. 폴더 정리 전 판정은 **LOCAL EXECUTION PASS / CI PASS**입니다. 새 구조에서는 로컬 회귀가 통과했으며 CI 재실행을 확인하고 있습니다. 구현과 실행 검증을 완료했으며, 멘토 리뷰·병합·클래스룸 최종 제출은 별도 절차입니다.

## 실제 실행 근거

| 항목 | 발견·실행·결과 | 원문 증거 |
|---|---|---|
| C++ OpenCV | OpenCV 4.6.0 어댑터·GoogleTest·데모 컴파일 및 실행 성공 | `logs/G2_build_baseline.log`, `logs/G2_build_final.log`, `logs/G4_cpp_demo_final.log` |
| GoogleTest | 31개 발견, 31개 실행, PASS 31, FAIL 0, skipped 0, disabled 0 | `logs/G2_gtest_list.log`, `logs/G2_gtest_final.log`, `gtest_final.xml` |
| gMock | 4개 테스트 PASS, 정확한 경로 인자의 `EXPECT_CALL` 일치 4건 | `logs/G2_gmock_final.log` |
| CTest | 32/32 PASS, Exit 0 | `logs/G2_ctest_final.log`, `ctest_final.xml` |
| 독립 smoke | 1개 실행 안의 16조건 PASS; GoogleTest가 아닙니다. | `logs/G2_ctest_baseline.log`, smoke 원본 출력 |
| ASan + UBSan | 별도 Debug 빌드 CTest 32/32 PASS, Exit 0 | `logs/G3_ctest_sanitized.log`, `ctest_sanitized.xml` |
| LeakSanitizer | 로컬 NOT RUN, CI에서는 `detect_leaks=1`로 CTest 32/32 PASS | `ci/run-41206106529/cpp-google-test.log` |
| Python 회귀 | 67/67 PASS, Exit 0 (1주차 29 + 2주차 38) | `logs/G4_unittest_final.log` |
| Python 커버리지 | 38 테스트·39 subtest PASS, 라인 141/142=99.30%, 표시 99% | `logs/G4_coverage.log`, `coverage.json` |
| 언어 간 XYZ 비교 | 120조건·7,660개 점, float32 완전 일치 | `logs/G4_differential.log`, `differential.json` |
| C++ 변이 검증 | 의도적 결함 6/6을 실제 assertion 실패(Exit 1)로 검출 | `mutations-final/*-test.log`, `mutations-final/summary.json` |
| 변이 후 원본 회귀 | CTest 32/32 PASS, Exit 0 | `logs/G3_clean_ctest_after_mutations.log` |
| 기존 산출물 보존 | 정리 전 28개 SHA256 일치; 정리 후 27개 바이트 동일·테스트 1개 경로 수정 | `preserved_before.json`, `preserved_after.json` |
| 이미지 재생성 | 깊이 맵·점 시각화 생성 성공, 원본 결과는 보존 | `logs/G4_python_visualizations.log`, `visual_reproduction.json` |
| C++ 깊이 PNG | Python 깊이 PNG와 크기·픽셀 완전 일치, 512×512×3 | `cpp_python_depth_visualization.json` |
| Git 무결성 | `git fsck --full --no-reflogs --strict`, Exit 0 | `logs/git_fsck.log` |
| PPT | 최종 첨부본 `comento_week2.ppt` 4장, 원본과 제출본 SHA256 일치, 전 페이지 렌더링 검수 | `presentation_qa.json`, `slides/` |
| GitHub Actions | `cpp-google-test`: **PASS**, `python-regression`: **PASS** | [GitHub Actions 실행 결과](https://github.com/brightlcy/comento-image-processing/actions/runs/41206106529), `ci/run-41206106529/` |

gMock 4개는 GoogleTest 31개에 포함됩니다. CTest 32개는 GoogleTest 31개와 독립 smoke 1개입니다. 이 항목들을 합쳐 테스트 수를 부풀리지 않았습니다. 최초 원본 21개 GoogleTest도 실제 실행하여 21/21 PASS를 확인한 뒤 10개를 추가하였습니다(`gtest_baseline.xml`).

## 환경 및 G1 의존성

- Ubuntu 24.04.3 LTS x86_64, GCC 13.3.0, CMake 3.28.3, C++17입니다.
- Ubuntu 패키지의 C++ OpenCV 4.6.0, GoogleTest/gMock 1.14.0을 사용하였습니다.
- Python 3.12.14, OpenCV 4.11.0, NumPy 2.2.6입니다. 전체 Python 버전은 `python_versions.json`에 있습니다.
- `G1_versions.log`에 실제 라이브러리·CMake 설정·패키지 버전·동적 연결 경로를 기록하였습니다.

일반 시스템 설치에서는 UID 전환(`setgroups`, `setegid`, `seteuid`)과 `/var/cache/apt/archives/partial` 쓰기 권한 오류가 발생하였습니다. 이 오류는 코드의 컴파일·테스트 실패로 처리하지 않았습니다. 실패 원문을 남기고 Ubuntu 공식 패키지를 작업 폴더로 다운로드하여 추출하였습니다. 시스템 `dpkg` 설치 성공으로 표시하지 않았습니다.

실제 사용한 의존성 경로는 `/workspace/scratch/e487502bcbea/_deps/usr`입니다. `CMAKE_PREFIX_PATH`, `PATH`, `LD_LIBRARY_PATH`, `PKG_CONFIG_PATH`, `PKG_CONFIG_SYSROOT_DIR`을 이 경로에 맞추었습니다. Ubuntu 패키지 165개를 다운로드·추출하였으며, CMake가 이 경로의 OpenCV/GTest/gMock을 찾아 실제 컴파일·연결·실행하였습니다. 경로가 없는 재실행 환경에서는 이 파일의 절대 경로를 그대로 사용할 수 없습니다. 일반 Ubuntu 또는 CI 설치 명령은 아래와 같습니다.

```bash
sudo apt-get update
sudo apt-get install -y g++ cmake ninja-build libopencv-dev libgtest-dev libgmock-dev
```

위 시스템 설치는 이 Work에서 성공했다고 주장하지 않습니다. 다운로드·추출 대체 경로의 실행 근거는 `logs/G1_download_only.log`, `G1_extracted_packages.json`, `logs/G1_versions.log`에 있습니다. 초기 설치 시도는 중단하였고, 원문 및 중단 상태를 보존하였습니다.

## G2 실제 빌드와 실행

저장소 루트에서 아래 명령을 실행하였습니다. 이번 Work에서는 앞서 설명한 의존성 환경 변수를 설정한 상태입니다.

```bash
cmake -S week2/cpp -B build/cpp \
  -DCOMENTO_ENABLE_GOOGLETEST=ON \
  -DCOMENTO_REQUIRE_OPENCV_FOR_GTEST=ON
cmake --build build/cpp --parallel 2
ctest --test-dir build/cpp --output-on-failure
./build/cpp/cpp_gtests --gtest_list_tests
./build/cpp/cpp_gtests
./build/cpp/cpp_gtests --gmock_verbose=info --gtest_filter='MockSource.*'
```

컴파일 원문을 위해 `--verbose`, 기계 판독 결과를 위해 `--gtest_output=xml:...`와 `--output-junit ...`도 사용하였습니다. 명령과 Exit Code는 각 로그의 첫 줄·마지막 줄 및 `*.meta.json`에서 확인할 수 있습니다.

## G3 오류 원인·최소 조치·재검증

| 관찰 | 분류·원인 | 조치 및 결과 |
|---|---|---|
| 패키지 설치 실패 | 실행 환경의 UID 전환·시스템 캐시 권한 | 작업 폴더 다운로드·추출로 전환하여 실제 빌드·테스트 성공을 확인하였습니다. |
| sanitizer 빌드 후 테스트 발견 단계 실패 | LeakSanitizer가 `/proc/<pid>/task`를 읽지 못하였습니다. | LeakSanitizer만 비활성화하여 ASan/UBSan CTest 32/32를 확인하였습니다. 누수 검사는 NOT RUN입니다. |
| 데모 실행 권한 오류 | 생성 ELF 파일 모드가 0644여서 실행할 수 없었습니다. | 소유자 실행 비트를 복구하여 같은 바이너리로 262,144개 좌표와 깊이 PNG를 생성하였습니다. 코드 알고리즘은 수정하지 않았습니다. |
| 초기 NaN 입력 검사 제거 변이가 통과 | 출력 Z의 독립적인 유한성 검사가 여전히 NaN을 차단하여, 관찰 가능한 결함이 생기지 않았습니다. | 입력·출력의 두 유한성 검사를 제거하는 실제 결함으로 바꾸어 원래 기대값 그대로 assertion 실패를 확인하였습니다. 초기 시도도 보존하였습니다. |
| 샘플 XYZ 테스트가 개수만 검사 | 독립 리뷰에서 검증 범위 부족을 발견하였습니다. | 비대칭 입력의 정확한 좌표·순서·높이 검증을 추가하였습니다. 임시 X/Y 교환 결함을 검출하였습니다. |
| ROI·다차원 입력·실제 파일 성공 검증 부족 | 독립 리뷰에서 OpenCV 경계의 검증 누락을 발견하였습니다. | 비연속 ROI, 3D Mat, 잘못된 채널·자료형, 실제 PNG·빈 파일·손상 파일 검증을 추가하였습니다. |
| 극소 float 검사의 거짓 PASS 가능성 | `EXPECT_FLOAT_EQ`의 ULP 허용으로 0과 `denorm_min()`이 같게 취급될 수 있었습니다. | `EXPECT_EQ`와 `EXPECT_GT(...,0.f)`를 함께 추가하고 실제 GoogleTest·CTest·sanitizer를 재검증하였습니다. |

기존 생산 알고리즘의 치명적 결함은 이번 검토에서 발견하지 못하였습니다. 이는 모든 입력과 환경의 정확성을 보증한다는 뜻이 아닙니다. 기존 기대값을 완화하지 않았고, 실제 오류를 지우거나 건너뛰어 PASS시키지 않았습니다.

의도적 결함 검출은 임시 복사본에서만 수행하였습니다.

| 결함 | 실패를 확인한 테스트 |
|---|---|
| 샘플 X/Y 교환 | `Sampling.ExactSampleCoordinatesAndHeights` |
| BGR/RGB 교환 | `OpenCvAdapter.KnownBlueBgrPixelNotMistakenForRed` |
| Mat 차원 검사 누락 | `OpenCvAdapter.RejectsVolumeAndAdditionalChannelTypes` |
| 로더가 항상 예외 발생 | `OpenCvAdapter.ActualPngLoadPreservesPixelsAndProjectsCoordinates` |
| 로더 중복 호출 | `MockSource.LoadsExactlyOnceAndConverts` |
| NaN 유한성 보호 제거 | `Projection.RejectsMissingAndMalformedDepth` |

## G4 Python·언어 간·이미지 회귀

```bash
python -m pip install -r week2/requirements.txt
python -m unittest discover -s . -p 'test*.py' -v
python -m pytest week2/python/tests/test_image_to_3d.py -q --cov=week2.python.image_to_3d --cov-report=term-missing
python week2/tools/compare_cpp_python.py --binary build/cpp/cpp_xyz_probe
python week2/tools/check_cpp_mutations.py
python -m week2.python.image_to_3d --input data/originals/sample_02.jpg --output-dir artifacts/final-gate/reproduced
```

비교 도구는 고정 시드 20261031, 극단적 가로·세로 비율, 서로 다른 Z 배율(1e-30 포함), 점 예산, 실제 무손실 PNG 입력을 사용하였습니다. 좌표를 출력하는 실제 C++ 실행 파일과 보존한 Python 구현을 비교하였습니다. 임의 허용 오차로 맞춘 결과가 아닌 float32 완전 일치입니다.

기존 결과 PNG 10장 중 9장은 새 실행과 파일 바이트까지 일치하였습니다. 산점도 PNG는 기존 689×672×4에서 현재 682×701×4로 렌더 크기가 달라졌으며, 원본을 덮어쓰지 않았습니다. 이를 수학적 좌표 불일치로 오인하거나 기존 이미지와 완전히 재현되었다고 주장하지 않았습니다. 원본 데이터·생산 코드·기존 결과 파일의 SHA256은 28개 모두 유지되었습니다.

과거 Debian 실행의 150조건 언어 간 비교 및 이전 변이 검증은 `previous_20261031_debian_evidence.zip`에 보존하였습니다. 이번 실행 수치와 합산하지 않았습니다.

## G5 GitHub Actions 및 승인

사용자 승인 후 `feature/week2-final-execution-20261031` 브랜치를 생성하고 검토한 자료를 원격에 반영했습니다. [GitHub Actions 실행 결과](https://github.com/brightlcy/comento-image-processing/actions/runs/41206106529)은 push 이벤트로 실제 실행되었으며 두 Job 모두 success입니다. 검증한 커밋은 `77ea2cf2ed5e312434049be9cd6f8e2fe22d53b5`입니다. 이후 제출 문서·결과 이미지·로그 반영에는 같은 테스트 코드를 사용했습니다. 최종 PR의 Checks에서도 최신 커밋 상태를 확인합니다.

CI 환경은 Ubuntu 24.04.5, GCC 13.3.0, CMake 3.31.6, C++ OpenCV 4.6.0, GoogleTest/gMock 1.14.0입니다. `sudo apt-get` 시스템 설치, 컴파일, GoogleTest 31개, gMock 4개, CTest 32개, Python unittest 67개, pytest 38개·39 subtest, 언어 간 비교 120조건·7,660개 점을 실제 로그로 확인했습니다. CI는 `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`로 별도 CTest 32개도 통과했습니다. 로컬의 LeakSanitizer 제한과 구분했습니다.

원문 Job 로그와 기계 판독 요약은 `ci/run-41206106529/`에 보존했습니다. Actions 아티팩트 `week2-cpp-evidence`와 `week2-python-evidence`에는 XML·JUnit·버전·좌표 비교·이미지가 있습니다. 이전 `remote_snapshot.json`과 로컬 실패 로그는 실행 전의 기록으로 보존했습니다.

터미널 Push는 인증 정보가 없어 Exit 128로 실패했고, GitHub 연결의 쓰기 요청도 403으로 차단됐습니다. 사용자가 승인한 브라우저 경로로 파일을 반영했습니다. 원격의 기존 1주차 이력을 부모로 유지했고, 최초 ZIP의 로컬 커밋 이력도 제출 ZIP에 보존했습니다. 업로드된 코드 13개와 최종 PPT의 해시가 검토본과 일치하는지 확인했습니다. 이번 2주차 작업에서는 main에 직접 Push하거나 PR을 병합하지 않았습니다. 작업 중 1주차 PR #1이 병합된 상태를 확인하여 새 PR의 base는 main으로 정했습니다. 상세한 기록은 [PUSH_PLAN.md](PUSH_PLAN.md)에 있습니다.

GitHub 스킬별 실제 적용은 [SKILL_USAGE.md](SKILL_USAGE.md), 별도 AI 코드 리뷰는 [CODE_REVIEW.md](CODE_REVIEW.md)에 기록하였습니다. 멘토·동료의 외부 리뷰는 아직 수행하지 않았습니다.

## 남은 항목과 과학적 한계

1. 멘토가 PR의 Files changed·Checks·PPT를 검토해야 합니다.
2. 클래스룸에 최종 PR 주소를 제출해야 합니다. PR 병합은 별도 사용자 승인을 받습니다.
3. macOS의 기존 PNG 픽셀 완전 일치 실패는 미해결이며, 이번 Linux PASS는 그 문제 해결의 증거가 아닙니다.
4. 로컬 LeakSanitizer는 NOT RUN이며 CI에서는 통과했습니다. macOS 재실행은 NOT RUN입니다.
5. PPT는 렌더러·구조·레이아웃 검사로 확인하였으며, 네이티브 PowerPoint에서 직접 열어 검증한 것은 아닙니다.
6. 가상 깊이는 `gray/255`를 높이로 표시한 2.5D 시각화입니다. 물리적 거리·실제 3D 복원·모델 인식 정확도는 평가하지 않았습니다.

## 최종 제출본 재확인

사용자가 수정한 `week2/presentation/comento_week2.ppt`를 최종 발표 자료로 교체했습니다. 원본 파일의 내용은 변경하지 않았고, 4쪽을 확인용 PDF·PNG로 렌더링해 모두 검수했습니다. 이전 PPTX의 검사 기록은 `previous_presentation/`에 보존했습니다.

코드 13개 파일의 해시가 검증 당시와 같은지 확인한 뒤 Python 회귀와 CTest를 다시 실행했습니다. 각각 67/67과 32/32가 통과했습니다. 새 로그는 `logs/current_review_python.log`와 `logs/current_review_ctest.log`에 있습니다.

공식 업무요청서 13~16쪽과 대조한 완료 항목은 `REQUIREMENTS_CHECK.md`, PR 설명의 문체 검토는 `WRITING_REVIEW.md`에 있습니다. 기존 PR #1의 리뷰와 댓글은 각각 0건이었으며, 멘토의 열람 여부는 확인할 수 없었습니다. 설명 검토 후 사용자가 원격 반영과 PR 생성을 승인했습니다. 브라우저 인증을 마친 뒤 실제 CI의 성공을 확인했습니다.

## 폴더 정리 후 재검증

사용자 요청에 따라 Python 코드를 `../python/`, 문서를 현재 `docs/`, PPT를 `../presentation/`으로 옮겼습니다. 이 문서의 짧은 로그·XML 경로는 별도 표기가 없으면 `../verification/`을 기준으로 합니다. 기존 CI와 원문 로그는 당시의 디렉터리 구조를 기록한 이력으로 보존했습니다. 새 구조의 검증 결과는 `../verification/layout/`과 최신 PR Checks에서 확인합니다.

파일 이동 직후 기존 import 경로가 남아 테스트 모듈을 불러오지 못하는 오류를 실제로 재현했습니다. `week2.python.image_to_3d`로 import와 mock 경로를 수정했습니다. Python 구현 파일과 PPT는 이동 전후 바이트가 같습니다. 테스트 기대값과 생산 알고리즘은 바꾸지 않았습니다.

폴더 정리 후 로컬 재검증에서 Python unittest 67/67, pytest 38개·39 subtest, CTest 32/32, 언어 간 비교 120조건·7,660개 점이 통과했습니다. 새 모듈 경로로 실제 샘플의 깊이 맵과 점 시각화도 생성했습니다. 차등 비교 도구의 첫 실행에서 잘못 지정한 `--output` 옵션 오류(Exit 2)를 별도 보존하고, 올바른 `--json` 옵션으로 재실행해 Exit 0을 확인했습니다.
