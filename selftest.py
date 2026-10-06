#!/usr/bin/env python3
"""LLM 없이 검증: 비전 JSON 정규화 → 질문(불확실 항목만, ≤3) → 답변 적용 → 추천 → 프리셋 주입 → sanity/repair → CLI → ui 로컬 자산.
python3 selftest.py"""
import json, os, re, subprocess, sys
import app

calls = []
def fake(system, messages, model, on_token=None, images=None):
    calls.append({"system": system, "messages": messages, "images": images})
    out = FAKE
    if on_token: on_token(out)
    return out
app.ollama = fake

# 1) 읽기: 코드펜스 섞인 JSON, 라벨로 참조한 edge, 모르는 방향, 없는 노드 참조
FAKE = '```json\n' + json.dumps({"elements": [{"label": "사용자", "kind": "actor"}, {"id": "n2", "label": "웹 서버"}, {"id": "n2", "label": "DB", "kind": "db", "uncertain": True}],
    "edges": [{"from": "사용자", "to": "n2", "label": "HTTP"}, {"from": "n2", "to": "n3", "direction": "both"}, {"from": "n2", "to": "유령"}],
    "groups": [{"label": "백엔드", "members": ["n2", "n3", "x"]}], "handwriting_notes": ["캐시 미정"], "guessed_type": "architecture"}, ensure_ascii=False) + '\n```'
r, raw = app.read_sketch("AAAA")
assert calls[-1]["images"] == ["AAAA"] and "JSON" in calls[-1]["system"]
ids = [e["id"] for e in r["elements"]]
assert ids == ["n1", "n2", "n3"], ids                       # 중복 id → 재부여
assert r["edges"][0]["from"] == "n1" and r["edges"][0]["direction"] == "->" and not r["edges"][0]["uncertain"]
assert r["edges"][1]["direction"] == "?" and r["edges"][1]["uncertain"]  # 모르는 방향
assert len(r["edges"]) == 2 and any("유령" in n for n in r["confidence_notes"])
assert r["groups"][0]["members"] == ["n2", "n3"]

# 2) 질문은 불확실 항목만, 기본값 포함, 최대 3
qs = app.questions(r)
assert [q["key"] for q in qs] == ["edge:1", "elem:n3"], qs
assert qs[0]["default"] == "->" and qs[1]["default"] == "DB"
r2 = app.apply_answers(json.loads(json.dumps(r)), {"edge:1": "<->", "elem:n3": "DB(Postgres)"})
assert r2["edges"][1]["direction"] == "<->" and not r2["edges"][1]["uncertain"] and r2["elements"][2]["label"] == "DB(Postgres)"
assert app.questions(r2) == []
big = {"elements": [{"label": f"x{i}", "uncertain": True} for i in range(6)], "edges": []}
assert len(app.questions(app.normalize(big))) == app.MAX_QUESTIONS

# 3) 추천
rec = app.recommend(r2, "단순화"); assert rec["type"] == "아키텍처" and rec["style"] == "IEEE-모노"
assert app.recommend(app.normalize({"elements": [{"label": "a", "kind": "actor"}], "guessed_type": ""}), "원본")["type"] == "시퀀스"

# 4) 그리기: 프리셋 frontmatter + classDef 주입, LLM 이 쓴 classDef 는 제거, 인사이트 분리, 모드/스타일 지시 전달
FAKE = '<think>..</think>```mermaid\nflowchart TB\n  n1["사용자"] --> n2["웹 서버"]\n  classDef foo fill:#000\n  class n1 input\n```\n=====\n핵심은 웹 서버 중심 구조.'
src, ins = app.draw(r2, "인사이트", "논문-파스텔", "아키텍처")
assert src.startswith("---\nconfig:\n  theme: \"base\"") and "look" not in src
assert "classDef module fill:#DCEBFA" in src and "classDef foo" not in src and ins == "핵심은 웹 서버 중심 구조."
assert "flowchart TB 로 그린다" in calls[-1]["messages"][0]["content"] and "인사이트 재구성" in calls[-1]["messages"][0]["content"]
assert "input, module, output, store, note" in calls[-1]["system"] and 'n3: "DB(Postgres)" (db)' in calls[-1]["messages"][0]["content"]
assert app.sanity(src) is None
src2, _ = app.draw(r2, "원본", "손그림-스케치", "자동")
assert 'look: "handDrawn"' in src2 and "classDef" not in src2 and "[classDef 이름" not in calls[-1]["system"]
FAKE = 'sequenceDiagram\n  participant n1 as "사용자"\n  n1->>n2: HTTP'
src3, _ = app.draw(r2, "원본", "IEEE-모노", "시퀀스"); assert "classDef" not in src3 and 'theme: "neutral"' in src3  # 시퀀스엔 classDef 없음

assert app.decorate('flowchart TB\n  n1["a"] -->| | n2["b"]', "IEEE-모노", "아키텍처").count('-->| |') == 0  # 빈 라벨 제거

# 5) sanity / repair (프리셋 유지)
bad = app.decorate('flowchart TB\n  n1["a" --> n2["b"]', "Distill-블루오렌지", "아키텍처")
assert "괄호" in app.sanity(bad)
FAKE = 'flowchart TB\n  n1["a"] --> n2["b"]'
fixed = app.repair(bad, "Parse error")
assert app.sanity(fixed) is None and "classDef blue" in fixed and "[파싱 오류]" in calls[-1]["messages"][0]["content"]

# 6) TikZ, 저장/목록
FAKE = '```latex\n\\tikzset{}\n\\begin{tikzpicture}\\node[box](n1){a};\\end{tikzpicture}\n```'
assert app.tikz(fixed, r2).startswith("\\tikzset")
rid = app.save({"image_b64": "iVBORw0KGgo=", "reading": r2, "mode": "원본", "style": "IEEE-모노", "type": "아키텍처", "source": fixed})
run = next(x for x in app.list_runs() if x["id"] == rid)  # 동시 실행과 무관하게
assert os.path.exists(os.path.join(app.WS, rid, "sketch.png")) and "사용자" in run["head"]

# 7) CLI 파서 (LLM 호출 전 인자 검사만), ui.html 로컬 자산만
rr = subprocess.run([sys.executable, "app.py", "--cli", "sample/sketch1.png", "--mode", "엉뚱"], capture_output=True, text=True, cwd=app.ROOT)
assert rr.returncode == 2 and "invalid choice" in rr.stderr
ui = app.read(os.path.join(app.ROOT, "ui.html"))
assert not re.search(r'<(script|link)[^>]+(src|href)="https?://', ui) and "https://" not in ui
assert os.path.exists(os.path.join(app.ROOT, "static", "mermaid.min.js"))
for s in app.STYLES: app.frontmatter(s)  # 모든 프리셋 YAML 생성
# 저작권 표기: 서버가 화면에 붙이는 코드가 있어야 한다 (LICENSE·NOTICE)
_src = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "app.py"), encoding="utf-8").read()
assert "wqkgMjAyNiBnZ2dnODY1NyDCtyBkb25nanVraW0uZGV2QGdtYWlsLmNvbQ==" in _src and "signed(" in _src and "X-Author" in _src, "저작권 표기 누락"

print("selftest OK — 프리셋", len(app.STYLES), "유형", len(app.TYPES))
