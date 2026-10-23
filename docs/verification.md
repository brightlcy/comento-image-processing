# 실제 실행·검증 기록

기준일 2026-10-23. Linux x86_64, Python 3.12.14, OpenCV 4.11.0, NumPy 2.2.6에서 수행했다. macOS·Windows나 멘토 컴퓨터에서 실행했다고 주장하지 않는다.

## 성공한 명령

프로젝트 루트에서 새 가상환경을 구성하고 requirements.txt의 버전으로 설치했다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python image_preprocessing.py
python image_preprocessing.py --output-dir artifacts/reproduced
python -m unittest discover -s tests -v
python scripts/verify_results.py
```

Hugging Face 원본 다운로드도 실제 수행했다. 마지막 명령은 테스트를 실행하고, 별도 임시 디렉터리에 결과를 다시 생성한 뒤 제출 출력과 비교한다.

```bash
python scripts/download_samples.py
```

## 확인된 결과

| 확인 | 실제 결과 | 증거 |
|---|---|---|
| 패키지 의존성 | pip check 정상 | requirements.txt |
| 소스 확보 | Food101 train 0–4, SHA256 기록 | data/source_manifest.json |
| 전체 실행 | 종료 코드 0, 원본 5장 처리 | results/run_summary.json |
| 자동검증 | **29 tests, OK**, 종료 코드 0 | evidence/unittest.log |
| 재현 | 별도 경로 생성 44개 / 44개 SHA256 일치 | evidence/verification.json, evidence/reproduction.log |
| 결과 5장 | 각 224×224, 단일 채널 uint8 PNG | preprocessed_samples/ |
| 정규화 | float32, 유한한 [0,1], 5개 NPY | results/normalized/ |
| 필터 결과 | 실사진 통과 2 / 제외 3 | results/outlier_decisions.json, results/accepted/ |
| 정답 합성 입력 | normal 통과 / dark·small 제외 | results/outlier_examples/ |

`verification.json`에는 검증 당시 핵심 소스·설치 버전 파일의 SHA256과 44개 출력의 양쪽 해시가 기록된다. 이후 코드가 바뀌었다면 그 검증을 최종 소스의 성공 기록으로 재사용하지 말고 다시 실행한다.

## 최소 자동검증 범위

| 분류 | 확인 내용 |
|---|---|
| 입력 | 정상 BGR 로드, 누락·빈·손상 파일, 빈 배열·잘못된 채널·dtype, CLI 오류 종료 |
| 색상 | H=0/10/11/169/170/179, S=119/120, V=69/70, 빨강·파랑·초록·흰색 구분 |
| Threshold | 밝기 126/127/128의 strict 비교, HSV 마스크와 다른 결과 |
| 전처리 | 224 크기·채널·dtype, 정규화 범위·수치, impulse Blur, 반전 열 대응, 회전 마커 위치, 채도·명도 변화, 결정성 |
| 이상치 | 평균 49/50/51, 영역 499/500/501 픽셀, 분리된 연결 요소, 빨강 없음, 잘못된 임계값 |
| 산출물 | 원본 해시, 정확히 5장 디코드, PNG↔NPY 대응, 무관한 출력 보존·오류, 통과 파일과 판정의 대응 |

## 발견한 문제와 처리

1. 초기 설치의 OpenCV 4.13.0.92는 이 환경에서 import 중 SIGBUS(종료 135)가 발생했다. 원인을 확정하지 않았고, 정상 import·전체 실행·의존성 점검을 확인한 4.11.0.86과 NumPy 2.2.6으로 버전을 고정했다. 실패한 초기 환경을 검증 완료로 처리하지 않았다.
2. 빨간 최대 영역 비율을 음식 객체 크기라고 설명하면 부정확하다. 실사진에서 3장을 거부한 실제 결과를 남기고, 적용 대상과 오분류 가능성을 명시했다. 전처리 확인용 PNG 5장과 실제 필터 통과 NPY 2장을 구분했다.
3. 정규화 float 배열을 PNG만으로 보존했다고 설명하면 틀리다. NPY 실수 배열과 uint8 PNG 시각화를 함께 저장하고 픽셀 대응을 검증했다.
4. 네이티브 Push는 인증 부재로 실패했고, 연결 도구는 새 비공개 저장소에 404를 반환했다. 코드 성공과 Git 원격 완료를 구별하고 후속 절차를 남겼다. PR·외부 리뷰·Merge의 성공 기록은 없다.

PPT 페이지 수·패키지 검사와 각 슬라이드 시각 검수 결과는 최종 자체 검수에 기록한다. 자동검증 통과가 일반 객체 탐지 성능이나 학습 정확도 검증을 의미하지 않는다.
