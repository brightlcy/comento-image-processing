# Git 실행 상태와 후속 절차

확인 기준일: 2026-10-23 (한국 시간). 아래 상태를 실제 동료 리뷰나 승인으로 해석하지 않는다.

| 단계 | 실제 결과 | 근거 |
|---|---|---|
| 새 개인 저장소 | 설정 기록 있음, 현재 원격 조회 미확인 | https://github.com/brightlcy/comento-week1-image-processing — 과거 브라우저 생성 기록은 있으나 연결 API 404; 본인 계정 확인 필요 |
| 로컬 저장소 | 완료 | git init -b main, .git 존재, 원격 origin URL 설정 |
| 기능 브랜치 | 로컬 완료 | feature/image-processing, main은 요구사항 정의 커밋 |
| 커밋 | 완료 | 요구사항 정의 → 기능 → 검증·실행 이미지 → 문서·발표 자료 순으로 분리, git log로 확인 |
| 네이티브 Push | **미완료** | 실제 git push -u origin main 실행 실패: could not read Username for 'https://github.com': terminal prompts disabled |
| 연결 도구 업로드 | **미완료** | 새 비공개 저장소 조회가 GitHub API 404 Not Found 반환. 브라우저 업로드 경로도 시간 초과하여 코드 업로드로 판정하지 않음 |
| PR | **미완료** | 원격 브랜치 업로드가 선행되어야 함. docs/pr_description.md에 실제 변경 기준 본문 준비 |
| 외부 리뷰 요청·리뷰 | **미완료** | 멘토·동료 GitHub ID 미제공, 리뷰 요청·승인 없음 |
| 자체 검토 | 완료 | docs/verification.md. 외부 리뷰나 별도 사람의 승인으로 표시하지 않음 |
| Merge | **미완료** | 원문 p10의 리뷰·병합 허가를 아직 받지 않음 |

**원격 저장소는 생성되었지만 제출 코드가 올라간 저장소는 아니다.** 이 구분은 README·PPT·최종 보고에도 유지한다. 기존 receipt2recipe·FTL 저장소에는 접근·변경하지 않았다.

## 사용자 컴퓨터에서 남은 Push·PR 실행

제출 ZIP의 프로젝트 폴더에는 로컬 `.git` 이력을 포함한다. 압축을 해제한 뒤 해당 폴더로 이동한다. 다시 init하거나 clone할 필요가 없다.

```bash
cd comento-week1-image-processing
git status
git branch --show-current
git remote -v
```

macOS에서 gh가 없다면 설치하고, 본인이 GitHub 로그인 절차를 완료한다. 이 로그인 명령은 이번 실행환경에서 수행한 성공 기록이 아닌 **후속 명령**이다.

```bash
brew install gh
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
```

저장소 소유자가 brightlcy인지 확인한 뒤 업로드한다.

```bash
gh auth status
git push -u origin main
git push -u origin feature/image-processing
gh pr create --repo brightlcy/comento-week1-image-processing --base main --head feature/image-processing --title "Complete week 1 image processing and validation" --body-file docs/pr_description.md
```

생성된 실제 PR URL과 원격 HEAD를 기록하고 README·추적표·PPT·이 문서의 **미완료 상태를 갱신**한다. 로컬 실행이 성공했다고 원격 Push 성공으로 자동 바꾸지 않는다.

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/feature/image-processing
gh pr view --repo brightlcy/comento-week1-image-processing --web
```

멘토 GitHub ID를 확인한 뒤 PR 화면에서 리뷰를 요청한다. 비공개 저장소 열람 권한이 없다면 본인이 해당 멘토에게 필요한 권한을 부여한다. 대상 계정을 확인하지 않고 다른 사람을 초대하지 않는다.

외부 리뷰를 반영하고 병합 허가를 받은 후, 실제 PR 번호를 지정해 병합한다. 아직 수행하지 않은 명령이다.

```bash
gh pr merge PR_NUMBER --repo brightlcy/comento-week1-image-processing --merge
git checkout main
git pull --ff-only origin main
```

제출물·PPT에는 외부 단계가 대기 상태로 명시되어 있으므로, 완료 후 제출하려면 이 상태 설명도 일치하도록 갱신해야 한다.
