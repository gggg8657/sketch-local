# sketch-local — 손그림 사진을 논문 figure / 그래픽 스타일 다이어그램으로

> **한 줄 요약** — 화이트보드·노트에 손으로 그린 다이어그램 사진을 올리면 로컬 비전 모델이 요소·연결을 읽고, 몇 가지 질문(화살표 방향, 흐린 글자)으로 확인한 뒤
> **원본 그대로 / 단순화 / 인사이트 재구성** 중 고른 방향과 **논문-파스텔·IEEE-모노·Nature 팔레트·손그림·플랫·다크** 등 8가지 스타일로 다시 그려 줍니다.
> 결과는 SVG·PNG·Mermaid·TikZ 로 내보내 보고서·논문·슬라이드에 바로 넣습니다. 파이썬 표준 라이브러리만, CDN 없음, 비전·텍스트 모델은 Ollama/vLLM 그대로.
> 3B 비전 모델로도 요소 5개짜리 스케치를 정확히 읽는 걸 확인했고, GPU 서버의 큰 VL 모델을 붙이면 흐린 글씨·복잡한 그림까지 올라갑니다.

## 실행

```bash
bash setup.sh                 # OS → Python → LLM 서버 탐색 → 비전 모델 확인 → selftest → http://localhost:8774
bash setup.sh stop
python3 app.py --cli sample/sketch1.png --mode 단순화 --style 논문-파스텔 --type 아키텍처   # 질문엔 기본값, Mermaid 를 stdout
```

| 환경변수 | 기본 | 설명 |
|---|---|---|
| `LLM_API` | `ollama` | `ollama` 또는 `openai`(vLLM 등) |
| `LLM_BASE_URL` | `http://localhost:11434` / `:8000/v1` | 서버 주소 |
| `LLM_MODEL` | `qwen3:8b` | 텍스트 모델(그리기·다듬기·TikZ) |
| `VISION_MODEL` | `qwen2.5vl:3b` | 비전 모델(읽기). 서버에선 `qwen2.5vl:32b` 급 권장 |
| `LLM_API_KEY` | (없음) | OpenAI 호환 서버 키 |
| `NUM_CTX` | `16384` | Ollama 컨텍스트 |
| `PORT` | `8774` | |

## 흐름

1. **읽기** — 사진(1600px 로 축소) → 비전 모델 → `{elements, edges, groups, handwriting_notes, guessed_type}` JSON. 서버가 id·방향을 정규화하고 모르는 방향은 `?`+불확실로 표시.
2. **확인** — 읽은 요소/연결을 한 줄 형식으로 보여주고 사용자가 고침 (`n1: 라벨 [종류] (?)`, `n1 -> n2 : 라벨 (?)`).
3. **방향 정하기** — 모드 선택(원본 그대로 / 단순화 N개 이하 / 인사이트 재구성) → 불확실 항목만 질문(최대 3, 기본값 제공) → 스타일·유형 추천(바꿀 수 있음).
4. **그리기** — 텍스트 모델이 Mermaid 작성, 서버가 프리셋(frontmatter 테마·classDef)을 붙여 브라우저에서 렌더. 파싱 오류면 LLM 자동 수정 1회. 인사이트 모드는 해설 문단 추가.
5. **다듬기** — "라벨 영어로", "DB 를 원통으로" 같은 요청으로 반복 수정.
6. **내보내기** — SVG / PNG / Mermaid 소스 / TikZ(코드만) / 번들 저장(`_workspace/<id>/` 에 sketch.png·bundle.json·diagram.mmd).

스타일 8종과 조사 근거는 [STYLES.md](STYLES.md). 유형: 자동·아키텍처·시퀀스·파이프라인·상태도·ER·마인드맵·블록.

## 폐쇄망
폴더 복사만으로 동작(의존성 0, `static/mermaid.min.js` 동봉). 비전 모델(VL)과 텍스트 모델만 서버에 있으면 됨. OpenAI 호환 서버는 이미지 입력(`image_url` data URI)을 지원해야 함(vLLM 의 VL 모델은 지원).

## 한계
- 질문 생성은 규칙 기반(불확실 플래그만 묻는다). 더 똑똑한 질문이 필요하면 `questions()` 를 LLM 로 승급.
- classDef 색상은 flowchart/상태도에만 적용, 시퀀스·ER 은 테마 변수만.
- TikZ 는 컴파일하지 않은 코드. 3B 비전 모델은 점선 묶음·"?" 메모 같은 미묘한 표시를 놓치기도 함(테스트에서 그룹 범위를 과하게 잡음).
