# Git 기반 픽셀 이미지 처리 실습 | 코멘토 1주차

OpenCV로 음식 이미지의 픽셀을 분석하고 빨간색 영역을 검출했다. Hugging Face Food101 사진 5장에 전처리와 간단한 이상치 판정을 적용했다.

## 구성

| 파일 | 설명 |
|---|---|
| `image_preprocessing.py` | 픽셀 분석, 빨간색 검출, 전처리, 이상치 판정 |
| `data/originals/` | 원본 JPEG 5장 |
| `data/source_manifest.json` | 원본 출처·해시값(SHA256); 실행 시 이미지 검증에 사용 |
| `preprocessed_samples/` | 224×224 흑백 결과 PNG 5장 (공식 제출 항목) |
| `test_image_preprocessing.py` | 핵심 함수와 실행 결과를 검증하는 자동 테스트 29개 |
| `week1_report.pptx` | 구현 과정과 실행 결과 요약 (3장) |
| `requirements.txt` | 의존 라이브러리 |

`results/`는 실행 시 자동 생성되며 Git에 포함하지 않는다. 마스크·필터 이미지, 정규화 배열(NPY), 이상치 판정(JSON)을 확인할 수 있다. `preprocessed_samples/`는 공식 제출물로 저장소에 포함한다.

## 실행

Python 3.12 이상을 권장한다. 이미 입력 사진 5장이 포함되어 있으므로 실행 중 인터넷 연결은 필요 없다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python image_preprocessing.py
python -m unittest discover -v
```

원본을 보존하며 별도 출력 폴더에서 시험하려면 `python image_preprocessing.py --output-dir artifacts/reproduced`를 실행한다.

## 구현 판단 및 결과

- **색상 검출:** OpenCV BGR→HSV 변환. 빨강의 Hue가 색상환의 시작과 끝에 걸쳐 있어 0~10과 170~179 범위를 합쳐 마스크 생성. `cv2.threshold()`로 별도의 밝기 이진화도 수행.
- **전처리:** Resize(224×224) → Gaussian Blur → 좌우 반전 → 15° 회전 → 채도·밝기 변화 → Grayscale → `float32 / 255`. PNG는 확인용이고 실제 정규화 값은 실행 시 생성되는 NPY에 저장.
- **이상치 판정:** 원본 이미지 기준 평균 밝기 50 미만 또는 가장 큰 **빨간 연결 영역** 비율 5% 미만이면 제외. 실제 결과는 5장 중 2장 통과, 3장 제외.
- **한계:** 빨간색 영역 크기는 일반적인 음식 객체 크기가 아니다. 모든 입력은 Food101의 같은 음식 종류(`beignets`)다. AI 모델 학습이나 음식 인식 정확도 평가는 수행하지 않았다.

데이터셋: [Food101](https://huggingface.co/datasets/ethz/food101). 원본 데이터 버전과 파일별 SHA256은 `data/source_manifest.json`에 기록했다.

## Git 제출

`feature/image-processing` 브랜치의 커밋을 GitHub에 Push하고 `main` 대상으로 Pull Request를 생성하여 멘토에게 리뷰 요청한다. **로컬 Git 이력은 준비되었지만 Push·PR·리뷰·Merge 성공 여부는 별도 확인이 필요하다.**
