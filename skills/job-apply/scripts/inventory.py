#!/usr/bin/env python3
"""지원 자료 목록. 기본 대상은 sources.yaml 의 base 와 evidence_roots.
한글 경로의 NFC/NFD 차이를 맞추고, 중간 산출물 폴더는 기본 제외한다.

사용: python3 inventory.py [폴더...] [--all] [--depth N]
"""
import argparse
import datetime as dt
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import evidence_roots, exclude_dirs, resolve  # noqa: E402

def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def walk(root: str, include_all: bool, max_depth: int):
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - root_depth
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and (include_all or d not in exclude_dirs()))
        if depth >= max_depth:
            dirnames[:] = []
        for f in sorted(filenames):
            if f.startswith(".") or f.startswith("~$"):
                continue
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            rel = unicodedata.normalize("NFC", os.path.relpath(p, root))
            mtime = dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
            print(f"{mtime}  {human(st.st_size):>7}  {rel}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true", help="tmp/_workspace 등도 포함")
    ap.add_argument("--depth", type=int, default=3)
    args = ap.parse_args()
    for raw in args.paths or evidence_roots():
        path = resolve(raw)
        print(f"\n## {unicodedata.normalize('NFC', path or raw)}")
        if not path:
            print("  (경로를 찾지 못함)")
            continue
        walk(path, args.all, args.depth)


if __name__ == "__main__":
    sys.exit(main())
