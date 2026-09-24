# 조사 프롬프트 모음

```text
"<TOPIC>"의 기준 문서를 찾아줘. 검색 결과 제목만 요약하지 말고 원문을 읽어 근거 문장과 경로,
Source Graph 갱신 시각을 함께 제공해. 충돌하는 내용이 있으면 최신 문서와 기준 문서를 구분해줘.
```

```text
<RELATIVE_PATH>를 변경하기 전에 get_markdown_links의 incoming과 outgoing을 모두 조사해.
직접 링크, backlink, 함께 수정해야 할 가능성이 있는 문서를 root_id와 경로별로 정리해줘.
```

```text
root_id=<ROOT_A>와 root_id=<ROOT_B>에서 "<QUERY>"를 각각 검색해.
각 루트의 상위 문서를 실제로 읽고 관점, 기준일, 근거 수준의 차이를 비교해줘.
```

```text
modified_from=<YYYY-MM-DD> 이후의 "<QUERY>" 문서만 최근순으로 찾아줘.
상위 5개를 읽고 새로 추가되거나 바뀐 내용을 날짜와 경로별로 요약해줘.
```
