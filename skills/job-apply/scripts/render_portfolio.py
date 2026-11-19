#!/usr/bin/env python3
"""포트폴리오 PDF 렌더러.

사용: python3 render_portfolio.py [portfolio.yaml] [-o 출력.pdf]
      (경로를 안 주면 사용자 데이터 폴더의 portfolio.yaml)

portfolio.yaml 구조
- cover: 표지 (eyebrow, role, claim, claim_p, career[], skills[], toc[], site_link)
- pages[]: 프로젝트 한 쪽씩 (eyebrow, title "주제목 | 부제", meta "a | b", slug, blocks[])
  blocks 종류: metric [큰 글씨, 설명] / intro 문단 / figure {src, max_h(mm), caption}
               blk [소제목, 본문] / flow [단계, "윗줄\\n아랫줄"] / split {figure, subs[[소제목, 본문]]}
               part {label, title, blocks[txt|flow|metric]} / divider / foot {stack "a · b", award, links[[slug, 글]]}
- appendix: 부록 (paper, awards[[날짜, 내용]], education[[날짜, 내용]], extra_projects[[slug, 이름, 설명]])
- site: 프로젝트 상세 링크 기준 URL ({site}/projects/{slug}.html), images: 그림 기준 폴더
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from config import data_home, profile  # noqa: E402
from pdf_base import PORTFOLIO_CSS, doc, e, render, set_theme  # noqa: E402


class Builder:
    def __init__(self, data: dict):
        self.d = data
        self.site = data.get("site", "").rstrip("/")
        self.images = Path(os.path.expanduser(data.get("images", "."))).resolve()
        p = profile()
        github = p.get("links", {}).get("github", "").replace("https://", "")
        self.contact = f'{e(p["contact"]["email"])} &nbsp;|&nbsp; {e(github)}'
        self.name = p["name"]["ko"]

    # ── 조각 ──
    @staticmethod
    def title_html(t):
        main, _, sub = t.partition(" | ")
        return e(main) + (f" <small>{e(sub)}</small>" if sub else "")

    @staticmethod
    def meta_html(m):
        return '<i>|</i>'.join(e(x) for x in m.split(" | "))

    def head(self, pg):
        slug = pg.get("slug")
        detail = f'<a class="detail" href="{self.site}/projects/{slug}.html">프로젝트 상세 ↗</a>' if slug else ""
        return (f'<header class="ph"><div><p class="eyebrow">{e(pg["eyebrow"])}</p><h1>{self.title_html(pg["title"])}</h1>'
                f'<p class="meta">{self.meta_html(pg["meta"])}</p></div>{detail}</header>')

    def fig(self, f):
        src = (self.images / f["src"]).resolve().as_uri()
        return f'<figure><img src="{src}" style="max-height:{f["max_h"]}mm" alt=""><figcaption>{e(f["caption"])}</figcaption></figure>'

    @staticmethod
    def flow(steps):
        out = []
        for i, s in enumerate(steps):
            a, _, b = s.partition("\n")
            if i:
                out.append('<li class="arr">→</li>')
            small = "<small>" + e(b) + "</small>" if b else ""
            out.append(f"<li><b>{i + 1:02d}</b>{e(a)}{small}</li>")
        return f'<ul class="flow">{"".join(out)}</ul>'

    def foot(self, f):
        award = f'<p class="award">{e(f["award"])}</p>' if f.get("award") else ""
        chips = ""
        if f.get("stack"):
            chips = '<ul class="chips">' + "".join(f"<li>{e(x)}</li>" for x in f["stack"].split(" · ")) + "</ul>"
        links = ""
        if f.get("links"):
            links = '<p class="links">' + "".join(
                f'<a href="{self.site}/projects/{slug}.html">{e(text)}</a>' for slug, text in f["links"]) + "</p>"
        return f'<div class="foot">{award}{chips}{links}</div>'

    def block(self, b):
        kind, val = next(iter(b.items()))
        if kind == "metric":
            return f'<div class="metric"><b>{e(val[0])}</b><span>{e(val[1])}</span></div>'
        if kind == "intro":
            return f'<p class="intro">{e(val)}</p>'
        if kind == "txt":
            return f'<p class="txt">{e(val)}</p>'
        if kind == "figure":
            return self.fig(val)
        if kind == "blk":
            return f'<div class="blk"><h2>{e(val[0])}</h2><p>{e(val[1])}</p></div>'
        if kind == "flow":
            return self.flow(val)
        if kind == "split":
            right = "".join(f"<h3>{e(a)}</h3><p>{e(t)}</p>" for a, t in val["subs"])
            return f'<div class="split">{self.fig(val["figure"])}<div class="sub3">{right}</div></div>'
        if kind == "part":
            inner = "".join(self.block(x) for x in val["blocks"])
            return f'<div class="part"><h2><span>{e(val["label"])}</span>{e(val["title"])}</h2>{inner}</div>'
        if kind == "divider":
            return '<div class="divider"></div>'
        if kind == "foot":
            return self.foot(val)
        sys.exit(f"알 수 없는 블록: {kind}")

    @staticmethod
    def pg(inner, cls=""):
        return f'<section class="pg {cls}">{inner}</section>'

    # ── 쪽 ──
    def cover(self):
        c = self.d["cover"]
        toc = "".join(f'<li><span class="no">{e(t["no"])}</span><div><b>{e(t["title"])}</b><span>{e(t["desc"])}</span></div></li>' for t in c["toc"])
        career = "".join(f'<li><span class="when num">{e(r["when"])}</span><div><b>{e(r["name"])}</b> <i>· {e(r["role"])}</i></div></li>' for r in c["career"])
        skills = "".join(f'<li class="plain">{e(s)}</li>' for s in c["skills"])
        return self.pg(f"""
