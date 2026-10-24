# 실행 및 검증 방법

## 코드 실행

Python 3 환경에서 프로젝트 루트 기준으로 다음과 같이 실행한다. 이전 검증 환경은 Linux/Python 3.12.14/OpenCV 4.11.0/NumPy 2.2.6이며, 사용자 macOS는 별도 확인해야 한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python image_preprocessing.py
python -m unittest discover -s tests -v
python scripts/verify_results.py
```

- `preprocessed_samples/`는 필수 결과 이미지 5장 (224×224 흑백 시각화)
- `results/normalized/`는 [0,1] float32 배열 5개
- `results/accepted/`에는 이상치 필터 통과 이미지 2개의 배열
- `results/outlier_decisions.json`에 원본 5장과 합성 예시 판정
- `results/color_detection/`에는 대표 원본(sample_02)의 HSV 마스크·검출·Threshold 이미지 4장만 버전 관리. 전체 5장의 중간 결과는 실행 때 재생성
- 실행에 따른 `docs/evidence/` 검증 로그와 `results/run_summary.json`은 환경 및 실행 시점에 따라 생성되는 파일로 Git에 올리지 않음

## 검증 의미

`unittest`는 원본 해시, 색상·임계값 경계, Blur·회전·반전·정규화, 오류 처리, 5장 파일, 필터 판정 등을 검사한다. 기존 과제 작성 환경과 별도 재실행에서 **29개 테스트 통과**가 확인되었으며, 현재 변경은 폴더 정리 및 문서·PPT 교체만 포함한다.

`verify_results.py`는 단위 테스트를 실행하고 임시 디렉터리에 전체 결과를 다시 만든 후 **Git에 보관한 대표 처리 결과물**과 SHA256을 비교한다. 초기 전체 44개 산출물 재현 기록은 원래 ZIP에서 수행된 역사적 검증이며, 정리본의 검증 범위는 선택된 결과물로 축소했다.

이 검증은 OpenCV 처리 규칙이 구현되었음을 보여주지만 Food101 객체 탐지의 정답률·정확도를 측정하지 않는다. '작은 객체' 조건은 실제 음식 크기가 아닌 빨간 연결 영역 크기에 한정된다.

## 원격 Git 상태

로컬 Git 커밋·브랜치는 준비되었지만 `Push`, PR 생성, 멘토 리뷰 및 Merge는 실제 GitHub에서 별도로 수행해야 한다. `docs/git_status.md`를 참고한다.
