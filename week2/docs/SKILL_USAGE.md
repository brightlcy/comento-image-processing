# GitHub 스킬 원문 및 실제 적용

obra/superpowers 저장소의 아래 SKILL.md 원문을 GitHub 연결로 직접 읽었습니다. 이름만 인용하지 않았으며 실제 코드·로그·검토 결과와 연결하였습니다.

| 스킬 원문 | 읽은 파일 blob SHA | 실제 수행과 증거 |
|---|---|---|
| [test-driven-development](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md) | `46838cc9e893c06259e3bdad0fc2425b36242f15` | 기존 기대값을 유지하고 10개 경계 테스트를 작성하였습니다. 임시 복사본의 실제 결함 6건에서 RED(Exit 1), 원본 31개 GoogleTest·32개 CTest에서 GREEN(Exit 0)을 확인하였습니다. `mutations-final/`, `logs/G3_clean_ctest_after_mutations.log`에 있습니다. |
| [systematic-debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) | `62fc752aaef59a8bbed5d305f4cadc60f8ae07ed` | 설치 권한·누수 검사 환경·실행 비트·동등 변이의 생존을 구별하여 원문 확보→재현→원인 확인→최소 조치→재검증을 수행하였습니다. `EXECUTION_STATUS.md` G3와 각 실패·재실행 로그에 있습니다. |
| [verification-before-completion](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md) | `7d45333cc4a49c57a80df6c1fe2fa777a207afbc` | 컴파일 성공과 테스트 성공을 구분하였습니다. XML·목록·Exit Code·실제 gMock 호출을 확인하고, GoogleTest 31/CTest 32/Python 67을 분리하였습니다. CI·LeakSanitizer·macOS는 미실행으로 유지하였습니다. |
| [requesting-code-review](https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md) | `68d338a58ecdd8b77bfbb519b781ef223dbbb842` | 별도 AI 리뷰어에게 저장소·요구사항·Git 범위를 명시하여 읽기 전용 검토를 요청하였습니다. 검증 누락 2건과 극소 float 검사 1건을 보완하고 후속 확인을 받았습니다. `CODE_REVIEW.md`에 범위와 판정을 기록하였습니다. |

TDD의 `writing-good-tests.md`, 리뷰의 `code-reviewer.md` 원문도 읽고 독립적인 정답값·구체적 반례·읽기 전용 검토 절차를 적용하였습니다. 이미 존재하던 생산 코드를 이번에 처음부터 TDD로 작성했다고 소급하여 주장하지 않습니다. 이번 작업은 기존 구현을 실제 실행하고 테스트의 오류 검출 능력을 보완한 검증 작업입니다. 신규 생산 알고리즘을 추가하거나 기존 코드를 임의로 삭제·재작성하지 않았습니다.

최초 NaN 입력 보호만 제거한 변이는 별도의 출력 보호 때문에 계약 위반을 만들지 못하였습니다. 이를 억지로 검출 성공으로 표시하지 않았습니다. 원인 확인 후 실제 NaN 출력이 가능한 결함으로 수정하여 기대값을 바꾸지 않고 검출하였습니다.

## 공식 문서 확인과 적용

- [GoogleTest CMake 공식 안내](https://google.github.io/googletest/quickstart-cmake.html): 실제 GTest 대상 연결, `gtest_discover_tests`, CTest 실행 및 테스트 목록 확인에 적용하였습니다.
- [gMock 공식 Cookbook](https://google.github.io/googletest/gmock_cook_book.html): 실제 `MOCK_METHOD`·정확한 인자의 `EXPECT_CALL`·호출 횟수·예외 전파를 검증하였습니다. `gmock_main`으로 gMock 플래그를 초기화한 뒤 `--gmock_verbose=info`에서 실제 일치 로그를 확보하였습니다.

스킬 사용과 테스트 실행을 혼동하지 않았습니다. 문서를 읽었다는 사실만으로 GoogleTest, Red Team, CI의 PASS를 부여하지 않았습니다. 원격 멘토·동료에게 리뷰를 요청하거나 메시지를 전송한 것은 아닙니다.

## PR 설명 문체 편집

사용자의 최종 설명 검토 요청에 따라 [blader/humanizer SKILL.md](https://github.com/blader/humanizer/blob/main/SKILL.md) 원문도 읽었습니다. 확인한 blob SHA는 `19fc634208e8cc6ae55d4ff287152583216fd244`입니다. PR 본문과 2주차 README의 문장을 `했습니다` 문체로 정리하고, 추상적인 성과 표현을 실제 구현·실행 수치로 바꿨습니다. 테스트 수와 미완료 상태는 유지했습니다. 적용 내용은 `WRITING_REVIEW.md`에 기록했습니다.
