# Claude Code 대화형 설치

```text
이 저장소의 GETTING_STARTED.md와 docs/clients/claude-code.md를 읽고 설치를 도와줘.
먼저 연결할 워크스페이스 경로, 각 설명, 포트, MCP 이름을 나에게 물어봐.
각 .mps/source-graph.sqlite를 사전 검사하고 Single/Hub/Multi 중 안전한 구성을 설명해줘.
모든 mount는 read_only, 포트는 127.0.0.1이어야 하며 기존 설정을 덮어쓰지 마.

Docker health와 대시보드를 확인한 다음 아래 형태로 프로젝트 범위에 등록해:
claude mcp add --transport http <MCP_NAME> --scope project http://127.0.0.1:<PORT>/mcp

claude mcp list와 실제 list/search/read 호출로 확인하고, 변경 내용과 제거 명령을 보고해줘.
```
