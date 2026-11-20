#!/usr/bin/env python3
"""자기소개서 글자 수·바이트 수 계산.

사용:
  python3 count.py final_coverletter.md                     # '## [웹 답변] …' 문항마다 계산
  python3 count.py final_coverletter.md --limit 1000        # 제한이 없는 문항에 1000자(공백 포함) 적용
  python3 count.py final_coverletter.md --limit "지원동기=1000자" --limit "경력기술서=4000byte"
  python3 count.py final_coverletter.md --all               # PDF 섹션까지 모든 '## ' 문항
  python3 count.py --text "본문"
  python3 count.py --file answer.txt --limit 1000 --unit chars|nospace|bytes|utf8

읽는 형식 (둘 다 된다):
  1) final_coverletter.md — SKILL.md 가 정한 형식. '## [웹 답변] 문항 이름' 아래 본문 전체가 답변이다.
     문항별 제한은 본문 안 주석으로 적을 수 있다: <!-- limit: 1000자 (공백 제외) -->
     주석과 '<!-- HUMANIZE-SUMMARY' 뒤는 세지 않는다(form_check.py 의 해시 기준과 같다).
  2) 옛 application.md — '## 문항' 아래 '- limit: 1000자' 줄과 ```text 블록.

제한 표기: 1000자 (공백 포함) / 1000자 (공백 제외) / 2000byte (한글 2바이트) / 2000byte (utf-8)
줄바꿈은 1자로 센다. 사이트 카운터가 줄바꿈을 2자로 세면 '줄바꿈 N개'만큼 더한 값과 비교한다.
"""
from __future__ import annotations

import argparse
import re
import sys

COMMENT = re.compile(r"<!--.*?-->", re.S)


def stats(text: str) -> dict[str, int]:
    return {
        "chars": len(text),
        "nospace": len(re.sub(r"\s", "", text)),
        "bytes": sum(2 if ord(c) > 127 else 1 for c in text),  # 한글 2byte (국내 채용 사이트에서 흔한 방식)
        "utf8": len(text.encode("utf-8")),
        "lines": text.count("\n") + 1 if text else 0,
        "newlines": text.count("\n"),
    }


def parse_limit(s: str) -> tuple[int, str] | None:
    m = re.search(r"(\d[\d,]*)\s*(자|byte|bytes|바이트)?", s, re.I)
    if not m:
        return None
    n = int(m.group(1).replace(",", ""))
    if (m.group(2) or "자") == "자":
        return n, "nospace" if re.search(r"공백\s*(제외|미포함)", s) else "chars"
    return n, "utf8" if re.search(r"utf-?8", s, re.I) else "bytes"


LABEL = {"chars": "공백 포함", "nospace": "공백 제외", "bytes": "byte(한글 2)", "utf8": "byte(UTF-8)"}


def report(title: str, text: str, limit: tuple[int, str] | None) -> bool:
    s = stats(text)
    line = (f"{title}\n  공백 포함 {s['chars']}자 | 공백 제외 {s['nospace']}자 | {s['bytes']}byte(한글 2) | "
            f"{s['utf8']}byte(UTF-8) | 줄바꿈 {s['newlines']}개")
    ok = True
    if limit:
        n, unit = limit
        used = s[unit]
        ratio = used / n * 100
        ok = used <= n
        flag = "초과" if not ok else ("80% 미만" if ratio < 80 else "OK")
        line += f"\n  제한 {n} {LABEL[unit]} → {used} ({ratio:.0f}%) [{flag}]"
    print(line)
    return ok


def body_text(sec_body: str) -> str:
    """'## ' 제목 줄 아래 본문 — form_check.section_text 와 같은 기준(주석 제거, 앞뒤 공백 제거)."""
    return COMMENT.sub("", sec_body).strip()


def parse_md(md: str, all_sections: bool = False):
    md = md.split("<!-- HUMANIZE-SUMMARY")[0]
    sections = re.split(r"^##\s+", md, flags=re.M)[1:]
    has_web = any(s.startswith("[웹 답변]") for s in sections)
    for sec in sections:
        title, _, rest = sec.partition("\n")
        title = title.strip()
        lim = re.search(r"^-\s*limit:\s*(.+)$", rest, re.M) or re.search(r"<!--\s*limit:\s*(.+?)\s*-->", rest)
        limit = parse_limit(lim.group(1)) if lim else None
        block = re.search(r"```(?:text)?\n(.*?)\n```", rest, re.S)
        if block:
            yield title, block.group(1), limit
        elif all_sections or title.startswith("[웹 답변]") or not has_web:
            rest = re.split(r"^#\s", rest, maxsplit=1, flags=re.M)[0]  # 다음 '# ' 큰 제목 전까지
            text = body_text(rest)
            if text:
                yield title, text, limit


def cli_limits(values: list[str], unit: str):
    """--limit 값들 → (기본 제한, [(문항 일부, 제한)])"""
    default, by_label = None, []
    for v in values:
        label, eq, spec = v.rpartition("=")
        if not eq:
            spec = v
        lim = parse_limit(spec)
        if not lim:
            sys.exit(f"--limit 값을 읽지 못했습니다: {v}")
        if re.fullmatch(r"\s*\d[\d,]*\s*", spec):
            lim = (lim[0], unit)  # 숫자만 주면 --unit 을 따른다
        if eq:
            by_label.append((label.strip(), lim))
        else:
            default = lim
    return default, by_label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--limit", action="append", default=[], help='1000 / "1000자 (공백 제외)" / "문항 일부=2000byte" (여러 번 가능)')
    ap.add_argument("--unit", default="chars", choices=list(LABEL))
    ap.add_argument("--all", action="store_true", help="[웹 답변] 이 아닌 '## ' 섹션도 센다")
    args = ap.parse_args()
    default, by_label = cli_limits(args.limit, args.unit)

    if args.text is not None or args.file:
        text = args.text if args.text is not None else open(args.file, encoding="utf-8").read().rstrip("\n")
        ok = report("(입력)", text, default)
        return 0 if ok else 2

    if not args.md:
        ap.print_help()
        return 1
    all_ok = True
    found = 0
    for title, body, limit in parse_md(open(args.md, encoding="utf-8").read(), args.all):
        found += 1
        limit = next((lim for lab, lim in by_label if lab in title), None) or limit or default
        all_ok &= report(f"## {title}", body, limit)
    if not found:
        print("'## [웹 답변] 문항' 섹션이나 '## 제목' 아래 ```text 블록을 찾지 못했습니다.")
        return 1
    print(f"\n{found}개 문항: " + ("모두 제한 이내" if all_ok else "제한 초과 있음"))
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
