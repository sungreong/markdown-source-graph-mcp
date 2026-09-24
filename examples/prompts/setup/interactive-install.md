# 대화형 설치 프롬프트

아래 내용을 Codex, Claude Code 또는 Gemini CLI 에이전트에게 전달하세요.

```text
markdown-source-graph-mcp를 이 컴퓨터에 로컬 전용으로 설치하고 연결해줘.

먼저 다음 정보를 한 번에 하나씩 확인하거나 질문해줘.
1. 저장소를 클론할 위치
2. 연결할 Markdown 워크스페이스 경로 목록
3. 각 경로의 용도를 설명하는 짧은 이름과 설명
4. 사용할 로컬 포트
5. 등록할 클라이언트가 Codex, Claude Code, Gemini CLI 중 무엇인지

작업 규칙:
- 저장소의 AGENTS.md, GETTING_STARTED.md, docs/multi-root.md를 먼저 읽어.
- 사용자가 제공하지 않은 호스트 경로를 추측하지 마.
- 각 워크스페이스에서 .mps/source-graph.sqlite 존재 여부를 읽기 전용으로 검사해.
- 하나의 워크스페이스면 Single, 좁은 공통 상위 폴더 아래 여러 개면 Hub,
  서로 떨어진 명시적 경로들이면 Named Multi-root 모드를 추천해.
- 사용자 홈, 드라이브 루트 또는 불필요하게 넓은 상위 폴더를 마운트하지 마.
- 기존 포트와 MCP 등록 이름 충돌을 먼저 확인해.
- .env 또는 .env.multi에는 실제 로컬 경로를 기록하되 Git에 커밋하지 마.
- bind mount는 반드시 read_only로 유지하고 포트는 127.0.0.1에만 열어.
- Docker Compose 실행 후 ps, /healthz, 대시보드, MCP 도구 목록을 확인해.
- list_markdown_roots와 search_markdown을 실제 호출해 연결을 증명해.
- Multi 모드라면 find_relevant_markdown_roots와 search_all_markdown도 검사해.

완료 후 다음을 표로 보고해줘.
- 선택한 모드와 이유
- root_id, 호스트 경로, 설명, 문서 수
- Docker 프로젝트명과 포트
- 등록된 MCP 이름과 endpoint
- 실제 호출한 도구와 결과 요약
- 실행하지 못한 단계와 이유
- 중지, 등록 제거, 볼륨 제거 명령
```
