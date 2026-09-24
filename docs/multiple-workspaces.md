# 여러 Markdown 워크스페이스 실행하기

이 서버는 컨테이너 하나에 Markdown 워크스페이스 하나를 연결합니다. 워크스페이스마다
Agent Docs가 별도의 `.mps/source-graph.sqlite`를 만들기 때문에, 컨테이너와 포트도 분리하면
클라이언트가 어떤 지식베이스를 검색하는지 명확해집니다.

예를 들어 `.env.research`를 만듭니다.

```dotenv
MARKDOWN_MCP_MODE=single
MARKDOWN_MOUNT_SOURCE=C:/Users/you/Documents/research
MARKDOWN_PUBLIC_PATH=C:/Users/you/Documents/research
MCP_PORT=8811
```

두 번째 `.env.wiki`를 만듭니다.

```dotenv
MARKDOWN_MCP_MODE=single
MARKDOWN_MOUNT_SOURCE=C:/Users/you/Documents/wiki
MARKDOWN_PUBLIC_PATH=C:/Users/you/Documents/wiki
MCP_PORT=8812
```

Compose 프로젝트 이름과 환경 파일을 분리해 실행합니다.

```powershell
docker compose --project-name markdown-research --env-file .env.research up -d --build
docker compose --project-name markdown-wiki --env-file .env.wiki up -d --build
```

클라이언트에는 두 서버를 서로 다른 이름으로 등록합니다.

```toml
[mcp_servers.markdown_research]
url = "http://127.0.0.1:8811/mcp"

[mcp_servers.markdown_wiki]
url = "http://127.0.0.1:8812/mcp"
```

중지할 때도 같은 프로젝트 이름과 환경 파일을 사용합니다.

```powershell
docker compose --project-name markdown-research --env-file .env.research down
docker compose --project-name markdown-wiki --env-file .env.wiki down
```
