# Skill Categories

## 카테고리 정의

| ID | 이름 | 아이콘 | 설명 |
|----|------|--------|------|
| git | Git | 📁 | 버전 관리, 커밋, PR |
| code | Code | 💻 | 코드 작성, 리뷰, 리팩토링 |
| test | Test | 🧪 | 테스트 작성, 실행 |
| docs | Docs | 📝 | 문서화, 코드맵 |
| plan | Plan | 📋 | 계획, 이슈 관리 |
| study | Study | 📚 | 학습, 복습 |
| resume | Resume | 📄 | 이력서, 자소서 |
| algo | Algorithm | 🧩 | 알고리즘 학습 |
| pm | PM | 🎯 | 프로젝트/제품 관리 |
| security | Security | 🔒 | 보안 검토 |
| misc | Misc | ✨ | 기타 |

## 스킬별 카테고리 매핑

```json
{
  "git": ["commit", "pr", "branch-cleanup", "worktree"],
  "code": ["code-review", "tdd", "build-fix", "refactor-clean", "restructure"],
  "test": ["test", "e2e", "test-coverage"],
  "docs": ["update-docs", "update-codemaps"],
  "plan": ["plan-quick", "issue"],
  "study": ["study", "study-wrap", "gg", "interview"],
  "resume": ["resume-write", "resume-review", "resume-tailor"],
  "algo": ["algo-start", "algo-review", "algo-save", "algo-learn"],
  "pm": ["agile-pm", "jira-ticket", "jd-update"],
  "security": ["security-review", "tdd-workflow"],
  "misc": ["skillbook", "session-wrap", "daily", "work-log", "sayno", "write"]
}
```

## 카테고리별 통계 표시

```
📊 카테고리별 사용 현황
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Git       ████████████████░░░░ 80% (3/3)
💻 Code      ██████████████░░░░░░ 70% (4/5)
🧪 Test      ████████░░░░░░░░░░░░ 40% (2/3)
📚 Study     ████████████░░░░░░░░ 60% (3/4)
...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 카테고리 정렬 순서

1. 사용 빈도 높은 카테고리 먼저
2. 같으면 발견율 높은 순
3. 같으면 알파벳 순

## 카테고리 뱃지

| 뱃지 | 조건 | 표시 |
|------|------|------|
| 🏆 | 카테고리 내 모든 스킬 발견 | Complete |
| ⭐ | 카테고리 내 Legendary 스킬 보유 | Star |
| 🔥 | 카테고리 내 가장 많이 사용 | Hot |

## 새 스킬 추가 시

1. `~/.claude/skills/` 스캔
2. SKILL.md 파일 파싱
3. 카테고리 자동 추론 (키워드 기반)
4. 매핑 없으면 `misc`로 분류
5. 수동 재분류 가능

### 자동 분류 키워드

| 키워드 | 카테고리 |
|--------|----------|
| git, commit, branch, pr | git |
| code, review, refactor | code |
| test, e2e, coverage | test |
| doc, readme, codemap | docs |
| plan, issue, task | plan |
| study, learn, gg | study |
| resume, cv, 이력서 | resume |
| algo, algorithm, 알고리즘 | algo |
| pm, jira, agile | pm |
| security, 보안 | security |
