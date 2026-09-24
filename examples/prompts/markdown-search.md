# MCP 확인용 프롬프트

아래 프롬프트는 Codex, Claude Code, Gemini CLI에서 공통으로 사용할 수 있습니다.

## 연결 확인

```text
markdown-source-graph MCP의 list_markdown_roots 도구를 호출해줘.
현재 워크스페이스의 Source Graph 상태와 문서 수를 알려줘.
```

## 근거 검색

```text
markdown-source-graph MCP를 사용해 "agent evaluation"을 검색해줘.
관련성이 높은 문서 5개를 고르고 경로, 제목, 관련 heading, 핵심 근거를 정리해줘.
```

## 링크와 백링크 탐색

```text
먼저 "MCP tooling"을 검색해 기준 문서를 찾아줘.
그다음 get_markdown_links를 사용해 해당 문서의 outgoing link와 backlink를 확인하고,
함께 읽어야 할 문서와 그 이유를 알려줘.
```

## 변경 전 영향 범위 확인

```text
docs/architecture.md를 수정하기 전에 markdown-source-graph MCP를 사용해
이 문서를 참조하는 문서와 이 문서가 참조하는 문서를 찾아줘.
아직 파일은 수정하지 말고 검토 순서와 변경 위험만 정리해줘.
```

## Hub 모드에서 워크스페이스 전환

```text
먼저 list_markdown_roots를 호출해 사용할 수 있는 워크스페이스를 보여줘.
root_id="teams/wiki"에서 "release process"를 검색한 다음,
root_id="research"에서 같은 주제를 검색해 두 결과의 차이를 비교해줘.
각 도구 호출에는 해당 root_id를 명시해줘.
```
