#!/usr/bin/env python3
"""자기소개서 문체 검사 — rules.yaml 의 style 규칙으로 확정본과 PDF 데이터를 검사한다.

사용:
  python3 style_check.py <폴더>/final_coverletter.md [<폴더>/resume.yaml <폴더>/letter.yaml …]
  python3 style_check.py --text "본문"
  python3 style_check.py final_coverletter.md --rules 다른/rules.yaml      # 기본: 사용자 데이터의 rules.yaml

검사 (rules.yaml `style:` 값. 없으면 괄호 안 기본값):
  middle_dot       (warn)  본문의 가운뎃점(·). 쉼표나 슬래시로 바꾼다
  team_size        (warn)  "5인 팀", "세 명이 함께", "팀원 4명", "team of 4" 같은 인원수
  bracket_heading  (off)   '## [웹 답변]' 답변의 첫 줄이 [소제목] 한 줄인지 (heading_min_chars 이상인 답변만)
  heading_min_chars (300)  bracket_heading 을 볼 최소 길이(공백 제외). 이력서 타이틀·한 줄 소개 같은 짧은 칸은 건너뛴다
  heading_skip     (아래 HEADING_SKIP)  제목에 이 말이 든 웹 답변은 bracket_heading 을 보지 않는다 (경력 주요업무·프로젝트 상세 칸)
  long_paragraph   (500)   이보다 긴 문단(한 줄)이 있으면 경고. 0 = 끔
  tech_list        (0)     한 문장에 영문 단어가 이 개수 이상이면 경고(기술명 나열). 0 = 끔
  avoid            (아래 AVOID)  쓰지 않을 표현. 경고
  allow            ([])    위 검사에서 뺄 정확한 문구 (공고의 공식 직무명 "AI·AX", 학과 공식 명칭 등)
middle_dot·team_size·bracket_heading 값: error(종료 코드 2) / warn(보고만) / off

- .md: '## ' 섹션마다 본문을 본다(주석과 HUMANIZE-SUMMARY 제외 — count.py 와 같은 기준).
  섹션 안에 <!-- style-skip: bracket_heading tech_list --> 를 두면 그 섹션에서 해당 검사를 건너뛴다.
  경력 상세처럼 목록 형식인 칸에만 쓰고, 건너뛴 사실은 출력에 남는다.
- .yaml(resume·letter): 글 값(eyebrow, lede, text, tag, sub, rail_meta, evidence …)에서 middle_dot·team_size·avoid 만 본다.
  profile.yaml 에서 오는 공식 명칭(학과·수상명)은 검사하지 않는다.

종료 코드: 0 = error 없음(경고는 있을 수 있음), 2 = error 규칙 위반, 1 = 읽을 글 없음
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from count import body_text  # noqa: E402

AVOID = ["에 있어서", "하는 것이 가능", "인재가 되겠습니다", "다양한", "효과적인", "혁신적인"]
HEADING_SKIP = ["주요업무", "담당업무", "상세", "타이틀", "간단소개", "한 줄"]
DEFAULTS = {"middle_dot": "warn", "team_size": "warn", "bracket_heading": "off", "heading_min_chars": 300,
            "heading_skip": HEADING_SKIP, "long_paragraph": 500, "tech_list": 0, "avoid": AVOID, "allow": []}
LEVELS = {"error", "warn", "off"}

NUM = r"(?:\d+|두|세|네|다섯|여섯|일곱|여덟|아홉|열)"
TEAM = re.compile(
    rf"{NUM}\s*(?:명|인)\s*(?:팀|규모|조\b|으로\s*(?:구성|이뤄|이루어)|이\s*함께|이서|의\s*팀)"
    rf"|팀원\s*{NUM}\s*명|(?:팀|조)\s*\(\s*{NUM}\s*(?:명|인)"
    r"|\bteam of \d+|\b\d+-(?:person|member) team|\b\d+ (?:team )?members\b", re.I)
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9+#]*(?:[.\-][A-Za-z0-9+#]+)*")
HEADING = re.compile(r"^\[[^\[\]]{2,}\]$")
SKIP = re.compile(r"<!--\s*style-skip:(.*?)-->", re.S)
NOT_PROSE = {"output", "source", "link", "links", "url", "file", "theme", "layout", "lang", "when", "after_section"}


def load_rules(path: str | None) -> dict:
    if path:
        with open(path, encoding="utf-8") as f:
            r = yaml.safe_load(f) or {}
    else:
        from config import rules
        r = rules()
    style = dict(DEFAULTS)
    style.update({k: v for k, v in (r.get("style") or {}).items() if v is not None})
    return style


def snippet(text: str, start: int, end: int, pad: int = 12) -> str:
    s = text[max(0, start - pad):end + pad].replace("\n", " ")
    return ("…" if start > pad else "") + s + ("…" if end + pad < len(text) else "")


class Checker:
    def __init__(self, style: dict):
        self.s = style
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.notes: list[str] = []

    def add(self, level: str, msg: str):
        if level == "error":
            self.errors.append(msg)
        elif level == "warn":
            self.warns.append(msg)

    def mask(self, text: str) -> str:
        """allow 문구는 같은 길이의 공백으로 가려 검사에서 뺀다 (위치는 유지)."""
        for a in self.s.get("allow") or []:
            text = text.replace(str(a), " " * len(str(a)))
        return text

    def common(self, where: str, text: str):
        t = self.mask(text)
        lv = self.s["middle_dot"]
        if lv != "off":
            hits = [m.start() for m in re.finditer("·", t)]
            if hits:
                shown: list[int] = []
                for i in hits:  # 붙어 있는 가운뎃점(a·b·c)은 예시 하나로
                    if not shown or i - shown[-1] > 12:
                        shown.append(i)
                ex = " / ".join(snippet(text, i, i + 1) for i in shown[:3])
                self.add(lv, f"{where}: 가운뎃점 {len(hits)}개 → 쉼표나 슬래시로 ({ex})")
        lv = self.s["team_size"]
        if lv != "off":
            for m in TEAM.finditer(t):
                self.add(lv, f"{where}: 팀 인원수 '{m.group(0)}' → 맡은 부분만 쓴다 ({snippet(text, m.start(), m.end())})")
        for phrase in self.s.get("avoid") or []:
            n = t.count(str(phrase))
            if n:
                self.warns.append(f"{where}: 피할 표현 '{phrase}' {n}번")

    def section(self, title: str, body: str, skip: set[str]):
        where = f"## {title}"
        if skip:
            self.notes.append(f"{where}: 건너뜀 {', '.join(sorted(skip))} (style-skip 주석)")
        self.common(where, body)
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        size = len(re.sub(r"\s", "", body))
        lv = self.s["bracket_heading"]
        exempt = any(str(w) in title for w in self.s.get("heading_skip") or [])
        if (lv != "off" and "bracket_heading" not in skip and title.startswith("[웹 답변]") and not exempt
                and size >= int(self.s["heading_min_chars"]) and lines and not HEADING.match(lines[0])):
            self.add(lv, f"{where}: 첫 줄이 [소제목] 한 줄이 아님 → '{lines[0][:30]}'")
        limit = int(self.s["long_paragraph"] or 0)
        if limit and "long_paragraph" not in skip:
            for ln in lines:
                if len(ln) > limit:
                    self.warns.append(f"{where}: {len(ln)}자 문단 (기준 {limit}자) → 나눠서 읽히게 '{ln[:24]}…'")
        n = int(self.s["tech_list"] or 0)
        if n and "tech_list" not in skip:
            for sent in re.split(r"(?<=[.!?])\s+|\n", body):
                words = LATIN.findall(self.mask(sent))
                if len(words) >= n:
                    self.warns.append(f"{where}: 한 문장에 영문 {len(words)}개 ({', '.join(words[:6])}) → 꼭 필요한 기술명만, "
                                      f"비전공자도 읽히게 '{sent.strip()[:30]}…'")

    def md(self, path: str, md: str) -> int:
        md = md.split("<!-- HUMANIZE-SUMMARY")[0]
        found = 0
        for sec in re.split(r"^##\s+", md, flags=re.M)[1:]:
            title, _, rest = sec.partition("\n")
            rest = re.split(r"^#\s", rest, maxsplit=1, flags=re.M)[0]
            block = re.search(r"```(?:text)?\n(.*?)\n```", rest, re.S)
            body = block.group(1) if block else body_text(rest)
            if not body:
                continue
            skip = set(re.findall(r"[a-z_]+", " ".join(SKIP.findall(rest))))
            self.section(title.strip(), body, skip)
            found += 1
        return found

    def yaml_values(self, path: str, data) -> int:
        found = 0

        def walk(v, key_path):
            nonlocal found
            if isinstance(v, dict):
                for k, x in v.items():
                    if str(k) not in NOT_PROSE:
                        walk(x, f"{key_path}.{k}" if key_path else str(k))
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{key_path}[{i}]")
            elif isinstance(v, str) and v.strip():
                found += 1
                self.common(f"{Path(path).name} {key_path}", v)

        walk(data, "")
        return found


def main() -> int:
    ap = argparse.ArgumentParser(description="자기소개서 문체 검사 (rules.yaml style)")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--text")
    ap.add_argument("--rules", help="rules.yaml 경로 (기본: 사용자 데이터 폴더)")
    args = ap.parse_args()
    c = Checker(load_rules(args.rules))
    found = 0
    if args.text is not None:
        c.section("[웹 답변] (입력)", args.text.strip(), set())
        found = 1
    for f in args.files:
        text = Path(f).read_text(encoding="utf-8")
        if f.endswith((".yaml", ".yml")):
            found += c.yaml_values(f, yaml.safe_load(text) or {})
        else:
            found += c.md(f, text)
    if not found:
        print("검사할 글이 없습니다 ('## ' 섹션이나 yaml 글 값).")
        return 1
    for m in c.errors:
        print("오류:", m)
    for m in c.warns:
        print("경고:", m)
    for m in c.notes:
        print("참고:", m)
    print(f"\n문체 검사: 오류 {len(c.errors)}개, 경고 {len(c.warns)}개"
          + (" — 오류는 모두 고치고, 경고는 읽어 보고 판단한다" if c.errors or c.warns else " — 통과"))
    return 2 if c.errors else 0


if __name__ == "__main__":
    sys.exit(main())
