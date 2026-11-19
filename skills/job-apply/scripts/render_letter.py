#!/usr/bin/env python3
"""자기소개서·경력기술서 PDF 렌더러.

사용: python3 render_letter.py <지원폴더>/letter.yaml [-o 출력.pdf]

- 본문은 letter.yaml 의 source (윤문 확정본 Markdown) 에서 읽는다. '## ' 소제목마다 한 섹션.
  소제목에 ' — ' 가 있으면 앞은 왼쪽 레일 이름, 뒤는 굵은 한 줄 제목이 된다.
- '## [웹 답변] …' 섹션은 지원서 입력용이라 PDF 에 넣지 않는다.
- requirements(공고 요건 ↔ 경험 표)는 after_section 번째 섹션 뒤에 넣는다.
- lang: en 이면 영문 라벨('Preferred' 등)과 영문 이름을 쓴다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from config import profile  # noqa: E402
from pdf_base import LABELS, LETTER_CSS, contact_html, doc, e, render, section, set_theme  # noqa: E402

WEB_PREFIX = "[웹 답변]"


def letter_blocks(md_text: str) -> list[str]:
    text = md_text.split("<!-- HUMANIZE-SUMMARY")[0]
    blocks = [x.strip() for x in re.split(r"^## ", text, flags=re.M) if x.strip()]
    return [b for b in blocks if not b.startswith(WEB_PREFIX)]


def req_html(rows: list[dict], lang: str = "ko") -> str:
    lis = []
    for r in rows:
        a = f'<span class="opt">{LABELS[lang]["preferred"]}</span>{e(r["req"])}' if r.get("optional") else e(r["req"])
        lis.append(f'<li><b>{a}</b><span>{e(r["evidence"])}</span></li>')
    return f'<ul class="req">{"".join(lis)}</ul>'


def build_html(data: dict, md_text: str) -> str:
    lang = data.get("lang", "ko")
    name = profile()["name"]["en" if lang == "en" else "ko"]
    parts = [f"""
<header class="hd">
  <div>
    <p class="eyebrow">{e(data["eyebrow"])}</p>
    <h1>{e(name)} <small>{e(data.get("subtitle", ""))}</small></h1>
  </div>
  {contact_html()}
</header>"""]
    req = data.get("requirements")
    rail_meta = data.get("rail_meta", {})
    for i, blk in enumerate(letter_blocks(md_text), start=1):
        head, _, body = blk.partition("\n")
        rail, _, headline = head.strip().partition(" — ")
        paras = "".join(f"<p>{e(x.strip().replace(chr(10), ' '))}</p>" for x in body.split("\n\n") if x.strip())
        h3 = f"<h3>{e(headline)}</h3>" if headline else ""
        parts.append(section(rail, rail_meta.get(rail), h3 + paras))
        if req and i == req.get("after_section", 1):
            parts.append(section(req.get("heading", LABELS[lang]["requirements"]), req.get("meta"), req_html(req["rows"], lang)))
    return doc(data["title"], data.get("label", "Cover Letter" if lang == "en" else "자기소개서"), LETTER_CSS, "".join(parts), lang)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("letter_yaml")
    ap.add_argument("-o", "--out")
    ap.add_argument("--theme", help="테마 프리셋으로 미리보기 (theme.yaml 무시)")
    args = ap.parse_args()
    set_theme(args.theme)
    src = Path(args.letter_yaml).resolve()
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    md = (src.parent / data["source"]).read_text(encoding="utf-8")
    out = Path(args.out) if args.out else src.parent / data["output"]
    print(render(build_html(data, md), out, src.parent / "_build", f"{src.stem}.html"))


if __name__ == "__main__":
    main()
