# 스타일 프리셋 조사 노트 (sketch-local)

손그림을 "전파해도 부끄럽지 않은" 그림으로 바꿀 때 고를 수 있는 룩 8종. 조사 요지와 Mermaid 11 구현 토큰. 구현은 `app.py` 의 `STYLES` 딕셔너리.

## 조사 요지
- ML/CS 논문 아키텍처 figure: 가는 균일 선(0.5~1pt), 회색조 위에 2~3색 강조, 연한 파스텔 채움(채도는 핵심 요소에만), 둥근 모서리 모듈 박스, 영역을 연한 배경 사각형으로 묶음. 패널 a/b/c 마커. Distill 이 퍼뜨린 파랑+주황 조합이 NeurIPS/ICML 기본값. (labfig.com/blog/ai-figures-for-machine-learning-papers, sci-draw.com/blog/ai-architecture-neural-network-diagram-guide)
- IEEE/ACM 블록 다이어그램: 흑백 인쇄 전제, 흰 채움·검은 실선, 선택/미래 요소는 점선, 직각 연결, 세리프 글꼴(Times). (IBM 아키텍처 다이어그램 가이드 ibm.github.io/itaa-docs/Archi-diagrs-v3.pdf 의 단색 규약 참고)
- Nature/Science: 색각이상 안전 Okabe-Ito(Wong 2011, Nature Methods 8:441) 8색 — #E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7 #000000. 범주는 색 + 선 모양을 함께 써서 구분. (sci-draw.com/blog/colorblind-safe-palettes-okabe-ito-reference)
- UML 시퀀스: 흰 참여자 박스, 검은 생명선, activate 막대, Note 상자(연노랑).
- 그래픽 룩: 손그림(roughjs 계열 흔들린 선), 플랫 단색(테두리 없음·흰 글씨·둥근 모서리), 다크 슬라이드(진회색+네온 테두리).
- Mermaid 11: frontmatter `config.look: handDrawn`(스케치), `theme: base` + `themeVariables`(사용자 팔레트는 base 에서만 전부 열림), `theme: neutral`(흑백 인쇄), `classDef`/`class` 로 역할별 색. (mermaid.js.org/config/theming.html)

## 프리셋

| 이름 | 쓸 때 | 엔진 | 토큰 |
|---|---|---|---|
| 논문-파스텔 | NeurIPS/ICML 풍 아키텍처·파이프라인 | theme base | 채움 #DCEBFA(모듈) #E3F4E8(입력) #FDE8D0(출력) #F3E8F8(저장) · 선 #4A5568 1px · Helvetica 14px · rx 6 · subgraph 배경 #F7FAFC |
| IEEE-모노 | 흑백 인쇄 저널·학회 | theme neutral | 흰 채움 · 검정 1.2px · 점선 optional 5 3 · 회색 강조 #E5E5E5 · Times 13px · 직각 curve linear |
| Nature-Okabe-Ito | 범주를 색으로 구분해야 할 때, 색각이상 안전 | theme base | 흰 채움 + 테두리 2px: #0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00 · 선 #333 |
| Distill-블루오렌지 | 흐름 vs 대비 두 축만 강조 | theme base | blue #EAF2FB/#0072B2 · orange #FFF1E0/#E69F00 · grey #F2F2F2/#888 · rx 4 · curve basis |
| 손그림-스케치 | 원본 느낌 유지, 아이디어 단계 공유 | look handDrawn | 기본 테마 + Chalkboard/Comic 계열 글꼴 15px |
| 플랫-컬러풀 | 인포그래픽·포스터·사내 공지 | theme base | 테두리 없음, 채움=테두리 #4C6EF5 #F76707 #12B886 #7950F2 #868E96 · 흰 글씨 · rx 10 |
| 다크-발표용 | 어두운 슬라이드 | theme dark | 채움 #1F2937 · 네온 테두리 #22D3EE #F472B6 #A3E635 2px · 글자 #F9FAFB |
| UML-클래식 | 시퀀스·상태도 교과서 룩 | theme default | actor 흰/검, signal 검정, Note #FFF8DC/#8B8000 |

## 유형
자동 / 아키텍처(flowchart TB + subgraph) / 시퀀스 / 파이프라인(flowchart LR) / 상태도 / ER / 마인드맵 / 블록(block-beta).

## 한계
- classDef 는 flowchart/state 에만 붙는다. 시퀀스·ER·마인드맵은 themeVariables 만 적용.
- handDrawn 룩은 flowchart 계열에서 가장 잘 먹는다.
- TikZ 내보내기는 LLM 변환 코드만 준다(컴파일 안 함). 글꼴·여백은 논문 템플릿에서 조정.
