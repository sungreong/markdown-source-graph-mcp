from __future__ import annotations

from typing import Any


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_markdown_roots",
        "label": "워크스페이스 목록",
        "purpose": "연결된 지식 공간과 문서 수, 인덱스·캐시 상태를 확인합니다.",
        "when": "검색을 시작하거나 사용할 root_id를 모를 때",
        "parameters": [],
        "returns": "root_id, 설명, 경로, 문서 수, 갱신 상태",
        "step": 1,
    },
    {
        "name": "find_relevant_markdown_roots",
        "label": "관련 공간 찾기",
        "purpose": "질문을 각 루트에 가볍게 검색해 적합한 워크스페이스 후보와 근거를 찾습니다.",
        "when": "질문이 어느 워크스페이스에 속하는지 불분명할 때",
        "parameters": ["query", "sample_results_per_root"],
        "returns": "루트별 설명과 샘플 문서",
        "step": 2,
    },
    {
        "name": "search_markdown",
        "label": "한 공간 검색",
        "purpose": "선택한 Source Graph에서 제목과 본문을 검색합니다.",
        "when": "검색할 root_id가 명확할 때",
        "parameters": ["query", "root_id", "limit", "modified_from", "modified_to", "sort_by"],
        "returns": "문서 경로, 제목, excerpt, heading, 수정 시각",
        "step": 3,
    },
    {
        "name": "search_all_markdown",
        "label": "여러 공간 동시 검색",
        "purpose": "전체 또는 지정한 여러 워크스페이스를 한 번에 검색합니다.",
        "when": "질문이 여러 프로젝트에 걸치거나 결과를 비교할 때",
        "parameters": ["query", "root_ids", "limit_per_root", "sort_by"],
        "returns": "root_id가 포함된 통합 검색 결과와 루트별 오류",
        "step": 3,
    },
    {
        "name": "read_markdown",
        "label": "문서 원문 읽기",
        "purpose": "검색 결과의 Markdown을 필요한 줄 범위만 안전하게 읽습니다.",
        "when": "검색 결과의 실제 근거를 확인할 때",
        "parameters": ["root_id", "relative_path", "start_line", "max_lines"],
        "returns": "줄 번호 범위, 전체 줄 수, Markdown 내용",
        "step": 4,
    },
    {
        "name": "get_markdown_links",
        "label": "연결 문서 확인",
        "purpose": "문서가 참조하는 링크와 이 문서를 참조하는 backlink를 조사합니다.",
        "when": "관련 문서나 변경 영향 범위를 파악할 때",
        "parameters": ["root_id", "relative_path", "direction", "limit"],
        "returns": "outgoing과 incoming 문서 목록",
        "step": 5,
    },
    {
        "name": "get_source_graph_status",
        "label": "인덱스 상태 확인",
        "purpose": "특정 루트의 Source Graph 호환성, 문서 수, 캐시 최신성을 확인합니다.",
        "when": "검색 결과가 오래됐거나 연결 문제를 진단할 때",
        "parameters": ["root_id"],
        "returns": "kind, 갱신 시각, 캐시 문서 수, stale 상태",
        "step": 6,
    },
    {
        "name": "refresh_markdown_root",
        "label": "검색 캐시 갱신",
        "purpose": "현재 Source Graph를 검색 캐시로 다시 가져옵니다. 원본은 수정하지 않습니다.",
        "when": "Source Graph가 갱신됐지만 즉시 캐시를 새로 만들고 싶을 때",
        "parameters": ["root_id"],
        "returns": "가져온 문서 수와 갱신 시각",
        "step": 6,
    },
]


def tool_catalog() -> list[dict[str, Any]]:
    return TOOLS
