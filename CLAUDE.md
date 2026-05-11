# Brainrot Patent — Claude 작업 가이드

이 프로젝트는 황당한 아이디어를 특허 명세서로 변환하는 데모. 현재 frontend를 **원클릭 → 대화형 수정 + PDF 다운로드**로 고도화 중.

## 우선 읽을 문서

새 세션 시작 시 다음 순서로 읽어 컨텍스트 확보:
1. `AGENTS.md` — AI 도구 공통 지시문 (역할 분담, 금지 사항)
2. `CONTRIBUTING.md` — 브랜치/커밋/PR 규칙
3. `docs/API_CONTRACT.md` — API 스키마 (절대 직접 수정 금지, diff 문서로 변경 제안)

## 하네스: Frontend Stack PR

**목표:** Frontend 고도화 작업을 Stack PR 방식으로 안전하게 진행. 사용자가 따라칠 수 있게 변경을 작게 쪼개고, 백엔드 영향 변경은 handoff 문서로 백엔드팀에 전달.

**트리거:** Frontend 기능 추가/수정 요청이 오면 `brainrot-orchestrator` 스킬을 사용한다. 예: "세션 ID 기능 추가", "대화 UI 만들고 싶어", "다음 PR", "PDF 다운로드 붙여줘". 단순 질문이나 디버깅은 직접 응답.

**구성:**
- 에이전트: `.claude/agents/pr-planner.md`, `frontend-builder.md`, `git-helper.md`
- 오케스트레이터: `.claude/skills/brainrot-orchestrator/SKILL.md`
- 작업 산출물: `_workspace/` (PR 계획, 빌드 리포트), `docs/handoff/` (백엔드 전달 명세)

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-11 | 초기 구성 (3 agents + 1 skill) | 전체 | Frontend 대화형 + PDF 고도화 시작 |

## 사용자 컨텍스트

- **역할:** Frontend (2번 / 박서연 라인)
- **숙련도:** 개발 입문 단계. 따라치는 학습 방식을 선호 — **단, `frontend/**` 코드만**.
- **편집 권한:** `frontend/**`, `docs/handoff/**`, `_workspace/**`. 그 외는 다른 담당자 영역이므로 직접 수정 금지.

## 따라치기 정책

사용자가 직접 타이핑하고 싶어하는 건 **frontend 코드뿐**이다. 다음은 묻지 말고 자동 처리:

- `.claude/**` 하네스 파일
- `CLAUDE.md`, `.gitignore`, `package.json`, `tsconfig.json` 등 설정 파일
- `docs/handoff/**` 백엔드 전달 문서
- `_workspace/**` 작업 산출물
- git 명령 (브랜치/커밋/PR 생성도 기본 자동, 사용자가 명시적으로 "내가 칠게" 할 때만 안내 모드)

## 절대 하지 않는 것

- `backend/**` 직접 수정 — 변경 필요 시 `docs/handoff/` 문서 작성
- `docs/API_CONTRACT.md` 직접 수정 — 동일하게 handoff 문서로 제안
- `prompts/**`, `examples/**` 수정 — AI/RAG 담당자(4번) 영역
- `tests/**` 직접 수정 — Playwright 담당자(5번) 영역
- main 브랜치에 직접 commit 또는 push
- `git add .` / `git add -A` — 변경 파일 명시
