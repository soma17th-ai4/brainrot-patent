# Brainrot Patent

황당한 아이디어를 실제 특허 명세서처럼 보이는 문서로 변환하는 AI 에이전트 데모 프로젝트입니다.

사용자는 "방구로 가는 자동차"처럼 일상어로 아이디어를 입력하고, 서비스는 특허 문서의 어투와 구조를 모사해 7개 섹션의 명세서 초안과 PDF 다운로드 결과물을 제공합니다.

## 2주 MVP 목표

- 한국어 입력 1~3문장을 받는다.
- 검색 또는 샘플 근거를 활용해 배경기술을 만든다.
- 특허 명세서 7개 섹션을 JSON으로 생성한다.
- 프론트엔드에서 결과를 미리보기로 보여준다.
- 최종 데모에서는 PDF 다운로드 또는 PDF 유사 화면까지 시연한다.

## 핵심 문서

- [Project Brief](docs/PROJECT_BRIEF.md)
- [MVP Scope](docs/MVP_SCOPE.md)
- [Role Guide](docs/ROLE_GUIDE.md)
- [API Contract](docs/API_CONTRACT.md)
- [AI Dev Rules](docs/AI_DEV_RULES.md)
- [Prompt Guide](docs/PROMPT_GUIDE.md)
- [Demo Script](docs/DEMO_SCRIPT.md)
- [Two Week Plan](docs/TWO_WEEK_PLAN.md)

## 팀 역할

| 번호 | 역할 | 담당 |
| --- | --- | --- |
| 1 | 발표, 기획 | 임준현 |
| 2 | Frontend | 박서연 |
| 3 | Backend & Agent | 이진중 |
| 4 | AI, RAG | 황현석 |
| 5 | Playwright | 추웅재 |

## 기술 스택 기준

- Frontend: Next.js 14, TypeScript, Tailwind CSS
- Backend: FastAPI, Python 3.11
- Agent: LangGraph 또는 단순 파이프라인
- Search/RAG: Tavily 또는 사전 샘플 데이터 기반 fallback
- PDF: WeasyPrint 또는 HTML print fallback

