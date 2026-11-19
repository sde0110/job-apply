#!/usr/bin/env python3
"""자기소개서 글자 수·바이트 수 계산.

사용:
  python3 count.py application.md      # '## 문항' 단위로 계산, '- limit: 1000자' 등과 비교
  python3 count.py --text "본문"
  python3 count.py --file answer.txt --limit 1000 --unit chars|nospace|bytes|utf8

application.md 형식:
  ## 1. 지원 동기
  - limit: 1000자 (공백 포함)      ← 1000자 / 1000자 (공백 제외) / 2000byte / 2000byte (utf-8)
  ```text
  답변 본문
  ```
"""
import argparse
import re
import sys


def stats(text: str) -> dict[str, int]:
    return {
        "chars": len(text),
        "nospace": len(re.sub(r"\s", "", text)),
        "bytes": sum(2 if ord(c) > 127 else 1 for c in text),  # 한글 2byte (국내 채용 사이트에서 흔한 방식)
        "utf8": len(text.encode("utf-8")),
        "lines": text.count("\n") + 1 if text else 0,
    }


def parse_limit(s: str) -> tuple[int, str] | None:
    m = re.search(r"(\d[\d,]*)\s*(자|byte|bytes|바이트)", s, re.I)
    if not m:
        return None
    n = int(m.group(1).replace(",", ""))
    if m.group(2) == "자":
        return n, "nospace" if re.search(r"공백\s*(제외|미포함)", s) else "chars"
    return n, "utf8" if re.search(r"utf-?8", s, re.I) else "bytes"


LABEL = {"chars": "공백 포함", "nospace": "공백 제외", "bytes": "byte(한글 2)", "utf8": "byte(UTF-8)"}


def report(title: str, text: str, limit: tuple[int, str] | None) -> bool:
    s = stats(text)
    line = f"{title}\n  공백 포함 {s['chars']}자 | 공백 제외 {s['nospace']}자 | {s['bytes']}byte(한글 2) | {s['utf8']}byte(UTF-8)"
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


def parse_md(md: str):
    sections = re.split(r"^##\s+", md, flags=re.M)[1:]
    for sec in sections:
        title = sec.splitlines()[0].strip()
        lim_line = re.search(r"^-\s*limit:\s*(.+)$", sec, re.M)
        limit = parse_limit(lim_line.group(1)) if lim_line else None
        block = re.search(r"```(?:text)?\n(.*?)\n```", sec, re.S)
        if block:
            yield title, block.group(1), limit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--unit", default="chars", choices=list(LABEL))
    args = ap.parse_args()

    if args.text is not None or args.file:
        text = args.text if args.text is not None else open(args.file, encoding="utf-8").read().rstrip("\n")
        ok = report("(입력)", text, (args.limit, args.unit) if args.limit else None)
        return 0 if ok else 2

    if not args.md:
        ap.print_help()
        return 1
    all_ok = True
    found = False
    for title, body, limit in parse_md(open(args.md, encoding="utf-8").read()):
        found = True
        all_ok &= report(f"## {title}", body, limit)
    if not found:
        print("'## 제목' 아래 ```text 블록을 찾지 못했습니다.")
        return 1
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
