#!/usr/bin/env python3
"""sketch local — 손그림 사진을 비전 모델이 읽고, 대화로 방향을 정한 뒤, 논문 figure/그래픽 스타일 Mermaid 로 다시 그린다.
외부 의존성 없음(stdlib), CDN 없음(static/mermaid.min.js 동봉).

  python3 app.py                                   # http://localhost:8774
  VISION_MODEL=qwen2.5vl:7b LLM_MODEL=qwen3:32b python3 app.py
  LLM_API=openai LLM_BASE_URL=http://gpu:8000/v1 LLM_MODEL=Qwen3-32B VISION_MODEL=Qwen2.5-VL-32B python3 app.py
  python3 app.py --cli sketch.jpg --mode 단순화 --style 논문-파스텔 --type 아키텍처     # 질문엔 기본값, Mermaid 를 stdout 에

흐름: 읽기(비전 → JSON) → 확인/수정 → 모드(원본/단순화/인사이트) → 불확실 항목 질문(최대 3) → 스타일·유형 → 그리기(텍스트 LLM → Mermaid) → 다듬기 → 내보내기
"""
import base64
import datetime
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(ROOT, "_workspace")
LLM_API = os.environ.get("LLM_API", "ollama")            # ollama | openai (vLLM·LM Studio 등)
LLM_BASE = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1" if LLM_API == "openai" else "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")           # 텍스트(그리기·TikZ)
VISION = os.environ.get("VISION_MODEL", "qwen2.5vl:3b")   # 비전(읽기) — 서버에선 더 큰 VL 모델
LLM_KEY = os.environ.get("LLM_API_KEY", "")
PORT = int(os.environ.get("PORT", "8774"))
NUM_CTX = int(os.environ.get("NUM_CTX", "16384"))
MAX_QUESTIONS = 3
HEADS = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "erDiagram", "stateDiagram", "gantt", "mindmap", "timeline", "pie",
         "block-beta", "journey", "quadrantChart", "xychart", "C4Context")

# 유형: 이름 → (Mermaid 선언, 설명)
TYPES = {
    "자동": ("", "내용에 맞춰 고름"),
    "아키텍처": ("flowchart TB", "시스템 아키텍처 — subgraph 로 계층·영역을 묶고 모듈 간 화살표"),
    "시퀀스": ("sequenceDiagram", "참여자 간 메시지 순서"),
    "파이프라인": ("flowchart LR", "좌→우 데이터/처리 파이프라인"),
    "상태도": ("stateDiagram-v2", "상태와 전이"),
    "ER": ("erDiagram", "엔티티와 관계"),
    "마인드맵": ("mindmap", "중심 주제에서 가지"),
    "블록": ("block-beta", "격자형 블록 다이어그램(columns N)"),
}
# guessed_type(비전 모델이 추정) → 유형
GUESS2TYPE = {"architecture": "아키텍처", "system": "아키텍처", "sequence": "시퀀스", "pipeline": "파이프라인", "flow": "파이프라인",
              "state": "상태도", "er": "ER", "entity": "ER", "mindmap": "마인드맵", "mind": "마인드맵", "block": "블록"}

