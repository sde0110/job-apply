#!/usr/bin/env python3
"""이력서 PDF 렌더러.

사용: python3 render_resume.py <지원폴더>/resume.yaml [-o 출력.pdf] [--theme 프리셋]

- 이름·연락처·경력 기간·직함·학력·자격·어학·수상은 profile.yaml 에서 가져온다.
- 공고마다 달라지는 내용(머리말, 경력 세부 항목, 프로젝트, 기술)은 resume.yaml 에 쓴다.
- 어학·수상은 rules.yaml 규칙으로 거른다 (예: TOEIC 미기재, 미확인 수상 제외).
- resume.yaml 의 layout: compact 면 1쪽용 촘촘한 배치, lang: en 이면 영문 이력서
  (profile.yaml 의 *_en 값을 쓰고, 한글뿐인 값에 영문이 없으면 어떤 값이 필요한지 알려 주고 멈춘다).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from config import profile, rules  # noqa: E402
from pdf_base import (LABELS, RESUME_COMPACT_CSS, RESUME_CSS, chips, contact_html, doc, e, link, render,  # noqa: E402
                      set_theme, when, ym)

AWARD_OK = {"원본", "부분"}
HANGUL = re.compile(r"[가-힣]")


class Resume:
    def __init__(self, data: dict, prof: dict, rl: dict):
        self.d, self.prof, self.rl = data, prof, rl
        self.lang = data.get("lang", "ko")
        self.L = LABELS[self.lang]
        self.missing: list[str] = []

    # 영문 이력서: profile 값 대신 <key>_en 을 쓴다. 한글이 든 값에 _en 이 없으면 모아서 알린다.
    def v(self, obj: dict, key: str, where: str) -> str:
        val = obj.get(key)
        if self.lang != "en" or val in (None, ""):
            return "" if val is None else str(val)
        en = obj.get(f"{key}_en")
        if en:
            return str(en)
        if HANGUL.search(str(val)):
            self.missing.append(f"{where}.{key}_en  (현재 값: {val})")
        return str(val)

    def ym(self, s) -> str:
        return ym(s, self.lang)

    def career_small(self, c: dict, where: str) -> str:
        small = self.v(c, "display_title", where) or f'{self.v(c, "department", where)} {self.v(c, "title", where)}'.strip()
        parts = [small]
        et = self.v(c, "employment_type", where)
        if et and et not in small:
            parts.append(et)
        if c.get("note"):
            parts.append(self.v(c, "note", where))
        return " · ".join(parts)

    def experience(self) -> str:
        career = {c["company"]: (i, c) for i, c in enumerate(self.prof.get("career", []))}
        out = []
        for x in self.d.get("experience", []):
            if x["company"] not in career:
                sys.exit(f"profile.yaml career 에 없는 회사: {x['company']}")
            i, c = career[x["company"]]
            where = f"career[{i}]"
            body = ""
            if x.get("items"):
                def tag(it):
                    return " <small>" + e(it["tag"]) + "</small>" if it.get("tag") else ""

                items = "".join(f'<div class="item"><h4>{e(it["title"])}{tag(it)}</h4><p>{e(it["text"])}</p></div>'
                                for it in x["items"])
                body += f'<div class="items">{items}</div>'
            if x.get("text"):
                body += f'<p style="margin-top:1.2mm">{e(x["text"])}</p>'
            stack = f'<p class="co-stack">{e(x["stack"])}</p>' if x.get("stack") else ""
            out.append(f"""
  <article class="entry">{when(self.ym(c["start"]), self.ym(c.get("end")))}
    <div class="what">
      <h3>{e(self.v(c, "company", where))} <small>{e(self.career_small(c, where))}</small></h3>
      {stack}
      {body}
    </div>
  </article>""")
        return f'<section class="sec"><h2>{self.L["experience"]}</h2>{"".join(out)}</section>'

    @staticmethod
    def projects(sec: dict) -> str:
        rows = []
        for p in sec["entries"]:
            w = p["when"] if isinstance(p["when"], list) else [p["when"]]
            if p.get("link"):
                head = f'<h3>{e(p["title"])}</h3><div class="sub"><span>{e(p["sub"])}</span>{link(p["link"])}</div>'
            elif p.get("sub"):
                head = f'<h3>{e(p["title"])} <small>{e(p["sub"])}</small></h3>'
            else:
                head = f'<h3>{e(p["title"])}</h3>'
            dots = "".join(f"<li>{e(d)}</li>" for d in p.get("dots", []))
            dots = f'<ul class="dots">{dots}</ul>' if dots else ""
            text = f'<p style="margin-top:.5mm">{e(p["text"])}</p>' if p.get("text") else ""
            award = f'<p class="award">{e(p["award"])}</p>' if p.get("award") else ""
            stack = chips(p["stack"]) if p.get("stack") else ""
            cls = "entry compact" if p.get("compact") else "entry"
            rows.append(f"""
  <article class="{cls}" style="break-inside:avoid">{when(*w)}
    <div class="what">
      {head}
      {dots}{text}
      {award}
      {stack}
    </div>
  </article>""")
        note = f' <em>{e(sec["note"])}</em>' if sec.get("note") else ""
        return f'<section class="sec"><h2>{e(sec["heading"])}{note}</h2>{"".join(rows)}</section>'

    def skills(self) -> str:
        rows = []
        for s in self.d["skills"]:
            note = f'<i> · {e(s["note"])}</i>' if s.get("note") else ""
            rows.append(f'<div><dt>{e(s["label"])}</dt><dd>{e(s["value"])}{note}</dd></div>')
        return f'<section class="sec" style="break-inside:avoid"><h2>{self.L["skills"]}</h2><dl class="skills">{"".join(rows)}</dl></section>'

    def education(self) -> str:
        li = []
        for i, ed in enumerate(self.prof.get("education", [])):
            if not ed.get("degree"):
                continue  # 고등학교 등은 이력서에 넣지 않는다
            w = f"education[{i}]"
            a, b = ed["period"]
            li.append(f'<li>{when(self.ym(a), self.ym(b))}<div><b>{e(self.v(ed, "school", w))}</b> {e(self.v(ed, "major", w))} '
                      f'<i>· {e(self.v(ed, "degree", w))} {e(self.v(ed, "status", w))}</i></div></li>')
        for i, pg in enumerate(self.prof.get("education_programs", [])):
            w = f"education_programs[{i}]"
            a, b = pg["period"]
            hours = self.L["hours"].format(h=pg["hours"])
            li.append(f'<li>{when(self.ym(a), self.ym(b))}<div><b>{e(self.v(pg, "name", w))}</b> {e(hours)} '
                      f'<i>· {e(self.v(pg, "official_name", w))}, {e(self.v(pg, "org", w))}</i></div></li>')
        certs = sorted(enumerate(self.prof.get("certificates", [])), key=lambda t: t[1]["date"])
        by_issuer: dict[str, list] = {}
        for i, c in certs:
            by_issuer.setdefault(c["issuer"], []).append((i, c))
        for _, cs in by_issuer.items():
            years = {c["date"][:4] for _, c in cs}
            label = years.pop() if len(years) == 1 and len(cs) > 1 else self.ym(cs[0][1]["date"])
            names = " · ".join(
                f'<b>{e(self.v(c, "name", f"certificates[{i}]"))}</b> ({e(self.ym(c["date"]))})' if len(cs) > 1
                else f'<b>{e(self.v(c, "name", f"certificates[{i}]"))}</b>' for i, c in cs)
            i0, c0 = cs[0]
            li.append(f'<li><div class="when num">{e(label)}</div><div>{names} <i>· {e(self.v(c0, "issuer", f"certificates[{i0}]"))}</i></div></li>')
        policy = self.rl.get("language_scores", {})
        for t in self.prof.get("language_tests", []):
            if policy.get(t["name"]) == "never":
                continue
            li.append(f'<li><div class="when num">{e(self.ym(t["date"]))}</div><div><b>{e(t["name"])}</b> {e(t["score"])}</div></li>')
        return f'<section class="sec" style="break-inside:avoid"><h2>{self.L["education"]}</h2>\n  <ul class="rows">{"".join(li)}</ul>\n</section>'

    def awards(self) -> str:
        excluded = self.rl.get("exclude_from_resume_and_letter", []) + self.d.get("exclude_awards", [])
        li = []
        for i, a in enumerate(self.prof.get("awards", [])):
            if a.get("verified") not in AWARD_OK:
                continue  # 원본 미확인 수상은 넣지 않는다
            tokens = [t for t in a["title"].split() if len(t) > 2]
            if any(a["prize"] in ex and any(t in ex for t in tokens) for ex in excluded):
                continue
            w = f"awards[{i}]"
            detail = self.v(a, "project", w) + (f', {self.v(a, "role", w)}' if a.get("role") else "")
            li.append(f'<li><div class="when num">{e(self.ym(a["date"]))}</div><div><span class="prize">{e(self.v(a, "prize", w))}</span> '
                      f'<b>{e(self.v(a, "title", w))}</b> <i>· {e(detail)}</i></div></li>')
        if not li:
            return ""
        return f'<section class="sec" style="break-inside:avoid"><h2>{self.L["awards"]}</h2>\n  <ul class="rows">{"".join(li)}</ul>\n</section>'

    def html(self) -> str:
        name = self.prof["name"]
        if self.lang == "en":
            title_html = e(name.get("en") or self.v(name, "ko", "name"))
        else:
            title_html = f'{e(name["ko"])} <small>{e(name.get("en", ""))}</small>'
        head = f"""
