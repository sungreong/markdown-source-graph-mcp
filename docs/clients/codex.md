# Codex 등록 가이드

서버가 먼저 실행 중이어야 합니다.

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

## 방법 1: CLI로 등록

Codex CLI와 IDE 확장은 MCP 설정을 공유합니다.

```powershell
codex mcp add markdownSourceGraphLocal --url http://127.0.0.1:8811/mcp
codex mcp get markdownSourceGraphLocal
codex mcp list
```

설정 후 Codex를 다시 시작합니다.

## 방법 2: config.toml에 직접 등록

사용자 전체 설정은 `~/.codex/config.toml`, 신뢰한 프로젝트 전용 설정은
프로젝트의 `.codex/config.toml`에 다음 내용을 추가합니다.

```toml
[mcp_servers.markdown_source_graph]
url = "http://127.0.0.1:8811/mcp"
```

복사 가능한 예시는 [`examples/clients/codex/config.toml`](../../examples/clients/codex/config.toml)에 있습니다.

## 확인 프롬프트

```text
markdownSourceGraphLocal의 list_markdown_roots 도구를 호출하고,
현재 인덱스의 문서 수와 갱신 시각을 알려줘.
```

도구가 보이지 않으면 `codex mcp list`, Docker 상태, 포트가 일치하는지 확인한 뒤 Codex를 재시작합니다.

실제로 Codex가 `list_markdown_roots → search_markdown → read_markdown`을 호출하는 격리 테스트는
[SCENARIOS.md](../../SCENARIOS.md)의 **시나리오 C**를 따르세요. 전체 설치 순서는
[GETTING_STARTED.md](../../GETTING_STARTED.md)를 참고하세요.

공식 참고 자료: [OpenAI Docs MCP 연결 예시](https://developers.openai.com/learn/docs-mcp)
