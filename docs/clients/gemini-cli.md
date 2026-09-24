# Gemini CLI 등록 가이드

서버가 먼저 실행 중이어야 합니다.

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8811/healthz
```

## 방법 1: CLI로 등록

Markdown 프로젝트 폴더에서 프로젝트 범위로 등록합니다.

```powershell
gemini mcp add --transport http --scope project markdown-source-graph http://127.0.0.1:8811/mcp
gemini mcp list
```

모든 프로젝트에서 사용하려면 `--scope project`를 `--scope user`로 바꿉니다.

## 방법 2: settings.json 직접 작성

프로젝트 전용 설정은 `.gemini/settings.json`, 사용자 설정은 `~/.gemini/settings.json`에 둡니다.

```json
{
  "mcpServers": {
    "markdown-source-graph": {
      "httpUrl": "http://127.0.0.1:8811/mcp",
      "timeout": 600000,
      "trust": false
    }
  }
}
```

`trust: false`는 도구 호출 확인을 유지합니다. 동작을 확인한 뒤 필요한 경우에만 신뢰 정책을 변경하세요.
복사 가능한 파일은 [`examples/clients/gemini-cli/settings.json`](../../examples/clients/gemini-cli/settings.json)에 있습니다.

Gemini CLI를 다시 시작하고 `/mcp` 또는 `gemini mcp list`로 연결과 도구 검색 상태를 확인합니다.

공식 참고 자료: [Gemini CLI MCP 서버 문서](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md)

