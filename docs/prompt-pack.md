# Prompt Pack

설치와 사용을 에이전트에게 맡길 때 복사해서 사용할 수 있는 프롬프트 모음입니다. 경로와 포트 같은
자리표시자만 자신의 환경에 맞게 바꿉니다.

실행 중인 대시보드의 **프롬프트** 탭에서도 클라이언트와 용도별로 검색하고 **복사하기**를 눌러
바로 사용할 수 있습니다. 대시보드는 이 폴더의 Markdown 원본을 직접 읽으므로 문서와 화면 내용이
따로 관리되지 않습니다.

## 설치 프롬프트

| 대상 | 파일 | 용도 |
|---|---|---|
| 공통 대화형 설치 | [interactive-install.md](../examples/prompts/setup/interactive-install.md) | 에이전트가 필요한 경로를 질문하고 모드를 선택해 설치 |
| Codex | [설치](../examples/prompts/codex/install.md) · [사용](../examples/prompts/codex/use.md) | Codex 등록, E2E, 다중 검색 |
| Claude Code | [설치](../examples/prompts/claude-code/install.md) · [사용](../examples/prompts/claude-code/use.md) | 프로젝트 범위 등록과 근거 조사 |
| Gemini CLI | [설치](../examples/prompts/gemini-cli/install.md) · [사용](../examples/prompts/gemini-cli/use.md) | 프로젝트 범위 등록과 다중 검색 |

## 사용·운영 프롬프트

| 파일 | 용도 |
|---|---|
| [multi-workspace-routing.md](../examples/prompts/usage/multi-workspace-routing.md) | 질문에 맞는 루트 선택 또는 동시 검색 |
| [research-recipes.md](../examples/prompts/usage/research-recipes.md) | 근거 문서 조사, 비교, 영향 범위 분석 |
| [operations-check.md](../examples/prompts/usage/operations-check.md) | health, 마운트, 인덱스, 캐시와 호출 이력 점검 |

설치 프롬프트는 에이전트가 무조건 명령을 실행하게 만들지 않습니다. 먼저 현재 환경과 `.mps`를
읽기 전용으로 확인하고, 사용자가 제공하지 않은 경로를 추측하지 않으며, 기존 MCP 이름이나 포트가
충돌하면 사용자에게 알려 다른 값을 선택하도록 작성되어 있습니다.
