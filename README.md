# Git을 활용한 픽셀 단위 이미지 처리 실습

코멘토 1차 업무 과제. Python과 OpenCV로 이미지의 픽셀값을 분석하고, 빨간색 영역 검출·전처리·이상치 필터링을 구현했다.

## 1. 작업 내용

| 요구사항 | 구현 내용 |
|---|---|
| 픽셀 분석 | 이미지 크기, BGR 채널 평균, 중심 픽셀값 확인 |
| 색상 검출 | BGR→HSV 변환 후 빨간색 범위(H 0–10, 170–179) 마스크 생성 |
| 이진화 | `cv2.threshold()`로 밝기 127 초과 픽셀 구분 |
| 데이터 확보 | Hugging Face Food101 `train` 데이터의 원본 이미지 5장 |
| 전처리 | 224×224 → Gaussian Blur → 좌우 반전 → 15° 회전 → 채도·명도 조정 → Grayscale → Normalize |
| 이상치 필터 | 평균 밝기 50 미만 또는 최대 빨간 연결 영역 비율 5% 미만인 이미지 제외 |
| 버전 관리 | `main`, `feature/image-processing` 브랜치와 작업별 Git 커밋 |

## 2. 프로젝트 파일

```text
image_preprocessing.py     이미지 분석·검출·전처리·이상치 판정
requirements.txt           Python 의존성
README.md                  실행 및 결과 설명
data/originals/            입력 이미지 5장
data/source_manifest.json  Food101 출처 및 원본 SHA256
preprocessed_samples/      제출용 전처리 PNG 5장
results/                   색상 검출 사례, 수치 배열, 필터링 결과
scripts/                   데이터 다운로드·출력 재현 검사
tests/                     단위 테스트
submission/                결과 요약 PPT 3장
```

`data/originals/`는 입력이며 `preprocessed_samples/`는 전처리 결과다. `results/normalized/`에는 실제 `[0,1]` 범위의 `float32` 배열(`.npy`)이 저장된다. PNG 5장은 사람이 확인할 수 있도록 저장한 8비트 흑백 이미지다.

## 3. 설치 및 실행

Python 3.12 기준, 프로젝트 루트에서 실행한다. 실험에 사용한 원본 사진 5장이 포함되어 있어 인터넷 연결 없이 처리할 수 있다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python image_preprocessing.py
```

결과를 별도 폴더에 생성하려면:

```bash
python image_preprocessing.py --output-dir artifacts/reproduced
```

## 4. 검증

```bash
python -m unittest discover -s tests -v
python scripts/verify_results.py
```

단위 테스트 29개가 통과했다. 테스트 범위는 입력 오류 처리, HSV 범위, 밝기 임계값, 전처리 결과의 크기·값 범위, 원본 해시, 이상치 경계조건 등이다. `verify_results.py`는 새로운 임시 위치에서 다시 실행하여 저장된 대표 결과와 SHA256을 비교한다. 이때 생성되는 로그는 Git에 올리지 않는 `artifacts/verification/`에 보관된다.

## 5. 결과 및 한계

- 원본 5장 각각에 전처리를 적용하여 224×224 흑백 PNG 5장 생성.
- 이상치 판정 결과: `sample_02`, `sample_04` 통과; 나머지 3장 제외. 통과한 실수 배열은 `results/accepted/`에 저장.
- 작은 객체 판정은 **일반적인 음식 객체 검출이 아니라 빨간색 연결 영역 크기에 대한 간이 기준**이다. 빨간색이 적은 큰 음식도 제외될 수 있다.
- 이미지 5장은 모두 Food101의 동일 음식 클래스(`beignets`)에서 가져왔으며, 모델 학습이나 인식 정확도 측정은 수행하지 않았다.

데이터 출처: [Hugging Face Food101](https://huggingface.co/datasets/ethz/food101). 원본 파일 해시와 데이터셋 revision은 `data/source_manifest.json`에 기록했다. 데이터셋 카드의 라이선스 표기가 불명확하므로 이미지의 별도 상업적 이용 권한을 주장하지 않는다.

## 6. 제출 자료와 Git 협업

- 발표 자료: [`submission/week1_report.pptx`](submission/week1_report.pptx) (3장)
- GitHub 저장소: `https://github.com/brightlcy/comento-week1-image-processing` (원격 업로드 및 접근 권한은 제출자가 확인)
- 기능 브랜치: `feature/image-processing` → 대상 브랜치: `main`

**코드 리뷰와 병합은 GitHub에서 실제 PR을 생성한 뒤 진행한다.** 이 저장소의 로컬 커밋만으로 Push·외부 리뷰·Merge를 완료했다고 간주하지 않는다.