# 스타일 프리셋 (STYLES.md 참고). config → Mermaid frontmatter, classdef → flowchart/state 전용 classDef 블록, guide → LLM 지시
STYLES = {
    "논문-파스텔": {
        "config": {"theme": "base", "themeVariables": {"fontFamily": "Helvetica, Arial, sans-serif", "fontSize": "14px", "primaryColor": "#DCEBFA",
                   "primaryBorderColor": "#4A5568", "primaryTextColor": "#1A202C", "lineColor": "#4A5568", "secondaryColor": "#FDE8D0",
                   "tertiaryColor": "#E3F4E8", "clusterBkg": "#F7FAFC", "clusterBorder": "#CBD5E0", "edgeLabelBackground": "#FFFFFF"},
                   "flowchart": {"curve": "basis", "padding": 12}},
        "classdef": ["classDef input fill:#E3F4E8,stroke:#4A5568,stroke-width:1px,rx:6,ry:6",
                     "classDef module fill:#DCEBFA,stroke:#4A5568,stroke-width:1px,rx:6,ry:6",
                     "classDef output fill:#FDE8D0,stroke:#4A5568,stroke-width:1px,rx:6,ry:6",
                     "classDef store fill:#F3E8F8,stroke:#4A5568,stroke-width:1px",
                     "classDef note fill:#FFFFFF,stroke:#A0AEC0,stroke-dasharray:4 3,color:#4A5568"],
        "guide": "NeurIPS/ICML 아키텍처 figure 풍: 연한 파스텔 채움, 가는 회색 선, 둥근 모서리. 노드에 class 를 붙인다 — 입력/데이터=input, 처리 모듈=module, 출력/결과=output, 저장소/DB=store, 주석=note. 영역은 subgraph.",
    },
    "IEEE-모노": {
        "config": {"theme": "neutral", "themeVariables": {"fontFamily": "Times New Roman, serif", "fontSize": "13px"}, "flowchart": {"curve": "linear"}},
        "classdef": ["classDef block fill:#FFFFFF,stroke:#000000,stroke-width:1.2px",
                     "classDef optional fill:#FFFFFF,stroke:#000000,stroke-width:1px,stroke-dasharray:5 3",
                     "classDef emph fill:#E5E5E5,stroke:#000000,stroke-width:1.5px"],
        "guide": "IEEE/ACM 블록 다이어그램: 흑백, 흰 채움에 검은 실선, 선택 요소는 점선(optional), 강조는 회색(emph). 직각 연결, 장식 없음. 모든 노드에 block/optional/emph 중 하나.",
    },
    "Nature-Okabe-Ito": {
        "config": {"theme": "base", "themeVariables": {"fontFamily": "Helvetica, Arial, sans-serif", "fontSize": "14px", "primaryColor": "#FFFFFF",
                   "primaryBorderColor": "#0072B2", "lineColor": "#333333", "clusterBkg": "#FAFAFA", "clusterBorder": "#BBBBBB"}},
        "classdef": ["classDef c1 fill:#FFFFFF,stroke:#0072B2,stroke-width:2px", "classDef c2 fill:#FFFFFF,stroke:#E69F00,stroke-width:2px",
                     "classDef c3 fill:#FFFFFF,stroke:#009E73,stroke-width:2px", "classDef c4 fill:#FFFFFF,stroke:#CC79A7,stroke-width:2px",
                     "classDef c5 fill:#FFFFFF,stroke:#56B4E9,stroke-width:2px", "classDef c6 fill:#FFFFFF,stroke:#D55E00,stroke-width:2px"],
        "guide": "Nature Methods 권장 색각이상 안전 팔레트(Okabe-Ito). 흰 채움에 색 테두리로 범주를 구분: 같은 역할의 노드는 같은 class(c1~c6). 범주가 6개 이하가 되게.",
    },
    "Distill-블루오렌지": {
        "config": {"theme": "base", "themeVariables": {"fontFamily": "Inter, Helvetica, sans-serif", "fontSize": "14px", "primaryColor": "#EAF2FB",
                   "primaryBorderColor": "#0072B2", "primaryTextColor": "#1A1A1A", "lineColor": "#555555", "secondaryColor": "#FFF1E0",
                   "clusterBkg": "#F8F8F8", "clusterBorder": "#DDDDDD"}, "flowchart": {"curve": "basis"}},
        "classdef": ["classDef blue fill:#EAF2FB,stroke:#0072B2,stroke-width:1.5px,rx:4,ry:4",
                     "classDef orange fill:#FFF1E0,stroke:#E69F00,stroke-width:1.5px,rx:4,ry:4",
                     "classDef grey fill:#F2F2F2,stroke:#888888,stroke-width:1px,rx:4,ry:4"],
        "guide": "Distill 풍 두 색 강조: 주 흐름=blue, 대비·강조=orange, 보조=grey. 그 외 색 금지.",
    },
    "손그림-스케치": {
        "config": {"look": "handDrawn", "theme": "default", "themeVariables": {"fontFamily": "Chalkboard SE, Comic Sans MS, cursive", "fontSize": "15px"}},
        "classdef": [],
        "guide": "손그림 느낌(handDrawn look). 원본 스케치의 배치·장난기를 살리되 글씨만 정돈. class 없이 기본 모양.",
    },
    "플랫-컬러풀": {
        "config": {"theme": "base", "themeVariables": {"fontFamily": "Helvetica, Arial, sans-serif", "fontSize": "15px", "primaryColor": "#4C6EF5",
                   "primaryTextColor": "#FFFFFF", "primaryBorderColor": "#4C6EF5", "lineColor": "#495057", "clusterBkg": "#F1F3F5", "clusterBorder": "#F1F3F5"},
                   "flowchart": {"curve": "basis"}},
        "classdef": ["classDef k1 fill:#4C6EF5,stroke:#4C6EF5,color:#FFFFFF,rx:10,ry:10", "classDef k2 fill:#F76707,stroke:#F76707,color:#FFFFFF,rx:10,ry:10",
                     "classDef k3 fill:#12B886,stroke:#12B886,color:#FFFFFF,rx:10,ry:10", "classDef k4 fill:#7950F2,stroke:#7950F2,color:#FFFFFF,rx:10,ry:10",
                     "classDef k5 fill:#868E96,stroke:#868E96,color:#FFFFFF,rx:10,ry:10"],
        "guide": "그래픽/인포그래픽 풍: 테두리 없는 진한 단색 채움에 흰 글씨, 둥근 모서리. 역할별로 k1~k5 를 돌려 쓴다.",
    },
    "다크-발표용": {
        "config": {"theme": "dark", "themeVariables": {"fontFamily": "Helvetica, Arial, sans-serif", "fontSize": "15px", "primaryColor": "#1F2937",
                   "primaryBorderColor": "#22D3EE", "primaryTextColor": "#F9FAFB", "lineColor": "#9CA3AF", "clusterBkg": "#111827", "clusterBorder": "#374151"}},
        "classdef": ["classDef cyan fill:#1F2937,stroke:#22D3EE,stroke-width:2px,color:#F9FAFB", "classDef pink fill:#1F2937,stroke:#F472B6,stroke-width:2px,color:#F9FAFB",
                     "classDef lime fill:#1F2937,stroke:#A3E635,stroke-width:2px,color:#F9FAFB"],
        "guide": "어두운 배경 슬라이드용: 진회색 채움에 네온 테두리(cyan/pink/lime). 글자 흰색.",
    },
    "UML-클래식": {
        "config": {"theme": "default", "themeVariables": {"fontFamily": "Helvetica, Arial, sans-serif", "fontSize": "13px", "actorBkg": "#FFFFFF",
                   "actorBorder": "#000000", "signalColor": "#000000", "noteBkgColor": "#FFF8DC", "noteBorderColor": "#8B8000"}},
        "classdef": [],
        "guide": "교과서 UML: 흰 박스 검은 선, 시퀀스는 activate/deactivate 와 Note 를 적극 사용.",
    },
}


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


