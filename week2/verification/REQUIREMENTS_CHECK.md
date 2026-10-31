# 2주차 과제 확인표

업무요청서 「차시별 업무요청서_베어곰_최종.pdf」의 실제 13~16쪽과 제출 파일을 대조했습니다.

구현, 단위 테스트, 결과 이미지, 4장 PPT와 원격 브랜치 반영을 마쳤습니다. GitHub Actions의 두 Job도 실제로 통과했습니다. 멘토 리뷰와 클래스룸에 최종 PR 주소를 등록하는 절차는 별도로 남아 있습니다.

| ID | 공식 요구사항 | 원문 쪽 | 파일 또는 실제 확인 결과 | 상태 |
|---|---|---|---|---|
| W2-01 | Python 단위 테스트 환경 구성 | 13~14 | `week2/requirements.txt`, 의존성 설치 로그 | 완료 |
| W2-02 | 변환 코드의 주요 기능을 테스트 케이스로 검증 | 13~14 | `week2/test_image_to_3d.py` 38개, 입력·좌표·형상·정규화·오류 조건 검사 | 완료 |
| W2-03 | OpenCV와 NumPy로 이미지 변환 구현 | 13, 15 | `week2/image_to_3d.py`의 `make_depth`, `make_points` | 완료 |
| W2-04 | 기본 깊이 맵 생성 | 13, 15 | `make_depth`, `colorize_depth`, `week2/results/depth_map.png` | 완료 |
| W2-05 | 깊이 값을 이용한 포인트 클라우드 생성 | 15 | `make_points`, `make_visualizations`, 512×512 입력의 XYZ 262,144개 | 완료 |
| W2-06 | Unit Test 실제 실행 | 13, 15 | 새 확인에서도 Python 67/67, CTest 32/32 통과 | 완료 |
| W2-07 | 시각적 결과 분석과 개선점 도출 | 13, 15 | 회전 경계·Otsu·전처리 순서 비교, README, 최종 PPT 3쪽 | 완료 |
| W2-08 | 테스트 코드와 실행 결과 문서화 | 16 | README, `verification/EXECUTION_STATUS.md`, 로그·XML | 완료 |
| W2-09 | 변환 결과 이미지 첨부 | 16 | `week2/results/depth_map.png`, `point_cloud.png` | 완료 |
| W2-10 | 과정과 결과를 PPT 4쪽 이내로 요약 | 16 | 최종 수정본 `week2/comento_week2.ppt`, 렌더링한 4쪽 전체 확인 | 완료 |
| W2-11 | Git 저장소 링크 제출 | 16 | 2주차 코드와 수정 PPT를 전용 원격 브랜치에 반영했습니다. | 원격 반영 완료·클래스룸 등록 대기 |

요청서 15쪽의 예제도 Grayscale 밝기를 가상 깊이와 Z 좌표에 사용합니다. 이번 구현은 밝기를 0~1로 정규화하고 Z 배율 40을 적용했습니다. 실제 거리 추정이나 3D 복원 정확도를 평가한 것으로 설명하지 않았습니다.

## 추가로 요청한 검증

| 항목 | 실제 확인 | 상태 |
|---|---|---|
| C++ OpenCV | 어댑터·실제 이미지 로딩·데모 빌드 및 실행 | 통과 |
| GoogleTest | 발견·실행 31개, 31개 통과 | 통과 |
| gMock | 정확한 인자와 호출 횟수 4개, GoogleTest 31개에 포함 | 통과 |
| C++와 Python의 XYZ 비교 | 120조건, 7,660개 점의 float32 완전 일치 | 통과 |
| 변이 검증 | 의도적 결함 6건 검출, 원본 전체 회귀 통과 | 통과 |
| ASan·UBSan | 별도 빌드 CTest 32/32 통과 | 통과 |
| LeakSanitizer | 로컬은 프로세스 접근 제한으로 NOT RUN이며, CI에서는 detect_leaks=1로 32/32 통과했습니다. | CI 통과 |
| GitHub Actions 두 Job | [GitHub Actions 실행 결과](https://github.com/brightlcy/comento-image-processing/actions/runs/41206106529)에서 두 Job success를 확인했습니다. | 통과 |
| 기존 macOS PNG 픽셀 차이 | Linux 통과와 구분해 추적했습니다. | 미해결 |

## 최종 PPT 교체

첨부한 `comento_week2.ppt`를 그대로 복사해 제출 파일로 지정했습니다. 파일 내용은 다시 작성하거나 변환하지 않았습니다. 확인용 PDF와 PNG만 별도로 생성해 검수했습니다.

- 제출 경로는 `week2/comento_week2.ppt`입니다.
- 원본과 제출 파일의 SHA256은 `80a0fbb73475a57e380266b301b8c2db6569d257a1f39ab4aff9ae78975924d5`로 같습니다.
- 4쪽 모두 이미지와 한글이 표시되는 것을 확인했습니다.
- PPT의 GoogleTest 31개, gMock 4개, Python 67개 수치가 실행 기록과 일치했습니다.
- 이전 `week2_report.pptx`는 현재 제출 목록에서 빼고 Git 이력에 보존했습니다.

## 기존 PR 상태와 제출 방법

기존 [PR #1](https://github.com/brightlcy/comento-image-processing/pull/1)은 `feature/image-processing`에서 `main`으로 열려 있습니다. 승인 리뷰, 일반 댓글, 코드 리뷰 댓글은 모두 0건이었습니다. 기록이 없으므로 멘토가 읽었는지는 확인할 수 없습니다.

같은 `feature/image-processing` 브랜치에 2주차 코드를 Push하면 기존 PR에도 추가됩니다. 주차별 변경을 구분해 검토할 수 있도록 새 `feature/week2-final-execution-20261031` 브랜치와 새 2주차 PR을 사용합니다.

1주차 PR이 계속 열려 있으면 2주차 PR의 base는 `feature/image-processing`으로 정합니다. 그 전에 1주차 PR이 병합되면 원격 상태를 다시 확인하고 base를 `main`으로 정합니다.

사용자가 설명과 제출 파일을 검토하고 원격 반영·새 PR 생성을 승인했습니다. 전용 브랜치와 실제 CI 결과를 제출 자료에 반영했습니다. 멘토 리뷰와 PR 병합은 별도 절차입니다.
