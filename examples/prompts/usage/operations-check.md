# 운영 점검 프롬프트

```text
markdown-source-graph MCP 운영 상태를 점검해줘.
1. /healthz와 Docker health 상태 확인
2. list_markdown_roots로 mount, .mps, kind, 문서 수, stale 여부 확인
3. 캐시가 stale이면 원인을 설명한 뒤 refresh_markdown_root 실행 여부를 물어봐
4. 최근 MCP Activity에서 실패 호출과 느린 호출을 확인
5. Parameter Patterns에서 자주 쓰는 검색어·root_id·limit 조합을 요약
6. 문제, 영향 범위, 안전한 조치 명령을 표로 보고

Markdown 원문과 .mps를 수정하거나 삭제하지 마. 볼륨 삭제도 명시적인 승인 없이 실행하지 마.
```
