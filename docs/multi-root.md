# Named Multi-root 모드

공통 상위 폴더 전체를 마운트하지 않고, 서로 떨어진 여러 Markdown 워크스페이스를 이름으로 연결하는
모드입니다. 클라이언트가 런타임에 새 호스트 경로를 추가할 수는 없으며, Compose를 시작할 때 허용한
경로만 읽을 수 있습니다.

## 예시 구성

```text
C:/app/AI_MONITORING
  └─ .mps/source-graph.sqlite       → root_id: ai-monitoring

C:/app/interset_monitoring/my_carrer_signal
  └─ .mps/source-graph.sqlite       → root_id: career-signal
```

```powershell
Copy-Item .env.multi.example .env.multi
```

`.env.multi`:

```dotenv
MARKDOWN_ROOT_1_SOURCE=C:/app/AI_MONITORING
MARKDOWN_ROOT_1_DESCRIPTION=AI monitoring, reports, pipelines, and operational documentation
MARKDOWN_ROOT_2_SOURCE=C:/app/interset_monitoring/my_carrer_signal
MARKDOWN_ROOT_2_DESCRIPTION=Career signals, job research, applications, and personal career documentation
MCP_PORT=18812
```

설명은 AI가 질문에 맞는 루트를 판단할 때 사용하므로 각 워크스페이스의 목적과 주요 자료를 짧고
구체적으로 적습니다. 큰따옴표는 JSON 구성을 깨뜨릴 수 있으므로 설명에 넣지 않습니다.

## 시작 전 검사와 실행

```powershell
python scripts/check_workspace.py "C:/app/AI_MONITORING"
python scripts/check_workspace.py "C:/app/interset_monitoring/my_carrer_signal"
docker compose --env-file .env.multi -f docker-compose.multi.yml up -d --build
docker compose --env-file .env.multi -f docker-compose.multi.yml ps
Invoke-RestMethod http://127.0.0.1:18812/healthz
```

브라우저에서는 `http://127.0.0.1:18812/`을 열어 두 루트의 경로, 설명, 문서 수, 인덱스 갱신 시각,
캐시 상태와 오류를 한 화면에서 확인할 수 있습니다.

두 경로는 각각 `/workspaces/ai-monitoring`과 `/workspaces/career-signal`에 읽기 전용으로 마운트됩니다.
하나가 잘못됐지만 다른 하나가 유효하면 health는 HTTP 200과 `status: degraded`를 반환합니다. 둘 다
쓸 수 없으면 HTTP 503입니다.

Codex 등록:

```powershell
codex mcp add markdownSourceGraphMulti --url http://127.0.0.1:18812/mcp
codex mcp get markdownSourceGraphMulti
```

## 제공되는 선택·검색 도구

| 목적 | 도구 | 동작 |
|---|---|---|
| Hub 목록 | `list_markdown_roots` | ID, 설명, 경로, 문서 수, 인덱스 상태 표시 |
| 질문에 맞는 곳 찾기 | `find_relevant_markdown_roots` | 모든 루트에서 소량 검색해 후보와 근거 반환 |
| 원하는 한 곳 검색 | `search_markdown` | 지정한 `root_id`만 정밀 검색 |
| 여러 곳 동시 검색 | `search_all_markdown` | 전체 또는 지정한 `root_ids`를 한 호출로 검색 |
| 결과 원문 읽기 | `read_markdown` | 결과에 포함된 `root_id`와 상대 경로로 읽기 |
| 문서 관계 확인 | `get_markdown_links` | 같은 루트 안의 link와 backlink 확인 |

## 질문별 사용 예시

대상이 분명한 경우:

```text
AI 모니터링 파이프라인 장애 처리 문서를 찾아줘.
먼저 list_markdown_roots를 확인하고, 설명상 가장 맞는 root_id 하나에서 search_markdown을 실행해.
관련 문서 두 개를 읽고 근거 경로를 함께 보여줘.
```

어느 쪽인지 애매한 경우:

```text
최근 signal 수집 방식에 관한 문서를 찾아줘.
find_relevant_markdown_roots로 두 워크스페이스를 먼저 조사하고,
근거가 가장 강한 root_id에서 다시 정밀 검색해줘.
```

두 영역을 함께 조사하는 경우:

```text
search_all_markdown으로 "weekly report automation"을 모든 root에서 동시에 찾아줘.
root_id별 결과를 구분하고, 각 root에서 가장 관련 있는 문서를 하나씩 읽어 차이를 비교해줘.
```

일부 루트만 동시에 검색:

```text
search_all_markdown의 root_ids를 ["ai-monitoring", "career-signal"]로 지정해서
"notification"을 검색하고 root_id별로 결과를 정리해줘.
```

## 루트 추가

`docker-compose.multi.yml`의 `MARKDOWN_MCP_ROOTS_JSON`에 고유한 `id`, 컨테이너 `path`, 호스트에
표시할 `public_path`, `description`을 추가하고 같은 컨테이너 경로로 읽기 전용 bind mount를
추가합니다. 호스트 경로는 `.env.multi` 변수로 둡니다. 변경 후 컨테이너를 다시 생성해야 합니다.

## 종료와 제거

```powershell
codex mcp remove markdownSourceGraphMulti
docker compose --env-file .env.multi -f docker-compose.multi.yml down
```
