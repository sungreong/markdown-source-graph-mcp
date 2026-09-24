# Repository Agent Instructions

이 저장소에서 작업하는 에이전트는 변경 전에 다음 문서를 순서대로 읽습니다.

1. `GETTING_STARTED.md` — 처음 설치하고 로컬 MCP를 연결하는 표준 절차
2. `README.md` — 기능, 환경 변수, 도구, 보안 모델
3. `SCENARIOS.md` — Single/Hub/Codex E2E 및 실패 시나리오
4. 다중 루트 작업이라면 `docs/multi-root.md`
5. 대시보드나 감사 이력 작업이라면 `docs/dashboard.md`
6. 작업 대상 클라이언트 문서
   - Codex: `docs/clients/codex.md`
   - Claude Code: `docs/clients/claude-code.md`
   - Gemini CLI: `docs/clients/gemini-cli.md`

## 변경 원칙

- Markdown 워크스페이스와 `.mps/source-graph.sqlite`는 항상 읽기 전용으로 유지합니다.
- MCP 포트는 `127.0.0.1`에만 publish합니다. 인증과 TLS 없이 `0.0.0.0` 또는 LAN에 공개하지 않습니다.
- 클라이언트가 임의의 호스트 절대 경로를 마운트하게 만들지 않습니다. Hub 모드에서는 미리 허용한
  상위 폴더 아래의 상대 `root_id`만 받고, Multi 모드에서는 시작 시 명시한 allowlist만 사용합니다.
- `.env`는 로컬 설정이므로 커밋하지 않습니다. 배포 가능한 예시는 `.env.example`과
  `.env.hub.example`에서 관리합니다.
- 포트, MCP 이름, 환경 변수, 도구 이름을 변경하면 README, Getting Started, Scenarios,
  `docs/clients/`, `examples/clients/`를 함께 갱신합니다.
- 다음 인덱스 식별자의 하위 호환성을 유지합니다.
  - `markdown-agent-docs.source-graph`
  - `markdown-pattern-studio.source-graph`
- 오류를 숨기지 않습니다. 잘못된 마운트나 인덱스에는 `/healthz`가 HTTP 503과 `error`, `action`을
  반환해야 합니다.
- 감사 이력에는 도구 파라미터와 결과 요약만 저장하고 Markdown 본문이나 검색 결과 전문을 저장하지
  않습니다. 대시보드는 로컬 bind 정책을 우회하지 않습니다.

## 필수 검증

Python 변경 후:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Compose 변경 후:

```powershell
python scripts/check_workspace.py "<workspace-or-hub-path>" [--hub --max-depth 4]
docker compose config
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:<port>/healthz
```

Codex 등록 변경 후:

```powershell
codex mcp get markdownSourceGraphLocal
codex mcp list
```

가능하면 `SCENARIOS.md`의 격리된 Codex CLI E2E를 실행해 다음 호출을 증명합니다.

```text
list_markdown_roots → search_markdown → read_markdown
```

## 여러 워크스페이스 마운트

공통 상위 폴더가 없는 경로는 `docker-compose.multi.yml`을 사용합니다. 저장소의 `.env.multi.example`을
로컬 `.env.multi`로 복사하고 호스트 경로와 설명을 수정합니다.

```powershell
Copy-Item .env.multi.example .env.multi
python scripts/check_workspace.py "C:/path/to/workspace-one"
python scripts/check_workspace.py "D:/path/to/workspace-two"
docker compose --env-file .env.multi -f docker-compose.multi.yml config
docker compose --env-file .env.multi -f docker-compose.multi.yml up -d --build
```

Compose의 각 루트는 아래 세 위치가 한 세트입니다.

1. `.env.multi`의 호스트 경로 변수
2. `volumes`의 고정 컨테이너 `target`과 `read_only: true`
3. `MARKDOWN_MCP_ROOTS_JSON`의 고유 `id`, 동일한 컨테이너 `path`, 호스트 `public_path`, 설명

예를 들어 `/workspaces/ai-monitoring`으로 bind mount했다면 JSON의 `path`도 정확히
`/workspaces/ai-monitoring`이어야 합니다. 루트를 추가하거나 제거할 때 이 세 곳을 함께 바꾸고
컨테이너를 다시 생성합니다. 사용자 홈, 드라이브 루트, `C:/app` 전체처럼 불필요하게 넓은 경로를
대신 마운트하지 않습니다. 자세한 예시는 `docs/multi-root.md`를 따릅니다.

검증 명령:

```powershell
docker compose --env-file .env.multi -f docker-compose.multi.yml ps
Invoke-RestMethod http://127.0.0.1:<port>/healthz
```

`list_markdown_roots`에 모든 ID와 설명이 나타나는지, `find_relevant_markdown_roots`가 후보를 찾는지,
`search_markdown`이 지정한 한 루트만 검색하는지, `search_all_markdown`이 여러 루트를 동시에
검색하는지 확인합니다.

## 완료 보고

최종 응답에는 다음을 구분해 적습니다.

- 구현한 기능
- 실제 실행한 검증
- 실행하지 못한 검증과 이유
- 현재 실행 중인 컨테이너와 등록된 MCP 이름
- 사용자 설정에 발생한 변경과 제거 방법
