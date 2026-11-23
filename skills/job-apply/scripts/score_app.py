#!/usr/bin/env python3
"""지원 결과물 채점 — 지원 폴더 하나를 규칙으로 검사해 점수를 낸다. 모델 호출 없음.

사용:
  python3 score_app.py <지원폴더>                     # 사용자 데이터의 rules.yaml 기준
  python3 score_app.py <지원폴더> [<지원폴더> …] --rules 다른/rules.yaml
  python3 score_app.py <지원폴더> --json 결과.json

항목 (통과 / 실패 / 확인 / 해당 없음). 점수 = 통과 ÷ (통과 + 실패) × 100. 확인은 점수에 넣지 않고 사람이 본다.
  필수 파일     final_coverletter.md, evidence.md, status.md
  글자 수       '## [웹 답변]' 문항이 <!-- limit --> 를 넘지 않음 (count.py 기준)
  문체          style_check.py 의 error 0 (경고 수는 함께 보여 준다)
  PDF           폴더에 PDF 가 있으면 _build/pdf_check.json 이 있고 모두 통과, PDF 보다 나중에 만든 결과
  다른 회사명   같은 상위 폴더의 다른 지원 폴더 회사명이 제출 글(final_coverletter.md, resume·letter yaml)에 없음
  어학 금지     rules.yaml language_scores 에서 never 인 시험 이름이 제출 글에 없음
  남은 표시     TODO, TBD, XXX, ○○, {{ }}, [회사명], (미확인), 확인 필요 같은 작업 표시가 제출 글에 없음
  근거          evidence.md 표에 채운 줄이 3개 이상 (내용이 맞는지는 사람이 본다)
  윤문 기록     final_coverletter.md 의 HUMANIZE-SUMMARY, 또는 status.md·application.md 에 경로(light/standard/heavy)와
                변경률(% 또는 verify_gates 결과)을 적은 줄. '윤문: 건너뜀(이유)'만 있으면 확인으로 둔다
  확인 (점수 밖) rules.yaml exclude_from_resume_and_letter·never_claim_without_new_evidence 의 낱말이 제출 글에 나오면
                 문맥을 사람이 본다 ("Kubernetes 는 경험이 없지만"은 괜찮다)

종료 코드: 0 = 실패 없음, 2 = 실패 있음, 1 = 폴더가 없음
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

import count  # noqa: E402
import style_check  # noqa: E402

APP_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}_([^_]+)_")
PLACEHOLDER = re.compile(r"TODO|TBD|XXX|○○|\{\{[^}]*\}\}|\[회사명\]|\[직무명\]|\(미확인\)|확인\s*필요|추후\s*기재", re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def submitted_texts(folder: Path) -> dict[str, str]:
    """제출하는 글: final_coverletter.md 본문(주석 제외)과 resume·letter yaml 의 글 값."""
    out: dict[str, str] = {}
    final = folder / "final_coverletter.md"
    if final.exists():
        out[final.name] = COMMENT.sub("", final.read_text(encoding="utf-8").split("<!-- HUMANIZE-SUMMARY")[0])
    for p in sorted(folder.glob("resume*.yaml")) + sorted(folder.glob("letter*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        vals: list[str] = []

        def walk(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    if str(k) not in style_check.NOT_PROSE:
                        walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)
            elif isinstance(v, str):
                vals.append(v)
        walk(data)
        out[p.name] = "\n".join(vals)
    return out


def find_terms(texts: dict[str, str], terms: list[str], longer: list[str] | None = None) -> list[str]:
    """terms 가 나온 곳. longer 에 든 더 긴 이름(예: 'TOEIC Speaking')의 일부로 나온 것은 뺀다."""
    hits = []
    for name, text in texts.items():
        for t in terms:
            for m in re.finditer(re.escape(t), text):
                rest = text[m.start():]
                if any(lg != t and rest.startswith(lg) for lg in longer or []):
                    continue
                hits.append(f"{name}: '{t}' ({text[max(0, m.start() - 12):m.end() + 12].strip()})".replace("\n", " "))
                break
    return hits


def keyword(item) -> str:
    """rules.yaml 목록 항목의 첫 낱말 (예: 'Kubernetes, GPU·CUDA' → 'Kubernetes')."""
    s = item if isinstance(item, str) else str((item or {}).get("name") or (item or {}).get("topic") or "")
    m = re.match(r"\s*([^\s,(（—–·/]+)", s)
    return m.group(1) if m and len(m.group(1)) >= 3 else ""


def check_folder(folder: Path, rules: dict) -> list[dict]:
    res: list[dict] = []

    def add(name, status, detail=""):
        res.append({"item": name, "status": status, "detail": detail})

    final = folder / "final_coverletter.md"
    missing = [n for n in ("final_coverletter.md", "evidence.md", "status.md") if not (folder / n).exists()]
    add("필수 파일", "실패" if missing else "통과", "없음: " + ", ".join(missing) if missing else "")

    # 글자 수
    if final.exists():
        over, total, nolimit = [], 0, 0
        for title, body, limit in count.parse_md(final.read_text(encoding="utf-8")):
            total += 1
            if not limit:
                nolimit += 1
                continue
            n, unit = limit
            used = count.stats(body)[unit]
            if used > n:
                over.append(f"{title} {used}/{n}")
        if total:
            note = f"{total}문항" + (f", 제한 표시 없음 {nolimit}" if nolimit else "")
            add("글자 수", "실패" if over else "통과", "; ".join(over) or note)
        else:
            add("글자 수", "해당 없음", "'## [웹 답변]' 문항 없음")
    else:
        add("글자 수", "해당 없음")

    # 문체
    files = [p for p in [final, *sorted(folder.glob("resume*.yaml")), *sorted(folder.glob("letter*.yaml"))] if p.exists()]
    if files:
        style = dict(style_check.DEFAULTS)
        style.update({k: v for k, v in (rules.get("style") or {}).items() if v is not None})
        c = style_check.Checker(style)
        for p in files:
            text = p.read_text(encoding="utf-8")
            if p.suffix in (".yaml", ".yml"):
                c.yaml_values(str(p), yaml.safe_load(text) or {})
            else:
                c.md(str(p), text)
        detail = f"오류 {len(c.errors)}, 경고 {len(c.warns)}" + (f" — {c.errors[0][:80]}" if c.errors else "")
        add("문체", "실패" if c.errors else "통과", detail)
    else:
        add("문체", "해당 없음")

    # PDF
    pdfs = [p for p in folder.glob("*.pdf")]
    if pdfs:
        rep = folder / "_build" / "pdf_check.json"
        if not rep.exists():
            add("PDF", "실패", f"PDF {len(pdfs)}개, _build/pdf_check.json 없음 → build_pdfs.py 나 pdf_check.py --json")
        else:
            try:
                data = json.loads(rep.read_text(encoding="utf-8"))
            except ValueError:
                data = []
            rows = data if isinstance(data, list) else [data]
            bad = [Path(r.get("pdf", "?")).name for r in rows if not r.get("ok")]
            checked = {Path(r.get("pdf", "")).name for r in rows}
            stale = [p.name for p in pdfs if p.name in checked and p.stat().st_mtime > rep.stat().st_mtime + 1]
            unchecked = [p.name for p in pdfs if p.name not in checked]
            if bad or stale:
                add("PDF", "실패", "; ".join([f"실패: {', '.join(bad)}"] * bool(bad) + [f"검사 뒤 바뀜: {', '.join(stale)}"] * bool(stale)))
            else:
                add("PDF", "통과", f"{len(rows)}개 통과" + (f", 검사 기록 없는 첨부 {len(unchecked)}개(포트폴리오 등)" if unchecked else ""))
    else:
        add("PDF", "해당 없음")

    texts = submitted_texts(folder)

    # 다른 회사명 (이번 회사명 안에 든 짧은 이름은 빼고 찾는다: '그린데이터' 지원의 '그린')
    m = APP_DIR.match(folder.name)
    current = m.group(1) if m else None
    others = sorted({mm.group(1) for d in folder.parent.iterdir()
                     if d.is_dir() and d != folder and (mm := APP_DIR.match(d.name)) and mm.group(1) != current})
    if texts and others:
        masked = {n: t.replace(current, " " * len(current)) if current else t for n, t in texts.items()}
        hits = find_terms(masked, others)
        add("다른 회사명", "실패" if hits else "통과", "; ".join(hits) or f"{len(others)}개 회사명 검사")
    else:
        add("다른 회사명", "해당 없음", "비교할 다른 지원 폴더 없음" if texts else "")

    # 어학 금지
    scores = rules.get("language_scores") or {}
    never = [k for k, v in scores.items() if str(v) == "never"]
    if texts and never:
        hits = find_terms(texts, never, longer=list(scores))
        add("어학 금지", "실패" if hits else "통과", "; ".join(hits) or ", ".join(never))
    else:
        add("어학 금지", "해당 없음")

    # 남은 표시
    if texts:
        hits = [f"{n}: '{mm.group(0)}'" for n, t in texts.items() for mm in [PLACEHOLDER.search(t)] if mm]
        add("남은 표시", "실패" if hits else "통과", "; ".join(hits))

    # 근거
    ev = folder / "evidence.md"
    if ev.exists():
        n, prev_sep = 0, False
        lines = ev.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            is_header = bool(re.fullmatch(r"\|?[\s:|-]+\|?", nxt)) and "-" in nxt
            if not is_header and sum(bool(c) for c in cells) >= 2:
                n += 1
        add("근거", "통과" if n >= 3 else "실패", f"채운 줄 {n}개")
    else:
        add("근거", "해당 없음")

    # 윤문 기록
    if final.exists():
        blob = final.read_text(encoding="utf-8")
        notes = "\n".join((folder / n).read_text(encoding="utf-8") for n in ("status.md", "application.md") if (folder / n).exists())
        lines = notes.splitlines()
        done = "HUMANIZE-SUMMARY" in blob or any(  # 템플릿 줄 '(경로 light/standard/heavy, 변경률 …)'은 빼고 본다
            re.search(r"light|standard|heavy", ln) and "light/standard/heavy" not in ln
            and re.search(r"\d+(\.\d+)?\s*%|verify_gates[^\n]*\d|exit\s*\d", ln) for ln in lines)
        skipped = next((ln.strip() for ln in lines if re.search(r"윤문\s*:", ln) and re.search(r"건너뜀|건너뛰|생략", ln)), "")
        if done:
            add("윤문 기록", "통과")
        elif skipped:
            add("윤문 기록", "확인", f"건너뛴 이유를 본다: {skipped[:80]}")
        else:
            add("윤문 기록", "실패", "HUMANIZE-SUMMARY 도, status.md·application.md 에 경로와 변경률도 없음")

    # 확인 (점수 밖)
    words = [w for w in map(keyword, (rules.get("exclude_from_resume_and_letter") or [])
                            + (rules.get("never_claim_without_new_evidence") or [])) if w]
    if texts and words:
        hits = find_terms(texts, words)
        if hits:
            add("확인: 빼기로 한 항목 언급", "확인", "; ".join(hits))
    return res


def score_of(res: list[dict]) -> int | None:
    p = sum(r["status"] == "통과" for r in res)
    f = sum(r["status"] == "실패" for r in res)
    return round(100 * p / (p + f)) if p + f else None


def main() -> int:
    ap = argparse.ArgumentParser(description="지원 결과물 채점")
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--rules", help="rules.yaml 경로 (기본: 사용자 데이터 폴더)")
    ap.add_argument("--json", help="결과를 이 파일에 JSON 으로 쓴다")
    args = ap.parse_args()
    if args.rules:
        rules = yaml.safe_load(Path(args.rules).read_text(encoding="utf-8")) or {}
    else:
        from config import rules as user_rules
        rules = user_rules()
    out, failed = [], False
    for f in args.folders:
        folder = Path(f).expanduser().resolve()
        if not folder.is_dir():
            print(f"폴더가 없습니다: {folder}")
            return 1
        res = check_folder(folder, rules)
        sc = score_of(res)
        failed |= any(r["status"] == "실패" for r in res)
        out.append({"folder": str(folder), "score": sc, "items": res})
        print(f"■ {folder.name}  점수 {sc if sc is not None else '-'}")
        for r in res:
            mark = {"통과": "✓", "실패": "✗", "확인": "?", "해당 없음": "·"}[r["status"]]
            print(f"  {mark} {r['item']}" + (f" — {r['detail']}" if r["detail"] else ""))
    if len(out) > 1:
        vals = [o["score"] for o in out if o["score"] is not None]
        print(f"\n{len(out)}개 폴더 평균 {sum(vals) / len(vals):.0f}" if vals else "")
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON: {args.json}")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
