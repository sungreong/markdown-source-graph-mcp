# Getting Started

이 문서는 아무것도 설치되지 않은 상태에서 Agent Docs Source Graph를 만들고, 저장소를 클론하고,
Docker로 로컬 MCP 서버를 실행한 다음 Codex에 도구로 등록하는 전체 절차입니다.

## 1. 준비 사항 확인

```powershell
git --version
docker version
docker compose version
code --version
codex --version
```

필수 항목:

- Git
- Docker Desktop 또는 Docker Engine + Compose
- VS Code
- Codex CLI 또는 Codex IDE/Desktop

## 2. Agent Docs for Markdown 설치

[VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=datanewbie-labs.markdown-agent-docs)에서
설치하거나 다음 명령을 실행합니다.

```powershell
code --install-extension datanewbie-labs.markdown-agent-docs
```

검색할 Markdown 폴더를 VS Code로 연 다음:

1. Agent Docs 사이드바를 엽니다.
2. `Agent Docs: Initialize Source Graph`를 실행합니다.
3. `Start Graph` 또는 `Agent Docs: Open Source Graph`를 실행합니다.
4. 다음 파일이 생성됐는지 확인합니다.

```text
<workspace>/.mps/source-graph.sqlite
```

## 3. 저장소 클론

```powershell
cd C:\app
git clone https://github.com/sungreong/markdown-source-graph-mcp.git
cd markdown-source-graph-mcp
```

## 4. 실행 모드 선택

### Single 모드

워크스페이스 하나만 연결합니다.

```powershell
Copy-Item .env.example .env
```

```dotenv
MARKDOWN_MCP_MODE=single
MARKDOWN_MOUNT_SOURCE=C:/Users/you/Documents/my-markdown-workspace
MARKDOWN_PUBLIC_PATH=C:/Users/you/Documents/my-markdown-workspace
MCP_PORT=8811
```

### Hub 모드

허용한 상위 폴더 아래의 여러 워크스페이스를 하나의 MCP에서 선택합니다.

```powershell
Copy-Item .env.hub.example .env
```

```dotenv
MARKDOWN_MCP_MODE=hub
MARKDOWN_MOUNT_SOURCE=C:/Users/you/Documents/ProjectCode
MARKDOWN_PUBLIC_PATH=C:/Users/you/Documents/ProjectCode
MARKDOWN_MCP_DISCOVERY_MAX_DEPTH=4
MARKDOWN_MCP_DISCOVERY_TTL_SECONDS=15
MCP_PORT=8811
```

사용자 홈이나 드라이브 전체를 Hub로 마운트하지 마세요. Markdown 프로젝트만 들어 있는 가장 좁은
상위 폴더를 선택합니다.

### Named Multi-root 모드

공통 상위 폴더가 없는 두 워크스페이스만 정확히 연결하려면 다음 예시를 사용합니다.

```powershell
Copy-Item .env.multi.example .env.multi
docker compose --env-file .env.multi -f docker-compose.multi.yml up -d --build
```

각 경로와 설명은 `.env.multi`에서 바꿉니다. 자세한 사용법은
[docs/multi-root.md](docs/multi-root.md)를 참고하세요.

## 5. 시작 전 검사

Single:

```powershell
python scripts/check_workspace.py "C:/Users/you/Documents/my-markdown-workspace"
```

Hub:

```powershell
python scripts/check_workspace.py "C:/Users/you/Documents/ProjectCode" --hub --max-depth 4
```

성공하면 문서 수와 인덱스 종류가 출력됩니다. 실패하면 종료 코드 `2`이며 Docker를 실행하기 전에
경로나 Agent Docs 인덱스를 고쳐야 합니다.

## 6. Docker Compose 실행

```powershell
docker compose up -d --build
docker compose ps
```

health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

성공 조건:

- HTTP 200
- `status: ok`
- Single: `mps_index_present: true`
- Hub: `root_count`가 1 이상
- `docker compose ps`가 `healthy`

로컬 전용 바인딩도 확인합니다.

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8811 |
  Select-Object LocalAddress, LocalPort
```

`LocalAddress`가 `127.0.0.1`이어야 합니다.

브라우저에서 `http://127.0.0.1:8811/`을 열면 연결된 워크스페이스, 문서 수, 인덱스와 캐시 상태를
대시보드로 확인할 수 있습니다. JSON 상태가 필요할 때는 `/healthz`를 사용합니다.

## 7. Codex에 등록

다른 서버가 같은 포트를 쓰는지 먼저 확인합니다.

```powershell
codex mcp list
```

등록합니다.

```powershell
codex mcp add markdownSourceGraphLocal --url http://127.0.0.1:8811/mcp
codex mcp get markdownSourceGraphLocal
codex mcp list
```

Codex CLI와 IDE는 MCP 설정을 공유합니다. 이미 실행 중인 Codex 세션은 새 도구 목록을 자동으로
다시 읽지 않을 수 있으므로 새 Codex 세션을 시작합니다.

## 8. 첫 사용

Single 모드:

```text
markdownSourceGraphLocal의 list_markdown_roots를 호출해줘.
root_id="workspace"에서 "deployment"를 검색하고 첫 결과의 첫 30줄을 읽어줘.
```

Hub 모드:

```text
markdownSourceGraphLocal의 list_markdown_roots를 호출해줘.
사용 가능한 root_id를 보여준 다음 root_id="teams/wiki"에서 "deployment"를 검색해줘.
첫 결과를 읽고 get_markdown_links로 관련 문서도 확인해줘.
```

## 9. 운영 명령

```powershell
docker compose logs -f markdown-source-graph-mcp
docker compose restart
docker compose stop
docker compose start
docker compose down
```

`restart: unless-stopped`가 설정되어 있으므로 Docker daemon이 재시작되면 컨테이너도 다시 시작됩니다.

## 10. 제거

Codex 등록만 제거:

```powershell
codex mcp remove markdownSourceGraphLocal
```

컨테이너 중지 및 제거:

```powershell
docker compose down
```

검색 캐시 볼륨까지 제거하려는 경우에만 다음을 실행합니다.

```powershell
docker compose down -v
```

원본 Markdown과 `.mps`는 읽기 전용 bind mount이므로 위 명령으로 삭제되지 않습니다.

## 다음 문서

- [README](README.md)
- [실행 시나리오](SCENARIOS.md)
- [Codex 상세 가이드](docs/clients/codex.md)
- [Hub 모드](docs/hub-mode.md)
- [Named Multi-root 모드](docs/multi-root.md)
- [Dashboard와 MCP 호출 이력](docs/dashboard.md)
- [설치·사용 Prompt Pack](docs/prompt-pack.md)
