# PaceGuard Edge | 코멘토 3주차

도로 이미지에서 포트홀을 찾는 YOLO26n 모델을 학습했습니다. 같은 데이터에서 학습 입력 크기 416과 640을 비교하고, OpenCV로 탐지 위치를 시각화했습니다.

**결과:** India 240장 학습 / Czech 90장 검증 / Japan 90장 시험. 최종 Japan 시험에서 포트홀 95개 중 2개를 검출했습니다(TP 2, FP 1, FN 93). 아직 실제 경고 시스템에 적용할 수준은 아닙니다.

## 준비

저장소 **루트 폴더**에서 실행합니다. Python 3.12 기준의 기존 CPU 실험 설정입니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r week3/requirements.txt
mkdir -p week3/weights
curl -fL https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt -o week3/weights/yolo26n.pt
```

## 데이터 준비


```bash
python -m paceguard.data.download --countries India Czech Japan --output week3/datasets/archives
python -m paceguard.data.prepare --archives week3/datasets/archives --output week3/datasets/rdd2022 --split-config week3/configs/dataset_final.yaml
python -m paceguard.data.audit week3/datasets/rdd2022 --output week3/outputs/dataset_audit.json
```

## 학습 · 비교

```bash
# SGD, 416 vs 640 (같은 조건에서 입력 크기만 비교)
python -m paceguard.perception.train --config week3/configs/stage1_baseline.yaml --data week3/datasets/rdd2022/data.yaml --weights week3/weights/yolo26n.pt --project week3/runs/sgd
python -m paceguard.perception.train --config week3/configs/stage1_experiment.yaml --data week3/datasets/rdd2022/data.yaml --weights week3/weights/yolo26n.pt --project week3/runs/sgd

# Czech 검증: 모델 모두 같은 imgsz=640으로 평가
python -m paceguard.perception.evaluate --data week3/datasets/rdd2022/data.yaml --weights week3/runs/sgd/baseline/weights/last.pt --split val --name baseline --output-dir week3/outputs/eval/sgd
python -m paceguard.perception.evaluate --data week3/datasets/rdd2022/data.yaml --weights week3/runs/sgd/resolution640/weights/last.pt --split val --name resolution640 --output-dir week3/outputs/eval/sgd
```

후속 AdamW 실험은 `week3/configs/baseline.yaml`, `week3/configs/experiment.yaml`을 사용해 **별도** `--project week3/runs/adamw`에 실행합니다. 원래 실험에서는 개선되지 않았습니다.

두 SGD 후보만 비교하는 최소 재현 명령은 다음과 같습니다. 원래의 최종 선택은 AdamW 두 후보까지 Czech에서 비교한 결과였으므로, 아래는 **간소화된 실행 예시**입니다.

```bash
python -m paceguard.perception.select --evaluation-dir week3/outputs/eval/sgd --weights-dir week3/runs/sgd --output week3/outputs/eval/sgd/selection.json
python -m paceguard.perception.evaluate --data week3/datasets/rdd2022/data.yaml --weights week3/runs/sgd/resolution640/weights/last.pt --split test --name resolution640 --selection week3/outputs/eval/sgd/selection.json --output-dir week3/outputs/eval/japan
```

시험은 검증 결과로 모델을 미리 고정한 뒤 한 번만 실행합니다. Japan 시험을 보고 조건을 다시 조정하지 않습니다.

## 이미지 예측과 OpenCV 결과

```bash
python -m week3.predict --weights week3/runs/sgd/resolution640/weights/last.pt --image week3/datasets/rdd2022/test/images/EXAMPLE.jpg --output week3/outputs/pothole.jpg
```


