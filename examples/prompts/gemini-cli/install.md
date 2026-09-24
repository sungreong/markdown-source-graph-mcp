# Gemini CLI 대화형 설치

```text
GETTING_STARTED.md와 docs/clients/gemini-cli.md를 읽고 markdown-source-graph-mcp 설치를 진행해줘.
먼저 연결할 워크스페이스 경로와 설명, 포트, 등록 이름을 물어봐. 각 Source Graph를 검사하고
Single/Hub/Multi 중 적절한 모드를 선택해. read_only mount와 127.0.0.1 바인딩을 유지해.

Docker health와 대시보드를 확인하고 다음 형태로 프로젝트 범위에 등록해:
gemini mcp add --transport http --scope project <MCP_NAME> http://127.0.0.1:<PORT>/mcp

gemini mcp list, list_markdown_roots, 검색과 읽기 호출을 실제로 확인해. Multi 모드면 질문 기반 root
선택과 전체 동시 검색도 테스트하고 설정·검증·제거 방법을 정리해줘.
```
