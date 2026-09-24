# Hub 모드: 하나의 MCP에서 워크스페이스 전환

## 가능한 범위

Docker 컨테이너는 시작된 뒤 클라이언트가 보낸 임의의 호스트 경로를 새 bind mount로 연결할 수
없습니다. Hub 모드는 대신 사용자가 명시적으로 허용한 상위 폴더 하나를 `/markdown`에 읽기 전용으로
마운트합니다. MCP 클라이언트는 그 폴더 아래의 상대 `root_id`를 선택합니다.

서버 전체의 “현재 워크스페이스” 값을 바꾸는 상태 저장형 선택 도구는 두지 않습니다. 여러
클라이언트가 동시에 연결되어도 서로의 선택을 덮어쓰지 않도록 각 검색·읽기 호출에 `root_id`를
전달합니다.

```text
C:/Users/you/Documents/ProjectCode          ← 허용한 Hub
├─ research/.mps/source-graph.sqlite        ← root_id: research
└─ teams/wiki/.mps/source-graph.sqlite      ← root_id: teams/wiki
```

## 설정

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

상위 경로 전체를 컨테이너가 읽을 수 있으므로 범위를 지나치게 넓게 잡지 마세요. 사용자 홈이나
드라이브 루트 대신 Markdown 프로젝트만 들어 있는 전용 상위 폴더를 권장합니다.

## 시작 전 검사

```powershell
python scripts/check_workspace.py "C:/Users/you/Documents/ProjectCode" --hub --max-depth 4
```

지원되는 Source Graph를 하나도 찾지 못하면 종료 코드 `2`를 반환합니다.

## 실행과 상태 확인

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

유효한 워크스페이스가 없으면 health endpoint는 HTTP 503을 반환하고 Docker 상태는 `unhealthy`가
됩니다. 응답의 `error`와 `action` 필드에 원인과 조치가 표시됩니다.

## 클라이언트에서 선택

먼저 목록을 가져옵니다.

```text
markdown-source-graph MCP의 list_markdown_roots를 호출해줘.
root_id, public_path, source_documents, source_updated_at을 표로 보여줘.
```

그다음 모든 도구에 원하는 `root_id`를 전달합니다.

```text
root_id="teams/wiki"에서 "deployment checklist"를 검색해줘.
가장 관련 있는 문서를 읽고 backlink도 확인해줘.
```

다른 워크스페이스로 바꿀 때 컨테이너나 클라이언트 설정을 다시 시작할 필요는 없습니다.

```text
이번에는 root_id="research"에서 같은 주제를 검색하고 앞선 결과와 비교해줘.
```

## 발견 깊이

`MARKDOWN_MCP_DISCOVERY_MAX_DEPTH`는 Hub 바로 아래부터 워크스페이스 폴더까지 허용할 최대 깊이입니다.
너무 작으면 깊은 폴더를 발견하지 못하고, 너무 크면 목록 조회 시간이 늘어날 수 있습니다. 기본값은
`4`, 최대값은 `10`입니다.

발견 목록은 기본 15초 동안 캐시됩니다. 새 워크스페이스의 Source Graph를 만든 직후에는
`MARKDOWN_MCP_DISCOVERY_TTL_SECONDS`만큼 기다리거나 컨테이너를 재시작하면 됩니다.

## 안전장치

- `root_id`는 Hub 아래의 상대 경로만 허용합니다.
- `..`, 절대 경로, Windows 드라이브 경로는 거부합니다.
- Hub와 Markdown 파일은 컨테이너에서 읽기 전용입니다.
- 워크스페이스별 검색 캐시는 서로 다른 상태 디렉터리에 저장됩니다.
- `root_id`가 가리키는 폴더에 지원되는 `.mps/source-graph.sqlite`가 없으면 도구 호출이 실패합니다.
