#!/usr/bin/env python3
"""지원서 입력 결과 대조: 입력 계획(form_plan.yaml) ↔ 화면 점검 결과(inspect.js 출력).

사용:
  python3 form_check.py <지원폴더>/form_plan.yaml --show                       # 기대값 목록만 보기
  python3 form_check.py <지원폴더>/form_plan.yaml <inspect출력.txt> [--hashes "<hashes.js 출력>"]

form_plan.yaml
  fields:   # 위에서부터 화면 순서대로. label 은 화면 라벨의 일부 문자열, nth 는 같은 라벨이 여러 번일 때 몇 번째(1부터)
    - {label: 이름, kind: text, value: 홍길동}
    - {label: 성별, kind: select, value: 남성}               # select: 드롭다운·날짜·월 버튼의 표시 글자
    - {label: 장애여부, kind: radio, value: 비대상}
    - {label: 관심 분야, kind: checks, value: [Data pipeline]}
    - {label: 지원 동기, kind: text, text_from: "final_coverletter.md#[웹 답변] 지원 동기"}
    - {label: 이력서, kind: file, file: 이력서.pdf}           # 지원 폴더 기준 경로. 이름과 바이트 크기를 대조
  consents:  # 동의 체크박스 (라벨 일부 → 체크 여부)
    - {label: 필수항목, value: true}
  testbed: true   # 로컬 테스트 양식이면 제출됨·위험 버튼·화면/저장 불일치까지 검사

종료 코드: 0 = 모두 일치, 1 = 불일치 있음
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import yaml


def clean(s: str) -> str:  # inspect.js 의 clean() 과 같아야 한다
    s = re.sub(r"https?://", "", str(s))
    s = s.replace("@", "(at)")
    s = re.sub(r"[?=&]", "_", s)
    s = re.sub(r"([A-Za-z0-9-])\.(?=[A-Za-z]{2,})", r"\1[.]", s)
    return re.sub(r"\s+", " ", s).strip()


def short(s: str) -> str:
    return s[:20] + "…" if len(s) > 40 else s


def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def section_text(path: Path, heading: str | None) -> str:
    text = path.read_text(encoding="utf-8").split("<!-- HUMANIZE-SUMMARY")[0]
    if not heading:
        return text.strip()
    m = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, flags=re.M)
    if not m:
        sys.exit(f"{path.name} 에 '{heading}' 소제목이 없습니다")
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, flags=re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def expected(plan: dict, base: Path) -> list[dict]:
    exp = []
    for f in plan.get("fields", []):
        e = {"label": f["label"], "kind": f["kind"], "nth": f.get("nth", 1)}
        if f["kind"] == "text":
            if "text_from" in f:
                file, _, head = f["text_from"].partition("#")
                v = section_text(base / file, head or None)
            else:
                v = str(f["value"])
            e.update(value=v, len=len(v), hash=sha16(v))
        elif f["kind"] == "checks":
            e["value"] = sorted(f["value"] or [])
        elif f["kind"] == "file":
            p = base / f["file"]
            e["value"] = f"{p.name} {p.stat().st_size}"
        else:
            e["value"] = str(f["value"])
        exp.append(e)
    for c in plan.get("consents", []):
        exp.append({"label": c["label"], "kind": "consent", "nth": 1, "value": str(bool(c["value"])).lower()})
    return exp


def parse_rows(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.rstrip().rstrip("|").split("|")]
        if len(parts) < 4:
            continue
        rows.append({"seq": parts[0].lstrip("#"), "label": parts[1], "kind": parts[2], "value": parts[3],
                     "len": parts[4] if len(parts) > 4 else ""})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("actual", nargs="?")
    ap.add_argument("--hashes", default="", help="hashes.js 출력 문자열 또는 그 파일 경로")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    plan_path = Path(args.plan).resolve()
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    exp = expected(plan, plan_path.parent)
    if args.show or not args.actual:
        for e in exp:
            v = e["value"] if e["kind"] != "text" else f'{short(clean(e["value"]))} ({e["len"]}자, {e["hash"]})'
            print(f'{e["label"]} [{e["kind"]}#{e["nth"]}] = {v}')
        return 0

    rows = parse_rows(Path(args.actual).read_text(encoding="utf-8"))
    hs = args.hashes
    if hs and Path(hs).exists():
        hs = Path(hs).read_text(encoding="utf-8")
    toks = hs.split()
    hashes = dict(zip(toks[::2], toks[1::2]))

    fails = 0
    for e in exp:
        cands = [r for r in rows if e["label"] in r["label"] and r["kind"] == e["kind"]]
        if len(cands) < e["nth"]:
            print(f'✕ {e["label"]} [{e["kind"]}#{e["nth"]}] 화면에서 찾지 못함')
            fails += 1
            continue
        r = cands[e["nth"] - 1]
        ok, note = True, ""
        if e["kind"] == "text":
            if str(e["len"]) != r["len"]:
                ok, note = False, f'길이 {r["len"]} ≠ {e["len"]}'
            elif e["len"] <= 40:
                ok = r["value"] == clean(e["value"])
                note = "" if ok else f'값 "{r["value"]}" ≠ "{clean(e["value"])}"'
            elif r["seq"] in hashes:
                ok = hashes[r["seq"]] == e["hash"]
                note = "해시 일치" if ok else "해시 다름"
            else:
                ok = r["value"] == short(clean(e["value"]))
                note = "앞부분·길이 일치 (해시 미확인)" if ok else "앞부분 다름"
        elif e["kind"] == "checks":
            got = sorted([x for x in r["value"].split(";") if x])
            ok = got == e["value"]
            note = "" if ok else f"{got} ≠ {e['value']}"
        else:
            ok = clean(r["value"]) == clean(e["value"])
            note = "" if ok else f'"{r["value"]}" ≠ "{e["value"]}"'
        print(f'{"○" if ok else "✕"} {e["label"]} [{e["kind"]}#{e["nth"]}] {note}'.rstrip())
        fails += not ok

    err = next((r for r in rows if r["seq"] == "errors"), None)
    if err and err["value"] not in ("0", ""):
        print(f'✕ 화면의 필수 입력 오류 표시 {err["value"]}개')
        fails += 1
    if plan.get("testbed"):
        tb = {r["label"]: r["value"] for r in rows if r["seq"] == "testbed"}
        checks = [("제출됨", "false"), ("누르면 안 되는 버튼 클릭", "0"), ("화면·저장 불일치", "")]
        for k, want in checks:
            got = tb.get(k)
            ok = got == want
            print(f'{"○" if ok else "✕"} [testbed] {k}: {got!r}' + ("" if ok else f" (기대 {want!r})"))
            fails += not ok
        if tb.get("무시된 클릭") not in (None, "0"):
            print(f'  참고: 열린 목록 때문에 무시된 클릭 {tb["무시된 클릭"]}번 — 해당 칸을 다시 확인했는지 볼 것')
    print("\n결과:", "모두 일치" if not fails else f"불일치 {fails}건")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
