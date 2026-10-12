# 제3자 구성요소 (Third-party notices) — sketch-local

조사일 2026-10-12. 실제 파일(`static/`, `setup.sh`, `app.py` import, `ui.html`, `sample/`) 기준. 라이선스는 각 프로젝트의 LICENSE / npm 메타데이터 / 모델 카드에서 확인했다.
이 표는 고지용 정리이며 법률 자문이 아니다. 상업 이용 전에는 원문을 다시 확인할 것.

## 동봉 (저장소에 들어 있음)

| 이름 | 버전 | 쓰임 | 라이선스 | 링크 | 상업 이용 | 비고 |
|---|---|---|---|---|---|---|
| mermaid | 11.17.2 | 동봉 `static/mermaid.min.js` (diagram-local 과 같은 파일) | MIT | https://github.com/mermaid-js/mermaid | 가능 | 원문 `licenses/mermaid-LICENSE.txt`. 수정하지 않은 배포본 |
| └ mermaid 번들 안의 의존성 | mermaid 11.17.2 기준 | 위 파일 안에 함께 번들됨 | d3 (ISC), d3-sankey (BSD-3-Clause), dagre-d3-es · cytoscape · katex · khroma · marked · roughjs · stylis · dayjs 등 (MIT), chevrotain (Apache-2.0), DOMPurify (MPL-2.0 OR Apache-2.0) | https://www.npmjs.com/package/mermaid | 가능 | 전체 목록은 diagram-local 의 THIRD_PARTY_NOTICES 와 같음. DOMPurify 원문 `licenses/dompurify-LICENSE.txt` |

## 참고만 한 것 (코드·데이터 복사 없음)

| 이름 | 쓰임 | 권리 | 비고 |
|---|---|---|---|
| Okabe & Ito 색각 친화 팔레트 (Wong, *Nature Methods* 8:441, 2011) | 스타일 프리셋의 색 값 8개 | 색 값(사실 정보) | 출처 표기만 |
| 스타일 이름 "IEEE-모노", "Nature(Okabe-Ito)", "Distill" | 스타일 프리셋 이름 | IEEE, Nature, Distill 은 각 소유자의 이름·상표 | 서식 분위기를 뜻할 뿐, 해당 기관의 공식 템플릿·제휴·보증이 아님 (NOTICE 참고) |

## 실행 환경 (동봉 안 함)

| 이름 | 버전 | 쓰임 | 라이선스 | 링크 | 상업 이용 | 비고 |
|---|---|---|---|---|---|---|
| Python 표준 라이브러리 | 3.9+ | 서버(`app.py`) — 외부 pip 패키지 없음 | PSF-2.0 | https://docs.python.org/3/license.html | 가능 | |
| Ollama | 설치 시점 최신 | `setup.sh` 가 없으면 설치 — LLM 실행기 | MIT | https://github.com/ollama/ollama | 가능 | |

## 모델 가중치 (저장소에 없음 — 사용자가 내려받음)

| 이름 | 쓰임 | 라이선스 | 링크 | 상업 이용 | 비고 |
|---|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct (`qwen2.5vl:3b`) | **기본 비전 모델** (`app.py` `VISION_MODEL` 기본값, `setup.sh` 가 없으면 pull) | Qwen RESEARCH LICENSE (비상업) | https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE | **비상업** | [#1](https://github.com/gggg8657/sketch-local/issues/1) — `VISION_MODEL=qwen2.5vl:7b` 로 회피 |
| Qwen2.5-VL-7B-Instruct (`qwen2.5vl:7b`) | 대체 비전 모델 | Apache-2.0 | https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct | 가능 | |
| Qwen3-8B (`qwen3:8b`) | `setup.sh` 기본 pull 텍스트 모델 | Apache-2.0 | https://huggingface.co/Qwen/Qwen3-8B | 가능 | `MODEL=` 로 변경 |
| Gemma 4 31B (`gemma4:31b`) | 포털 배포 기본 모델(텍스트·비전) | Apache-2.0 | https://ai.google.dev/gemma/docs/gemma_4_license | 가능 | |

## 확인 필요

- **Qwen2.5-VL-3B (`qwen2.5vl:3b`) — Qwen Research License, 비상업** → [#1](https://github.com/gggg8657/sketch-local/issues/1).
  상업 이용 시 `VISION_MODEL=qwen2.5vl:7b`(Apache-2.0) 또는 `VISION_MODEL=gemma4:31b`(Apache-2.0)로 실행. 가중치는 저장소에 넣지 않는다.

## 이 저장소의 원저작물

`app.py`, `ui.html`, `goal-prompt.md`, `STYLES.md`, `selftest.py`, `setup.sh`, `README.md`, `sample/*.svg` — DongJu Kim (gggg8657), MIT (`LICENSE`).
