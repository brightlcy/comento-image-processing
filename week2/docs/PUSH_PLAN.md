# 원격 반영 및 2주차 PR 검토 기록

## 승인 대상

| 항목 | 준비한 값 |
|---|---|
| 저장소 | https://github.com/brightlcy/comento-image-processing |
| 새 원격 브랜치 | `feature/week2-final-execution-20261031` |
| 2주차 PR base | `main` |
| 보존한 원격 1주차 커밋 | `ea19e846bad43211246eb854349bbcbc80292b95` |
| 원격 main | `553f736cf83b94216bcb902bd44287617ef0ab24` — 1주차 PR 병합 후 확인한 기준입니다. |
| 현재 1주차 PR | https://github.com/brightlcy/comento-image-processing/pull/1 — 원격에서 병합 완료를 확인했습니다. 이번 2주차 작업에서는 병합하지 않았습니다. |
| CI | 두 Job PASS, [GitHub Actions 실행 결과](https://github.com/brightlcy/comento-image-processing/actions/runs/41209580635) |

사용자가 PR 설명과 수정 PPT를 검토한 뒤 원격 반영과 새 PR 생성을 승인했습니다. 새 브랜치를 생성하고 두 CI Job의 실제 성공을 확인했습니다. 이번 작업에서는 main에 직접 Push하거나 1주차 브랜치를 덮어쓰지 않았습니다.

## 변경 범위

- 첨부 ZIP에 이미 있던 `week2/`의 Python·C++·결과 PNG·4장 PPT 이력을 보존하였습니다.
- 원격 1주차 브랜치의 추가 커밋 2개를 로컬 병합하였습니다. README 충돌은 최신 1주차 검증 기록과 2주차 안내를 함께 보존하는 방향으로 해결하였습니다.
- `.github/workflows/comento-week2-cpp.yml`: 기존 두 Job을 유지하고 원문 로그·XML·항상 업로드·명시적 Bash pipefail·sanitizer·언어 간 비교를 추가하였습니다.
- `week2/cpp/CMakeLists.txt`: gMock 플래그 초기화와 테스트용 XYZ 비교 실행 파일 연결을 추가하였습니다.
- C++ 테스트 2개 파일: 기존 기대값을 유지하고 경계 검증 10개를 추가하였습니다.
- `week2/cpp/tests/xyz_probe.cpp`, `week2/tools/`: 테스트용 언어 간 비교·임시 변이 검증 도구입니다.
- README·PR 설명·검증 기록·4장 PPT를 실제 실행 결과에 맞추었습니다.
- `.gitignore`에 `build/`를 추가하였습니다. 기존 Python 생산 코드·이미지·멘토 실험 결과는 바이트 단위로 보존하였습니다.
- `week1_report.pptx`는 첨부 ZIP에 있던 이전 파일을 그대로 보존한 것입니다. 원격의 `1week.ppt`도 함께 보존하였습니다. 1주차 발표 자료를 새로 수정하지 않았습니다.

정확한 전체 변경 파일과 최종 커밋 목록은 제출 ZIP의 `HANDOFF/Git_Approval_Plan.md` 및 `HANDOFF/git_handoff.json`에서 확인할 수 있습니다. GitHub에 올리기 전에는 아래 명령으로 원격이 추가 변경되지 않았는지 확인해야 합니다.

```bash
git fetch origin
git status --short --branch
git log --oneline origin/feature/image-processing..HEAD
git diff --stat origin/feature/image-processing...HEAD
git merge-base --is-ancestor origin/feature/image-processing HEAD
```

## 승인 후 순서

1. 사용자가 PR 설명과 최종 PPT를 검토하고 위 브랜치의 원격 반영을 승인합니다.
2. 원격을 다시 조회하고 승인한 커밋만 새 브랜치에 Push합니다.
3. [Actions 화면](https://github.com/brightlcy/comento-image-processing/actions)에서 해당 브랜치·커밋의 `Comento Week 2 C++ GoogleTest and Python` 실행을 엽니다.
4. `cpp-google-test`와 `python-regression`의 실제 상태를 확인합니다. `week2-cpp-evidence`와 `week2-python-evidence` 아티팩트에서 로그·XML·버전을 검토합니다.
5. 실패하면 원문 원인을 분리하여 처리하고 다시 실행합니다. CI 성공 전에는 CI PASS로 보고하지 않습니다.
6. 두 Job이 통과하면 실제 Run URL과 결과를 반영하고 새 2주차 PR을 생성합니다.
7. 사용자가 Files changed·Checks·PPT를 확인하고 멘토 리뷰를 진행합니다. 병합은 별도의 사용자 승인 후 진행합니다.

터미널에서 시도한 명령은 아래와 같습니다. 인증 정보가 없어 Exit 128로 실패했습니다. GitHub 연결의 쓰기도 403으로 차단되어, 승인받은 브라우저 업로드로 전용 브랜치에 반영했습니다. 원격은 1주차 이력을 부모로 하는 새 업로드 커밋을 사용하며, 첨부 ZIP의 원래 로컬 커밋 이력은 코드 ZIP에 함께 보존했습니다.

```bash
git push -u origin HEAD:feature/week2-final-execution-20261031
```

작업 중 1주차 PR #1의 병합을 확인했습니다. 원격 이력을 다시 확인한 뒤 새 2주차 PR의 base를 main으로 정했습니다.

## 이번 최종 수정

사용자가 수정한 `week2/presentation/comento_week2.ppt`로 발표 자료를 교체했습니다. 이전 `week2/week2_report.pptx`는 현재 제출 목록에서 제외하고 Git 이력에 보존했습니다. 검토받은 `week2/docs/PR_DESCRIPTION.md`에 실제 CI 결과와 링크를 추가했습니다. 원격의 코드 13개와 최종 PPT가 로컬 검토본의 해시와 일치하는지 대조했습니다. 기존 PR #1의 리뷰·일반 댓글·코드 리뷰 댓글은 모두 0건으로 확인했습니다.

## 폴더 정리 반영

사용자 요청으로 Python 구현·테스트, 제출 문서, PPT를 각각 `python/`, `docs/`, `presentation/`으로 옮겼습니다. 이전 경로와 새 경로의 대응은 `../verification/layout/moves.json`에 기록했습니다. 원격 반영은 같은 2주차 브랜치에서 진행하며, 폴더 정리 후 CI를 다시 검증합니다.
