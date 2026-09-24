# GitHub Pages 안내 사이트

프로젝트 루트의 `index.html`은 Markdown Source Graph MCP를 소개하는 정적 사이트입니다.

공개 주소:

```text
https://sungreong.github.io/markdown-source-graph-mcp/
```

![Markdown Source Graph MCP 프로젝트 소개 사이트](../assets/github-pages-preview.png)

## 제공하는 내용

- 프로젝트 목적과 로컬 전용 보안 모델
- MCP 도구 8개의 용도와 주요 파라미터
- Agent Docs 설치부터 Docker Compose 실행까지의 순서
- Codex, Claude Code, Gemini CLI 등록 명령
- Single, Hub, Named Multi-root 모드 비교
- 로컬 대시보드 화면 미리보기

GitHub Pages는 안내용 정적 사이트입니다. 사용자의 Markdown, `.mps` 인덱스, 검색 결과, 감사 이력에
접근하지 않습니다. 실제 검색은 Docker Compose로 실행한 `http://127.0.0.1:8811/`에서만 수행합니다.

## 배포 방식

`.github/workflows/pages.yml`이 `main`의 사이트 관련 파일 변경을 감지해 배포합니다.

1. `index.html`, `site/`, 필요한 `assets/`를 `_site`에 모읍니다.
2. GitHub Pages artifact를 업로드합니다.
3. `github-pages` 환경에 배포합니다.

Actions 탭에서 **Deploy GitHub Pages** 워크플로를 수동 실행할 수도 있습니다.

## 로컬 미리보기

저장소 루트에서 다음을 실행합니다.

```powershell
python -m http.server 4173
```

브라우저에서 `http://127.0.0.1:4173/`을 엽니다. 이 미리보기 역시 제품 안내 사이트이며 MCP 검색
대시보드가 아닙니다.