<header class="hd">
  <div>
    <p class="eyebrow">{e(self.d["eyebrow"])}</p>
    <h1>{title_html}</h1>
    <p class="lede">{e(self.d["lede"])}</p>
  </div>
  {contact_html()}
</header>"""
        parts = [head, self.experience()]
        parts += [self.projects(s) for s in self.d.get("project_sections", [])]
        if self.d.get("skills"):
            parts.append(self.skills())
        parts.append(self.education())
        parts.append(self.awards())
        if self.missing:
            sys.exit("영문 이력서에 필요한 영문 값이 profile.yaml 에 없습니다. 아래 키를 채운 뒤 다시 실행하세요:\n  "
                     + "\n  ".join(dict.fromkeys(self.missing)))
        css = RESUME_CSS + (RESUME_COMPACT_CSS if self.d.get("layout") == "compact" else "")
        return doc(self.d["title"], self.d.get("label", self.L["resume"]), css, "".join(parts), self.lang)


def build_html(data: dict) -> str:
    return Resume(data, profile(), rules()).html()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resume_yaml")
    ap.add_argument("-o", "--out")
    ap.add_argument("--theme", help="테마 프리셋으로 미리보기 (theme.yaml 무시)")
    args = ap.parse_args()
    set_theme(args.theme)
    src = Path(args.resume_yaml).resolve()
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else src.parent / data["output"]
    print(render(build_html(data), out, src.parent / "_build", f"{src.stem}.html"))


if __name__ == "__main__":
    main()
