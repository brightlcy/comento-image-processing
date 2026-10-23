# 1차 업무 요구사항 추적표

기준: 「차시별 업무요청서_베어곰_최종.pdf」 실제 PDF 페이지 6–12 (총 23페이지).
6페이지는 프로젝트 상황, 7–10페이지는 Git·픽셀 처리, 11페이지는 기본 추가·심화 및 제출 파일, 12페이지는 최종 제출 형식이다.
개발 시작 전에 추출했다. 상태는 실제 증거를 확보한 뒤 갱신한다.

| ID | 구분 / 근거 | 공식 요구 내용 | 구현 파일·함수 | 검증 방법 / 결과 파일 | 상태 |
|---|---|---|---|---|---|
| R01 | 필수 p7–8 | 개인 원격 저장소 생성·로컬 연결 | Git origin | docs/git_status.md | 대기 |
| R02 | 필수 p8 | Git 환경 설정 (init 또는 clone) | 로컬 .git | git rev-parse / docs/git_status.md | 대기 |
| R03 | 필수 p7–8 | feature/image-processing 브랜치 | Git branch | git branch / docs/git_status.md | 대기 |
| R04 | 필수 p7 | 이미지 로드·픽셀값 분석 | image_preprocessing.py:load_image, analyze_pixels | tests / results/metrics.json | 대기 |
| R05 | 필수 p7·9 | 특정 색상 검출·필터링 | detect_red | tests / results/color_detection/ | 대기 |
| R06 | 필수 p7 | imread·cvtColor·threshold 사용 | load_image, detect_red, threshold_brightness | tests / results/color_detection/ | 대기 |
| R07 | 필수 p7·10 | 변경사항 Commit | 논리적 Git 커밋 | git log / docs/git_status.md | 대기 |
| R08 | 필수 p7·10 | 원격 feature 브랜치 업로드·Push | Git 원격 브랜치 | docs/git_status.md | 대기 |
| R09 | 필수 p7·10·12 | PR 생성 | GitHub PR | PR URL / docs/git_status.md | 대기 |
| R10 | 필수 p10 | 멘토 또는 동료 리뷰 요청·리뷰 | GitHub PR | 실제 리뷰 상태 / docs/git_status.md | 대기 |
| R11 | 필수 p10 | 리뷰 후 허가를 받아 Merge | GitHub PR main 병합 | merged 상태 / docs/git_status.md | 대기 |
| R12 | 기본 추가 p11 | Hugging Face 공개 이미지 확보 | scripts/download_samples.py | data/source_manifest.json / 원본 SHA256 | 대기 |
| R13 | 기본 추가 p11 | 224×224 크기 조정 | preprocess_image | tests / results/demo/resized.png | 대기 |
| R14 | 기본 추가 p11 | Grayscale | preprocess_image | shape 검증 / results/demo/grayscale.png | 대기 |
| R15 | 기본 추가 p11 | Normalize | preprocess_image | float32·[0,1] 검증 / results/normalized/ | 대기 |
| R16 | 기본 추가 p11 | Blur로 노이즈 제거 | preprocess_image | 합성 impulse 검증 / results/demo/blurred.png | 대기 |
| R17 | 기본 추가 p11 | 좌우 반전 | preprocess_image | 좌우 배열 대응 / results/demo/flipped.png | 대기 |
| R18 | 기본 추가 p11 | 회전 | preprocess_image | 위치 대응 / results/demo/rotated.png | 대기 |
| R19 | 기본 추가 p11 | 색상 변화 | change_color, preprocess_image | HSV·컬러 배열 변화 / results/demo/color_changed.png | 대기 |
| R20 | 심화 p11 | 평균 밝기 기반 어두운 이미지 제외 | evaluate_outlier, run | 정상·어두움·경계 / results/outlier_decisions.json | 대기 |
| R21 | 심화 p11 | 작은 객체 이미지 제외 | largest_red_ratio, evaluate_outlier, run | 알려진 색상 영역·경계 / results/outlier_decisions.json | 대기 |
| R22 | 제출 p11 | image_preprocessing.py | image_preprocessing.py | CLI 정상 실행 / results/run_summary.json | 대기 |
| R23 | 제출 p11 | preprocessed_samples/ 이미지 5장 | run | 5장 디코드·224 크기 / preprocessed_samples/ | 대기 |
| R24 | 제출 p11 | README 전처리 설명 | README.md | README 명령 재실행 / docs/verification.md | 대기 |
| R25 | 제출 p12 | Git 저장소 링크·PR·4페이지 이하 PPT | README·GitHub·submission/week1_report.pptx | URL·PPTX 구조 검사·렌더 확인 | 대기 |

## 사용자가 추가한 품질 조건 (공식 요구사항과 별도)

| ID | 요청 | 구현·증거 | 상태 |
|---|---|---|---|
| Q01 | 누락·손상·빈 입력 오류 처리 | load_image / tests | 대기 |
| Q02 | 빨강 Hue 양끝·S/V 경계, BGR 구분 | detect_red / tests | 대기 |
| Q03 | 정규화 실수 배열과 PNG 시각화 구분 | results/normalized/*.npy / README | 대기 |
| Q04 | 정상·오류·경계 최소 자동검증 | tests/test_image_preprocessing.py / docs/verification.md | 대기 |
| Q05 | 실행·이미지·문서·Git 상태 일치 | docs/red_team_review.md | 대기 |
| Q06 | 원본·결과 저장 및 5장 무결성 | data/originals/·results/·preprocessed_samples/ | 대기 |
| Q07 | PR 목적·변경·실행·결과·확인사항 | docs/pr_description.md / 실제 PR | 대기 |
| Q08 | 최대 4장 PPT 시각 검수 | submission/week1_report.pptx | 대기 |
