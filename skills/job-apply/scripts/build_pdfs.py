#!/usr/bin/env python3
"""지원 폴더의 PDF 를 한 번에 만들고 자동 검증한다.

사용: python3 build_pdfs.py <지원폴더> [--forbid 단어…] [--allow 단어…] [--theme 프리셋] [--only resume_en …]

- resume*.yaml → 이력서, letter*.yaml → 자기소개서·경력기술서 (파일마다 output 이름으로 PDF 하나)
- 쪽수 상한: yaml 의 max_pages, 없으면 layout: compact 는 1쪽, 나머지는 2쪽
- 금지어: 같은 상위 폴더의 다른 지원 폴더(YYYY-MM-DD_회사_직무)에서 회사명을 모으고 --forbid 를 더한다.
  이번 회사와 --allow 로 준 단어는 뺀다.
- 검증: pdf_check 의 모든 항목 (+ 이력서는 HTML 대조, 자기소개서는 원문 대조, lang: en 이면 한글 잔존)
- 미리보기: <지원폴더>/_build/<yaml 이름>.png — 자동 판정 뒤에 Read 로 열어 직접 본다
- 결과: <지원폴더>/_build/pdf_check.json, 종료 코드 0 = 모두 통과
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

import pdf_check  # noqa: E402
import render_letter  # noqa: E402
import render_resume  # noqa: E402
from pdf_base import render, set_theme  # noqa: E402

APP_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}_([^_]+)_")


def auto_forbid(folder: Path) -> tuple[str | None, list[str]]:
    m = APP_DIR.match(folder.name)
    current = m.group(1) if m else None
    others = set()
    for d in folder.parent.iterdir():
        mm = APP_DIR.match(d.name)
        # 이번 회사명 안에 든 짧은 이름('그린데이터' 지원의 '그린')은 이번 회사명과 가릴 수 없어 뺀다
        if d.is_dir() and d != folder and mm and mm.group(1) != current and not (current and mm.group(1) in current):
            others.add(mm.group(1))
    return current, sorted(others)


def jobs(folder: Path, only: list[str]) -> list[tuple[str, Path]]:
    out = [("resume", p) for p in sorted(folder.glob("resume*.yaml"))]
    out += [("letter", p) for p in sorted(folder.glob("letter*.yaml"))]
    return [(k, p) for k, p in out if not only or p.stem in only]


def build_one(kind: str, src: Path, forbid: list[str]) -> dict:
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    build = src.parent / "_build"
    pdf = src.parent / data["output"]
    if kind == "resume":
        html_text = render_resume.build_html(data)
    else:
        md = (src.parent / data["source"]).read_text(encoding="utf-8")
        html_text = render_letter.build_html(data, md)
    render(html_text, pdf, build, f"{src.stem}.html")
    max_pages = data.get("max_pages") or (1 if data.get("layout") == "compact" else 2)
    argv = [str(pdf), "--max-pages", str(max_pages), "--html", str(build / f"{src.stem}.html"),
            "--lang", data.get("lang", "ko"), "--sheet", str(build / f"{src.stem}.png")]
    if kind == "letter":
        argv += ["--source", str(src.parent / data["source"])]
    if forbid:
        argv += ["--forbid", *forbid]
    r = pdf_check.check(pdf_check.build_parser().parse_args(argv))
    r["yaml"] = src.name
    r["max_pages"] = max_pages
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--forbid", nargs="*", default=[])
    ap.add_argument("--allow", nargs="*", default=[])
    ap.add_argument("--theme")
    ap.add_argument("--only", nargs="*", default=[], help="yaml 파일 이름(확장자 제외)만 골라서")
    args = ap.parse_args()
    set_theme(args.theme)

    folder = Path(args.folder).resolve()
    todo = jobs(folder, args.only)
    if not todo:
        sys.exit(f"{folder} 에 resume*.yaml 이나 letter*.yaml 이 없습니다 (형식: references/pdf.md)")
    current, others = auto_forbid(folder)
    forbid = sorted((set(others) | set(args.forbid)) - set(args.allow) - {current, ""})
    print(f"금지어 {len(forbid)}개: {', '.join(forbid) if forbid else '없음'}" + (f"  (이번 회사: {current})" if current else ""))

    results = []
    for kind, src in todo:
        r = build_one(kind, src, forbid)
        results.append(r)
        i = r["info"]
        extra = []
        if "source" in i:
            extra.append(f"원문 누락 {i['source']['missing']}/{i['source']['sentences']}")
        if "html" in i:
            extra.append(f"HTML 누락 {i['html']['missing']}/{i['html']['chunks']}")
        fill = f", 마지막 쪽 {i['last_page_fill']:.0%}" if "last_page_fill" in i else ""
        print(f"\n[{'통과' if r['ok'] else '실패'}] {Path(r['pdf']).name}  ({src.name}) — {i['pages']}/{r['max_pages']}쪽{fill}, {', '.join(extra)}")
        for w in r["warns"]:
            print("  경고:", w)
        for f in r["fails"]:
            print("  실패:", f)
        print("  미리보기:", i["sheet"])

    out = folder / "_build" / "pdf_check.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = sum(not r["ok"] for r in results)
    print(f"\n결과: {'모두 통과' if not bad else f'실패 {bad}개'} ({out})")
    print("다음: 미리보기 PNG 를 Read 로 열어 자동 판정이 못 보는 것(어색한 줄바꿈, 빈 공간, 강조 과다)을 확인한다.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