<div class="head">
  <p class="eyebrow">{e(c["eyebrow"])}</p>
  <h1>{e(self.name)}</h1>
  <p class="role">{e(c["role"])}</p>
</div>
<p class="claim">{e(c["claim"])}</p>
<p class="claim-p">{e(c["claim_p"])}</p>
<div class="cv">
  <h2>경력</h2>
  <ul class="rows">{career}</ul>
</div>
<div class="cv">
  <h2>주로 사용하는 기술</h2>
  <ul class="rows">{skills}</ul>
</div>
<div class="toc"><h2>프로젝트 안내</h2><ul>{toc}</ul></div>
<div class="contact-line">
  <span>{self.contact}</span>
  <a class="site" href="{self.site}">{e(c["site_link"])}</a>
</div>""", "cover")

    def project(self, pg):
        return self.pg(self.head(pg) + "".join(self.block(b) for b in pg["blocks"]))

    def appendix(self):
        a = self.d["appendix"]

        def rows(items):
            return '<ul class="rows">' + "".join(
                f'<li><span class="when num">{e(d)}</span><div>{e(t)}</div></li>' for d, t in items) + "</ul>"

        paper = ""
        if a.get("paper"):
            paper = (f'<h2>연구</h2><div class="paper"><b>{e(a["paper"]["title"])}</b>'
                     f'<p>{e(a["paper"]["text"])}</p></div>')
        xp = "".join(f'<li><a href="{self.site}/projects/{s}.html">{e(n)}</a><span>{e(d)}</span></li>' for s, n, d in a["extra_projects"])
        return self.pg(
            self.head({"eyebrow": a["eyebrow"], "title": a["title"], "meta": a["meta"]})
            + f'<div class="ap">{paper}<h2>주요 수상</h2>{rows(a["awards"])}<h2>학력 · 교육 · 자격</h2>{rows(a["education"])}'
            + f'<h2>추가 프로젝트</h2><ul class="xp">{xp}</ul></div>'
            + f'<div class="foot" style="margin-top:9mm;font-size:8.6pt;color:var(--ink)">{self.contact}</div>'
        )

    def html(self):
        body = self.cover() + "".join(self.project(p) for p in self.d["pages"]) + self.appendix()
        return doc(self.d["title"], "포트폴리오", PORTFOLIO_CSS, body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portfolio_yaml", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--theme", help="테마 프리셋으로 미리보기 (theme.yaml 무시)")
    args = ap.parse_args()
    set_theme(args.theme)
    src = Path(args.portfolio_yaml or data_home() / "portfolio.yaml").resolve()
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else Path.cwd() / data["output"]
    print(render(Builder(data).html(), out, out.parent / "_build", "portfolio.html"))


if __name__ == "__main__":
    main()
