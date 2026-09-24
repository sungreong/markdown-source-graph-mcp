# Dashboard와 MCP 호출 이력

브라우저에서 MCP 주소의 루트 경로를 열면 로컬 대시보드가 표시됩니다.

```text
http://127.0.0.1:8811/
http://127.0.0.1:18812/
```

## 탭

| 탭 | 내용 |
|---|---|
| Overview | 모드, 루트 수, 전체 문서 수, 캐시 수, 호출·오류·평균 지연시간 |
| 지식 검색 | 전체 또는 선택한 워크스페이스를 검색하고 결과를 페이지로 탐색 |
| Workspaces | 루트 ID, 설명, 호스트 표시 경로, 문서 수, Source Graph와 캐시 상태 |
| 도구 안내 | MCP 도구 8개의 용도, 사용 시점, 주요 파라미터, 권장 호출 순서 |
| Activity | 최근 MCP 호출을 검색·도구 필터·페이지 단위로 탐색 |
| Parameter Patterns | 동일 파라미터 조합의 사용 횟수와 지연시간을 검색·페이지 단위로 탐색 |
| 프롬프트 | Codex, Claude Code, Gemini CLI와 공통 프롬프트를 보고 복사 |

Activity에서는 도구별 필터를 사용할 수 있습니다. 화면과 데이터는 10초마다 자동 갱신되며
**지금 새로고침**으로 즉시 갱신할 수 있습니다.

## 기록 범위

기본적으로 다음 메타데이터를 `/data/audit.sqlite3`에 기록합니다.

- 호출 시각과 MCP 도구명
- 검색어, `root_id`, limit, 정렬 방식, 읽기 줄 범위 등 입력 파라미터
- 성공 또는 실패와 오류 메시지
- 실행 시간
- 결과 개수, 후보 개수, 읽은 문서 전체 줄 수 같은 결과 요약

Markdown 본문, 검색 결과 전문, 읽은 문서 내용은 감사 DB에 저장하지 않습니다. 다만 검색어와 파일
경로 자체가 민감할 수 있으므로 `/data` 볼륨과 로컬 포트를 외부에 공개하지 마세요.

## 설정

```dotenv
MARKDOWN_MCP_AUDIT_ENABLED=true
MARKDOWN_MCP_AUDIT_MAX_ENTRIES=2000
```

- `MARKDOWN_MCP_AUDIT_ENABLED=false`: 새 호출 기록을 비활성화
- `MARKDOWN_MCP_AUDIT_MAX_ENTRIES`: 최근 기록 보존 개수, 최소 100, 최대 100,000

보존 한도를 넘으면 가장 오래된 항목부터 자동 삭제됩니다. 기록은 Docker named volume에 저장되므로
컨테이너 재생성 후에도 유지되고 `docker compose down -v`를 실행하면 캐시와 함께 삭제됩니다.

JSON API:

```text
GET /api/search?q=deployment&root_id=workspace&page=1&page_size=10
GET /api/activity?page=1&page_size=20&q=deployment
GET /api/activity?page=1&page_size=20&tool=search_markdown
GET /api/patterns?page=1&page_size=12&q=deployment
GET /api/prompts
GET /api/tools
```

전체 워크스페이스 검색은 한 루트의 결과가 앞 페이지를 독점하지 않도록 루트별 결과를 번갈아
배치합니다. 대시보드 검색도 Activity에 `dashboard_search` 호출로 기록됩니다.
