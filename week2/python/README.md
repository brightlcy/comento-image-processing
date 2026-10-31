# Python 이미지 변환과 테스트

`image_to_3d.py`에 이미지 변환 구현을, `tests/`에 단위 테스트를 모았습니다. 저장소 루트에서 다음 명령을 실행합니다.

```bash
python -m pip install -r week2/requirements.txt
python -m week2.python.image_to_3d --input data/originals/sample_02.jpg --output-dir artifacts/week2/reproduced
python -m unittest discover -s . -p 'test*.py' -v
python -m pytest week2/python/tests/test_image_to_3d.py -q --cov=week2.python.image_to_3d --cov-report=term-missing
```

가상 높이는 픽셀 밝기를 표시한 값이며 물리적 거리가 아닙니다. C++ 구현과 좌표를 비교하는 도구는 `../tools/compare_cpp_python.py`에 있습니다.
