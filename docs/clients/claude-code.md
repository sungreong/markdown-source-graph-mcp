# Claude Code 등록 가이드

서버가 먼저 실행 중이어야 합니다.

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

## 방법 1: CLI로 등록

현재 프로젝트에만 등록하려면 대상 Markdown 프로젝트 폴더에서 실행합니다.

```powershell
claude mcp add --transport http markdown-source-graph --scope project http://127.0.0.1:8811/mcp
claude mcp list
claude mcp get markdown-source-graph
```

프로젝트 범위 설정은 프로젝트 루트의 `.mcp.json`에 저장됩니다. 처음 Claude Code를 열면
프로젝트 MCP 서버 사용 승인을 요청할 수 있습니다.

모든 프로젝트에서 사용하려면 `--scope project` 대신 `--scope user`를 사용합니다.

## 방법 2: .mcp.json 직접 작성

Markdown 프로젝트 루트의 `.mcp.json`에 추가합니다.

```json
{
  "mcpServers": {
    "markdown-source-graph": {
      "type": "http",
      "url": "http://127.0.0.1:8811/mcp"
    }
  }
}
```

`type`을 생략하면 Claude Code가 stdio 서버로 해석할 수 있으므로 반드시 `"http"`로 지정합니다.
복사 가능한 파일은 [`examples/clients/claude-code/.mcp.json`](../../examples/clients/claude-code/.mcp.json)에 있습니다.

Claude Code 안에서 `/mcp`를 실행해 연결 상태와 도구 목록을 확인합니다.

공식 참고 자료: [Claude Code MCP 문서](https://code.claude.com/docs/en/mcp)

