# Codex 대화형 설치

```text
이 저장소의 AGENTS.md, GETTING_STARTED.md, docs/clients/codex.md를 먼저 읽어줘.
markdown-source-graph-mcp를 Codex에 로컬 전용으로 연결하고 싶어.

작업 전에 나에게 다음을 차례로 물어봐:
- 연결할 Markdown 워크스페이스 경로와 각 공간의 용도
- 사용할 포트와 MCP 등록 이름
- 한 공간만 연결할지, 여러 공간을 분리해서 연결할지

각 경로에서 .mps/source-graph.sqlite를 검사하고 Single/Hub/Multi 중 가장 좁고 안전한 모드를
선택해. 워크스페이스는 read_only, 포트는 127.0.0.1만 사용해. 기존 포트와 MCP 이름 충돌도 확인해.

Docker 실행 후 /healthz와 대시보드를 확인하고 다음 형태로 등록해:
codex mcp add <MCP_NAME> --url http://127.0.0.1:<PORT>/mcp

codex mcp get으로 등록을 확인하고, 격리된 E2E에서 list_markdown_roots → 질문 기반 root 선택 →
search_markdown → read_markdown을 실제로 실행해. Multi 모드면 search_all_markdown도 확인해.
마지막에는 설정, root별 문서 수, 검증 결과, 중지와 제거 명령을 보고해줘.
```
