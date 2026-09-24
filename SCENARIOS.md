# 실행 및 검증 시나리오

## 시나리오 A: 워크스페이스 하나를 로컬 Codex에 연결

목표: 하나의 Markdown 폴더를 포트 `8811`에서 검색합니다.

```powershell
Copy-Item .env.example .env
python scripts/check_workspace.py "<workspace>"
docker compose up -d --build
codex mcp add markdownSourceGraphLocal --url http://127.0.0.1:8811/mcp
codex mcp get markdownSourceGraphLocal
```

Codex 프롬프트:

```text
markdownSourceGraphLocal만 사용해서 list_markdown_roots를 호출해줘.
root_id="workspace"에서 "Source Graph"를 검색하고 첫 문서를 읽어줘.
```

## 시나리오 B: 하나의 서버에서 여러 워크스페이스 전환

목표: 컨테이너를 다시 시작하지 않고 `root_id`로 검색 대상을 바꿉니다.

```powershell
Copy-Item .env.hub.example .env
python scripts/check_workspace.py "<hub-path>" --hub --max-depth 4
docker compose up -d --build
```

Codex 프롬프트:

```text
list_markdown_roots로 워크스페이스를 보여줘.
root_id="research"에서 "evaluation"을 검색해줘.
그다음 root_id="teams/wiki"에서 같은 주제를 검색해 결과를 비교해줘.
```

모든 도구 호출에 `root_id`가 들어가므로 동시 접속한 다른 클라이언트의 선택과 충돌하지 않습니다.

## 시나리오 C: 격리된 Codex CLI E2E

목표: 다른 사용자 MCP 설정의 장애에 영향을 받지 않고 이 서버만 실제 호출합니다.

먼저 서버를 실행하고 health를 확인합니다.

```powershell
docker compose up -d --build
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

그다음 사용자 설정을 무시하고 테스트 대상 MCP 하나만 명령행에 주입합니다.

```powershell
$prompt = @'
Use only the markdownSourceGraphLocal MCP tools.
Call list_markdown_roots.
Search root_id markdown-pattern-studio for Source Graph with limit 3.
Read the first 12 lines of the first result.
Return ROOT_COUNT, SEARCH_RESULT_COUNT, FIRST_PATH, READ_TOTAL_LINES.
'@

codex exec `
  --ignore-user-config `
  -c 'mcp_servers.markdownSourceGraphLocal.url="http://127.0.0.1:8811/mcp"' `
  --ephemeral --json --color never -s read-only `
  $prompt
```

기본 모델 설정이 현재 Codex CLI와 맞지 않으면 계정과 CLI에서 지원되는 모델을 `-m`으로 지정합니다.
특정 모델 이름을 프로젝트 기본값으로 강제하지는 않습니다.

성공 로그에는 다음 이벤트가 순서대로 나타나야 합니다.

```text
mcp_tool_call list_markdown_roots completed
mcp_tool_call search_markdown completed
mcp_tool_call read_markdown completed
turn.completed
```

## 시나리오 D: `.mps` 누락 오류

`.mps/source-graph.sqlite`가 없는 폴더를 마운트하면:

- `/healthz`는 HTTP 503
- 응답은 `status: error`, `error`, `action` 포함
- Docker healthcheck는 non-zero
- 컨테이너는 `unhealthy`

사전 검사도 실패해야 합니다.

```powershell
python scripts/check_workspace.py "<empty-workspace>"
Write-Output $LASTEXITCODE
```

예상 종료 코드: `2`.

## 시나리오 E: 로컬 전용 확인

```powershell
docker compose ps
Get-NetTCPConnection -State Listen -LocalPort 8811 |
  Select-Object LocalAddress, LocalPort
