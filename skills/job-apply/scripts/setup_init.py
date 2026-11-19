#!/usr/bin/env python3
"""사용자 데이터 폴더 만들기 (초기 설정 1단계). 이미 있는 파일은 덮어쓰지 않는다.

사용: python3 setup_init.py [--home 경로] [--example]

- 기본 위치는 JOB_APPLY_HOME 또는 ~/.job-apply (폴더 권한 700, 파일 600)
- 기본: templates/data/*.example.yaml 을 profile.yaml 등으로 복사 → 사용자와 인터뷰하며 채운다
- --example: 가상 인물(홍길동) 예제 데이터로 채운다 (스킬을 시험할 때)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EXAMPLE = SKILL / "examples" / "hong-gildong"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home")
    ap.add_argument("--example", action="store_true")
    args = ap.parse_args()
    home = Path(args.home or os.environ.get("JOB_APPLY_HOME", "~/.job-apply")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)

    if args.example:
        sources = {p.name: p for p in (EXAMPLE / "data").glob("*.yaml")}
    else:
        sources = {p.name.replace(".example", ""): p for p in (SKILL / "templates" / "data").glob("*.example.yaml")}

    for name, src in sorted(sources.items()):
        dst = home / name
        if dst.exists():
            print(f"유지: {dst}")
            continue
        text = src.read_text(encoding="utf-8")
        if args.example:
            text = text.replace("{EXAMPLE_DIR}", str(EXAMPLE)).replace("{HOME}", str(home))
        dst.write_text(text, encoding="utf-8")
        os.chmod(dst, 0o600)
        print(f"생성: {dst}")

    print(f"\n사용자 데이터 폴더: {home}")
    if not args.example:
        print("다음: profile.yaml·sources.yaml 을 사용자 자료로 채운다 (/job-apply:job-apply setup 이 인터뷰로 진행)")
    print("확인: python3 scripts/doctor.py && python3 scripts/profile_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
