## 목적

코멘토 1차 업무(업무요청서 6–12페이지)의 Git 관리·픽셀 처리·AI 학습용 이미지 전처리·심화 필터링을 재현 가능한 코드와 결과로 정리한다.

## 변경 사항

- OpenCV 이미지 로드·픽셀 분석·BGR→HSV 빨간색 검출·cv2.threshold 밝기 이진화.
- Food101 train 행 0–4 원본 5장과 revision·SHA256 기록.
- 224×224 → Blur → 좌우 반전 → +15° 회전 → 색상 변화 → Grayscale → float32 Normalize.
- 평균 밝기와 빨간 연결 영역 비율로 이상치 판정. 통과 배열만 results/accepted/에 저장.
- 5장 PNG 시각화, NPY 정규화 배열, 실행 지표, README, 요구사항 추적표, 4페이지 PPT.

## 실행 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python image_preprocessing.py
python -m unittest discover -s tests -v
python scripts/verify_results.py
```

## 실제 결과

- Linux x86_64 / Python 3.12.14 / OpenCV 4.11.0 / NumPy 2.2.6에서 실행.
- 자동검증 29개 통과. 재실행 출력 44개가 제출 출력과 SHA256 일치.
- 224×224 단일 채널 PNG 5장. 정규화 실수 데이터는 별도 float32 NPY로 보존.
- 빨간 영역 기준으로 원본 5장 중 2장 통과·3장 제외. 일반 음식 객체 크기 판정 정확도를 의미하지 않는다.

## 확인 사항

- [x] 누락·손상·빈 입력 오류 처리와 HSV·밝기·영역 경계 확인.
- [x] 합성 정상·어두움·작은 빨간 영역 사례 확인.
- [x] 코드·원본·최종 이미지·문서 수치 일치 확인.
- [x] 자체 검토 기록 포함. 실제 동료 리뷰로 표시하지 않음.
- [ ] 멘토 또는 동료의 실제 리뷰 요청·리뷰·병합 허가.

이 본문은 업로드 후 사용할 PR 초안이다. 작성 시점에는 Push·PR이 미완료다. PR을 실제 생성한 뒤 해당 Git 상태를 README·추적표·PPT에 갱신해야 한다. 병합 전 멘토 리뷰가 필요하다.