```

통과 기준:

```text
PORTS: 127.0.0.1:8811->8811/tcp
LocalAddress: 127.0.0.1
```

`0.0.0.0:8811` 또는 `[::]:8811`로 노출되면 로컬 전용 조건을 통과하지 못한 것입니다.

## 2026-09-24 실제 검증 기록

환경:

- Windows + Docker Desktop 27.2.0
- Docker Compose v2.29.2
- Codex CLI 0.138.0
- MCP transport: Streamable HTTP
- 실제 테스트 포트: `127.0.0.1:18811`
- 등록 이름: `markdownSourceGraphLocal`

검증 결과:

| 항목 | 결과 |
|---|---|
| Agent Docs 구형 kind 인덱스 | 860문서 import/search 성공 |
| Agent Docs 최신 kind 인덱스 | 31,274문서 import/search 성공 |
| Hub 발견 | 실제 워크스페이스 3개 발견 |
| Docker health | `healthy` |
| 로컬 bind | `127.0.0.1:18811` 확인 |
| Codex 등록 | `enabled`, `streamable_http` 확인 |
| Codex 실제 도구 호출 | list → search → read 성공 |
| 검색 결과 | 3개 |
| 첫 문서 | `.agents/skills/source-graph-search/SKILL.md` |
| 읽은 문서 전체 줄 수 | 50 |
| `.mps` 누락 | HTTP 503, healthcheck exit 1 확인 |

첫 Codex 테스트에서는 사용자 기본 모델 `gpt-6-sol`이 해당 ChatGPT 계정용 CLI에서 지원되지 않아
400으로 중단됐습니다. 격리 실행에서 이 호스트가 지원한 `gpt-5.5`를 명시한 뒤 MCP 세 도구 호출이
완료됐습니다. 이는 MCP 서버 오류가 아니라 로컬 Codex CLI 모델 설정 문제였습니다.

## 시나리오 F: 서로 떨어진 두 워크스페이스를 질문에 따라 선택

```powershell
Copy-Item .env.multi.example .env.multi
docker compose --env-file .env.multi -f docker-compose.multi.yml up -d --build
```

도구 호출 흐름:

```text
list_markdown_roots
  → 질문의 대상이 명확하면 search_markdown(root_id=...)
  → 불명확하면 find_relevant_markdown_roots(query=...)
  → 양쪽 자료가 필요하면 search_all_markdown(query=...)
  → 선택한 결과를 read_markdown / get_markdown_links
```

상세 설정과 프롬프트는 [docs/multi-root.md](docs/multi-root.md)를 참고합니다.

### 2026-09-24 실제 Multi-root 검증

| 항목 | 결과 |
|---|---|
| `ai-monitoring` | 31,274문서, 최신 Agent Docs kind |
| `career-signal` | 732문서, 최신 Agent Docs kind |
| Compose 상태 | `healthy`, `127.0.0.1:18812` |
| Hub 목록 | 두 ID, 설명, 호스트 표시 경로 반환 |
| 선택 검색 | `career-signal`에서 `Career Signal Wiki` 검색 성공 |
| 동시 검색 | 두 root에서 각 1개 결과, 오류 없음 |
| 최초 대형 캐시 | 2.18GB Source Graph 포함 약 58초 |
| 후보 탐색 | 두 root의 설명과 샘플 근거 반환 |
| 실제 Codex 선택 | 커리어 질문에 `career-signal` 선택 |
| 실제 Codex 읽기 | `wiki/career-signal/entities/user-career-profile.md`, 전체 121줄 |

최초 검색 뒤 캐시는 Docker named volume에 저장되므로 Source Graph가 변경되지 않으면 재사용됩니다.
후보 탐색은 단순히 첫 후보를 정답으로 간주하지 않고, 루트 설명과 샘플 문서의 실제 내용을 AI가
함께 판단하도록 사용합니다.

## 시나리오 G: Dashboard와 호출 패턴 확인

```powershell
Start-Process http://127.0.0.1:18812/
Invoke-RestMethod "http://127.0.0.1:18812/api/activity?limit=10"
```

실제 검증 결과:

- Overview: Multi 모드, 루트 2개, 문서 32,006개 표시
- Workspaces: 경로, 설명, 문서 수, 캐시와 Source Graph 시각 표시
- Activity: `list_markdown_roots` 1회와 동일한 `search_markdown` 2회 표시
- Parameter Patterns: 검색어 `지원 우선순위`, `root_id=career-signal`, `limit=2` 조합 사용 횟수 2
- 감사 API: `enabled=true`, 오류 0건
- Markdown 본문과 검색 결과 전문은 감사 DB에 저장하지 않음