GOAL = read(os.path.join(ROOT, "goal-prompt.md"))  # 요청마다 다시 읽지 않음


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


# ── LLM (이미지 첨부 가능) ───────────────────────────────────────────────
def _clean(out):
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
    out = re.sub(r"^```\w*\s*\n", "", out)
    out = re.sub(r"\n?```\s*$", "", out)
    return out.strip()


def openai_chat(system, messages, model, on_token=None, images=None):
    msgs = [dict(m) for m in messages]
    if images and msgs:
        msgs[-1]["content"] = [{"type": "text", "text": msgs[-1]["content"]}] + \
            [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}} for b in images]
    body = {"model": model, "stream": True, "temperature": 0.2, "messages": [{"role": "system", "content": system}, *msgs]}
    hdr = {"Content-Type": "application/json", **({"Authorization": f"Bearer {LLM_KEY}"} if LLM_KEY else {})}
    req = urllib.request.Request(LLM_BASE + "/chat/completions", json.dumps(body).encode(), hdr)
    buf = []
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                tok = (json.loads(line[5:])["choices"][0].get("delta") or {}).get("content") or ""
                if tok:
                    buf.append(tok)
                    if on_token:
                        on_token(tok)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
    return "".join(buf)


def ollama(system, messages, model, on_token=None, images=None):
    """Ollama /api/chat 스트리밍. images=[base64] 는 마지막 user 메시지에 붙는다. LLM_API=openai 면 OpenAI 호환."""
    if LLM_API == "openai":
        return openai_chat(system, messages, model, on_token, images)
    msgs = [dict(m) for m in messages]
    if images and msgs:
        msgs[-1]["images"] = images
    body = {"model": model, "stream": True, "think": False, "options": {"temperature": 0.2, "num_ctx": NUM_CTX},
            "messages": [{"role": "system", "content": system}, *msgs]}
    for attempt in (0, 1):
        try:
            req = urllib.request.Request(LLM_BASE + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
            buf = []
            with urllib.request.urlopen(req, timeout=3600) as r:
                for line in r:
                    if not line.strip():
                        continue
                    j = json.loads(line)
                    if "error" in j:
                        raise RuntimeError(j["error"])
                    tok = j.get("message", {}).get("content", "")
                    if tok:
                        buf.append(tok)
                        if on_token:
                            on_token(tok)
                    if j.get("done"):
                        break
            return "".join(buf)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if attempt == 0 and "think" in msg:
                body.pop("think")
                continue
            raise RuntimeError(f"Ollama HTTP {e.code}: {msg[:300]}")


def models():
    if LLM_API == "openai":
        req = urllib.request.Request(LLM_BASE + "/models", headers={"Authorization": f"Bearer {LLM_KEY}"} if LLM_KEY else {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return [m["id"] for m in json.load(r)["data"]]
    with urllib.request.urlopen(LLM_BASE + "/api/tags", timeout=10) as r:
        return [m["name"] for m in json.load(r)["models"]]


def prompt(section):
    """goal-prompt.md 의 `## <section>` 본문."""
    txt = GOAL
    m = re.search(rf"^## {re.escape(section)}\s*$(.*?)(?=^## |\Z)", txt, re.M | re.S)
    if not m:
        raise KeyError(section)
    return m.group(1).strip()


# ── 1) 읽기 ─────────────────────────────────────────────────────────────
def _json_block(s):
    s = _clean(s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("JSON 없음: " + s[:120])
    return json.loads(s[i:j + 1])


def normalize(r):
    """비전 출력 정리: id 부여·중복 제거, 모르는 방향은 '?'+uncertain, 없는 노드 참조 제거."""
    out = {"elements": [], "edges": [], "groups": [], "handwriting_notes": [], "guessed_type": "", "confidence_notes": []}
    seen = {}
    for i, e in enumerate(r.get("elements") or []):
        if not isinstance(e, dict):
            e = {"label": str(e)}
        label = str(e.get("label") or e.get("text") or "").strip() or f"항목{i+1}"
        eid = re.sub(r"[^A-Za-z0-9_]", "", str(e.get("id") or "")) or f"n{i+1}"
        if eid in seen or eid[0].isdigit():
            eid = f"n{i+1}"
        seen[eid] = label
        out["elements"].append({"id": eid, "label": label, "kind": str(e.get("kind") or "box").lower(), "uncertain": bool(e.get("uncertain"))})
    bylabel = {v.lower(): k for k, v in seen.items()}

    def ref(x):
        x = str(x or "").strip()
        return x if x in seen else bylabel.get(x.lower())
    for e in r.get("edges") or []:
        if not isinstance(e, dict):
            continue
        a, b = ref(e.get("from")), ref(e.get("to"))
        if not a or not b:
            out["confidence_notes"].append(f"연결 참조 불명: {e.get('from')} → {e.get('to')}")
            continue
        d = str(e.get("direction") or "->").strip()
        if d not in ("->", "<-", "<->", "--"):
            d = "?"
        out["edges"].append({"from": a, "to": b, "label": str(e.get("label") or "").strip(), "direction": d,
                             "uncertain": bool(e.get("uncertain")) or d == "?"})
    for g in r.get("groups") or []:
        if isinstance(g, dict):
            mem = [m for m in (ref(x) for x in (g.get("members") or [])) if m]
            if mem:
                out["groups"].append({"label": str(g.get("label") or "그룹"), "members": mem})
    out["handwriting_notes"] = [str(x) for x in (r.get("handwriting_notes") or [])]
    out["guessed_type"] = str(r.get("guessed_type") or "").lower()
    out["confidence_notes"] += [str(x) for x in (r.get("confidence_notes") or [])]
    return out


def read_sketch(image_b64, model=VISION):
    raw = ollama(prompt("읽기"), [{"role": "user", "content": "이 손그림 다이어그램을 JSON 으로 읽어라."}], model, images=[image_b64])
    return normalize(_json_block(raw)), raw


# ── 2) 질문 (불확실 항목만, 최대 3, 기본값 제공) ─────────────────────────
def questions(reading):
    """ponytail: 규칙 생성. 8B 급 텍스트 모델에 질문 생성을 맡기면 엉뚱한 질문이 섞여서, 불확실 플래그만 묻는다. 더 똑똑한 질문이 필요하면 LLM 로 승급."""
    qs = []
    names = {e["id"]: e["label"] for e in reading["elements"]}
    for i, e in enumerate(reading["edges"]):
        if e["direction"] == "?" or e["uncertain"]:
            qs.append({"key": f"edge:{i}", "q": f"'{names[e['from']]}' 와 '{names[e['to']]}' 사이 화살표 방향은?",
                       "options": ["->", "<-", "<->", "--"], "default": "->" if e["direction"] == "?" else e["direction"]})
    for e in reading["elements"]:
        if e["uncertain"]:
            qs.append({"key": f"elem:{e['id']}", "q": f"'{e['label']}' 로 읽었는데 맞나요? (종류: {e['kind']})", "default": e["label"]})
    return qs[:MAX_QUESTIONS]


def apply_answers(reading, answers):
    for k, v in (answers or {}).items():
        v = str(v).strip()
        if not v:
            continue
        kind, _, key = k.partition(":")
        if kind == "edge" and key.isdigit() and int(key) < len(reading["edges"]):
            reading["edges"][int(key)].update(direction=v if v in ("->", "<-", "<->", "--") else "->", uncertain=False)
        elif kind == "elem":
            for e in reading["elements"]:
                if e["id"] == key:
                    e.update(label=v, uncertain=False)
    return reading


def recommend(reading, mode):
    t = next((v for k, v in GUESS2TYPE.items() if k in reading.get("guessed_type", "")), None)
    if not t:
        t = "시퀀스" if any(e["kind"] == "actor" for e in reading["elements"]) else ("아키텍처" if reading["groups"] else "파이프라인")
    style = {"원본": "손그림-스케치", "단순화": "IEEE-모노", "인사이트": "논문-파스텔"}.get(mode, "논문-파스텔")
    why = f"비전 모델 추정 '{reading.get('guessed_type') or '없음'}' → {t}. 모드 '{mode}' 기본 스타일 {style}."
    return {"type": t, "style": style, "why": why}


# ── 3) 그리기 ────────────────────────────────────────────────────────────
def _yaml(d, ind=0):
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            out.append(" " * ind + f"{k}:")
            out.append(_yaml(v, ind + 2))
        else:
            out.append(" " * ind + f"{k}: " + (json.dumps(v, ensure_ascii=False) if isinstance(v, str) else json.dumps(v)))
    return "\n".join(out)


def frontmatter(style):
    return "---\nconfig:\n" + _yaml(STYLES[style]["config"], 2) + "\n---\n"


def strip_front(src):
    return re.sub(r"\A---\n.*?\n---\n", "", src, flags=re.S)


def decorate(src, style, dtype):
    """LLM 출력(선언부터)에 frontmatter 와 classDef 블록을 붙인다. classDef 는 flowchart/state 에만."""
    body = strip_front(_clean(src))
    body = re.sub(r"^\s*classDef .*$\n?", "", body, flags=re.M)  # LLM 이 쓴 classDef 는 프리셋으로 대체
    body = re.sub(r"(-->|<-->|---|-\.->|==>)\|\s*(\"\s*\")?\s*\|", r"\1", body)  # 빈 라벨 `-->| |` 제거
    head = body.strip().splitlines()[0] if body.strip() else ""
    defs = STYLES[style]["classdef"]
    if defs and head.startswith(("flowchart", "graph", "stateDiagram")):
        body = body.rstrip() + "\n" + "\n".join("  " + d for d in defs) + "\n"
    return frontmatter(style) + body


def sanity(src):
    lines = [l for l in strip_front(src).strip().splitlines() if l.strip() and not l.strip().startswith("%%")]
    if not lines:
        return "빈 출력"
    if not lines[0].strip().startswith(HEADS):
        return f"첫 줄이 다이어그램 선언이 아님: {lines[0][:40]!r}"
    for a, b in ("[]", "()", "{}"):
        if src.count(a) != src.count(b):
            return f"괄호 불일치 {a}{b}"
    if src.count('"') % 2:
        return "큰따옴표 홀수"
    return None


def reading_text(reading):
    names = {e["id"]: e["label"] for e in reading["elements"]}
    el = "\n".join(f"- {e['id']}: \"{e['label']}\" ({e['kind']})" for e in reading["elements"])
    ed = "\n".join(f"- {e['from']} {e['direction']} {e['to']}" + (f' : "{e["label"]}"' if e["label"] else "") for e in reading["edges"])
    gr = "\n".join(f"- {g['label']}: {', '.join(g['members'])}" for g in reading["groups"])
    notes = "\n".join(f"- {n}" for n in reading["handwriting_notes"])
    return f"[요소]\n{el}\n\n[연결]\n{ed}\n\n[그룹]\n{gr or '- 없음'}\n\n[손글씨 메모]\n{notes or '- 없음'}"


def draw(reading, mode, style, dtype, messages=None, model=MODEL, on_token=None, max_nodes=8):
    """최초 그리기(messages 없음) 또는 다듬기(messages 에 이전 대화). 반환 (mermaid, insight)."""
    style = style if style in STYLES else "논문-파스텔"
    dtype = dtype if dtype in TYPES else "자동"
    system = prompt("그리기") + "\n\n[스타일 지시]\n" + STYLES[style]["guide"] + \
        ("\n\n[classDef 이름 — 이것만 사용, classDef 선언은 쓰지 말 것: " + ", ".join(d.split()[1] for d in STYLES[style]["classdef"]) + "]" if STYLES[style]["classdef"] else "")
    decl = TYPES[dtype][0]
    modetxt = {"원본": "원본 그대로: 요소·연결을 하나도 빼거나 더하지 않는다.",
               "단순화": f"단순화: 핵심만 남겨 노드 {max_nodes}개 이하. 비슷한 요소는 합치고 세부 연결은 생략한다.",
               "인사이트": "인사이트 재구성: 그림이 말하려는 핵심 구조를 해석해 더 읽기 좋은 구조로 재배치한다(계층·흐름 정리, 이름 정돈). "
                           "Mermaid 뒤에 `=====` 한 줄을 두고 그 아래에 3~5문장 한국어로 '이 그림이 말하는 것'과 '무엇을 어떻게 재배치했는지'를 쓴다."}.get(mode, "")
    user = f"[모드] {modetxt}\n[유형] {decl + ' 로 그린다.' if decl else '내용에 맞는 유형을 고른다.'}\n\n" + reading_text(reading)
    msgs = [{"role": "user", "content": user}] + [dict(m) for m in (messages or [])]
    raw = _clean(ollama(system, msgs, model, on_token))
    src, _, insight = raw.partition("\n=====")
    return decorate(src, style, dtype), insight.strip()


def repair(src, error, model=MODEL):
    body = strip_front(src)
    style = next((s for s in STYLES if src.startswith(frontmatter(s))), None)
    fixed = _clean(ollama(prompt("그리기"), [{"role": "user", "content": f"[파싱 오류]\n{error}\n\n[소스]\n{body}"}], model))
    return decorate(fixed, style, "자동") if style else fixed


def tikz(src, reading, model=MODEL):
    return _clean(ollama(prompt("TikZ"), [{"role": "user", "content": f"[Mermaid]\n{strip_front(src)}\n\n{reading_text(reading)}"}], model))


# ── 저장 ────────────────────────────────────────────────────────────────
RUN_RE = r"\d{4}-\d{2}-\d{2}-[0-9a-f]{4}"


def save(bundle):
    rid = bundle.get("id")
    if not (rid and re.fullmatch(RUN_RE, rid)):  # 클라이언트가 준 id 는 형식 검증 (경로 탈출 방지)
        rid = f"{datetime.date.today()}-{secrets.token_hex(2)}"
    d = os.path.join(WS, rid)
    os.makedirs(d, exist_ok=True)
    img = bundle.pop("image_b64", None)
    if img:
        with open(os.path.join(d, "sketch.png"), "wb") as f:
            f.write(base64.b64decode(img))
    bundle.update(id=rid, ts=datetime.datetime.now().isoformat(timespec="seconds"))
    write(os.path.join(d, "bundle.json"), json.dumps(bundle, ensure_ascii=False, indent=1))
    if bundle.get("source"):
        write(os.path.join(d, "diagram.mmd"), bundle["source"])
    return rid


def list_runs():
    if not os.path.isdir(WS):
        return []
    out = []
    for n in sorted(os.listdir(WS), reverse=True)[:50]:
        p = os.path.join(WS, n, "bundle.json")
        if os.path.exists(p):
            try:
                j = json.load(open(p, encoding="utf-8"))
                out.append({"id": j["id"], "ts": j.get("ts"), "mode": j.get("mode"), "style": j.get("style"), "type": j.get("type"),
                            "head": (j.get("reading") or {}).get("elements", [{}])[:3] and ", ".join(e.get("label", "") for e in j["reading"]["elements"][:3])})
            except Exception:
                pass
    return out


# ── HTTP ───────────────────────────────────────────────────────────────
HTML = read(os.path.join(ROOT, "ui.html")) if os.path.exists(os.path.join(ROOT, "ui.html")) else "ui.html 없음"


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        if "/api/" in (a[0] if a else "") and "/api/runs" not in a[0] and "/api/models" not in a[0]:
            super().log_message(fmt, *a)

    def _send(self, body, ctype="application/json", code=200):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
            if self.path == "/api/models":
                return self._send({"models": models(), "text": MODEL, "vision": VISION})
            if self.path == "/api/presets":
                return self._send({"styles": {k: v["guide"] for k, v in STYLES.items()}, "types": {k: v[1] for k, v in TYPES.items()}})
            if self.path == "/api/runs":
                return self._send(list_runs())
            m = re.fullmatch(rf"/api/runs/({RUN_RE})(/sketch\.png)?", self.path)
            if m:
                if m.group(2):
                    with open(os.path.join(WS, m.group(1), "sketch.png"), "rb") as f:
                        return self._send(f.read(), "image/png")
                return self._send(read(os.path.join(WS, m.group(1), "bundle.json")).encode())
            if self.path == "/static/mermaid.min.js":
                with open(os.path.join(ROOT, "static", "mermaid.min.js"), "rb") as f:
                    return self._send(f.read(), "application/javascript")
            self._send(HTML.encode(), "text/html; charset=utf-8")
        except FileNotFoundError:
            self._send({"error": "없음"}, code=404)
        except Exception as e:
            self._send({"error": f"{type(e).__name__}: {e}"}, code=500)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            if self.path == "/api/read":
                reading, raw = read_sketch(req["image_b64"], req.get("vision_model") or VISION)
                return self._send({"reading": reading, "raw": raw})
            if self.path == "/api/plan":
                reading = apply_answers(req["reading"], req.get("answers"))
                return self._send({"reading": reading, "questions": questions(reading) if not req.get("answers") else [],
                                   "recommend": recommend(reading, req.get("mode") or "원본")})
            if self.path == "/api/repair":
                src = repair(req.get("source", ""), req.get("error", ""), req.get("model") or MODEL)
                return self._send({"source": src, "sanity": sanity(src)})
            if self.path == "/api/tikz":
                return self._send({"tikz": tikz(req.get("source", ""), req.get("reading") or normalize({}), req.get("model") or MODEL)})
            if self.path == "/api/save":
                return self._send({"id": save(req)})
            if self.path != "/api/draw":
                return self._send({"error": "없음"}, code=404)
        except Exception as e:
            return self._send({"error": f"{type(e).__name__}: {e}"}, code=500)
        # /api/draw — SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(ev):
            self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
        try:
            src, insight = draw(req["reading"], req.get("mode") or "원본", req.get("style") or "논문-파스텔", req.get("type") or "자동",
                                req.get("messages"), req.get("model") or MODEL, on_token=lambda t: emit({"token": t}),
                                max_nodes=int(req.get("max_nodes") or 8))
            emit({"done": {"source": src, "insight": insight, "sanity": sanity(src)}})
        except Exception as e:
            emit({"error": f"{type(e).__name__}: {e}"})


def cli(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="app.py --cli")
    ap.add_argument("image")
    ap.add_argument("--mode", default="원본", choices=["원본", "단순화", "인사이트"])
    ap.add_argument("--style", default="논문-파스텔", choices=list(STYLES))
    ap.add_argument("--type", default="자동", choices=list(TYPES))
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args(argv)
    with open(a.image, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    print("[읽기] 비전 모델", VISION, file=sys.stderr)
    reading, _ = read_sketch(b64)
    qs = questions(reading)
    reading = apply_answers(reading, {q["key"]: q["default"] for q in qs})  # 비대화: 기본값
    print(f"[읽기] 요소 {len(reading['elements'])} 연결 {len(reading['edges'])} 질문 {len(qs)}(기본값 적용) → {recommend(reading, a.mode)['why']}", file=sys.stderr)
    src, insight = draw(reading, a.mode, a.style, a.type)
    bad = sanity(src)
    if bad:
        print(f"[경고] {bad}", file=sys.stderr)
    print(src)
    if insight:
        print("\n=====\n" + insight)
    if a.save:
        print("[저장]", save({"image_b64": b64, "reading": reading, "mode": a.mode, "style": a.style, "type": a.type, "source": src, "insight": insight}), file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.exit(cli(sys.argv[2:]))
    print(f"sketch local → http://localhost:{PORT}  (text={MODEL}, vision={VISION}, llm={LLM_API} {LLM_BASE})")
    ThreadingHTTPServer(("", PORT), H).serve_forever()
