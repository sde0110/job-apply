#!/usr/bin/env python3
"""이번 지원 산출물 폴더와 템플릿 생성. 이미 있는 파일은 덮어쓰지 않는다.

사용: python3 init_output.py <회사명> <직무명> [--date YYYY-MM-DD]
산출물 위치는 sources.yaml 의 output_dir (없으면 base/output/applications).
"""
import argparse
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TEMPLATES as _T, output_root  # noqa: E402

TEMPLATES = str(_T / "md")


def safe(s: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", s.strip()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("company")
    ap.add_argument("role")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    out = os.path.join(output_root(), f"{args.date}_{safe(args.company)}_{safe(args.role)}")
    os.makedirs(out, exist_ok=True)
    for name in ("application.md", "evidence.md", "status.md"):
        dst = os.path.join(out, name)
        if os.path.exists(dst):
            print(f"유지: {dst}")
            continue
        with open(os.path.join(TEMPLATES, name), encoding="utf-8") as f:
            body = f.read().replace("{{회사명}}", args.company).replace("{{직무명}}", args.role).replace("{{날짜}}", args.date)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"생성: {dst}")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
