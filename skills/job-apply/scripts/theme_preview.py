#!/usr/bin/env python3
"""테마 프리셋 미리보기: 이력서 1쪽을 프리셋마다 렌더해 한 장의 PNG 로 나란히 보여 준다.

사용: python3 theme_preview.py [resume.yaml] [-o 미리보기.png] [--presets neutral teal …]

- resume.yaml 을 주면 내 데이터(사용자 데이터 폴더의 profile)로, 안 주면 가상 인물 예제로 렌더한다.
- 고른 프리셋은 사용자 데이터 폴더의 theme.yaml 에 `preset: 이름` 으로 적는다.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
EXAMPLE = SCRIPTS.parent / "examples" / "hong-gildong"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resume_yaml", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--presets", nargs="*")
    args = ap.parse_args()
    if not args.resume_yaml:
        os.environ["JOB_APPLY_HOME"] = str(EXAMPLE / "data")  # 렌더에는 profile·rules 만 필요하다
    src = Path(args.resume_yaml or EXAMPLE / "application" / "resume.yaml").resolve()

    sys.path.insert(0, str(SCRIPTS))
    import yaml
    from PIL import Image, ImageDraw

    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # type: ignore

    import render_resume
    from pdf_base import colors, presets, render, set_theme

    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    names = args.presets or presets()
    tmp = Path(tempfile.mkdtemp(prefix="job-apply-themes-"))
    tiles = []
    for name in names:
        set_theme(name)
        pdf = render(render_resume.build_html(data), tmp / f"{name}.pdf", tmp / "_build", f"{name}.html")
        pix = pymupdf.open(pdf)[0].get_pixmap(dpi=60)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        bar = Image.new("RGB", (im.width, 28), "white")
        d = ImageDraw.Draw(bar)
        d.rectangle([8, 8, 20, 20], fill=colors()["accent"])
        d.text((28, 8), name, fill="black")
        tile = Image.new("RGB", (im.width, im.height + 28), "white")
        tile.paste(bar, (0, 0))
        tile.paste(im, (0, 28))
        tiles.append(tile)
    w, h = tiles[0].size
    cols = min(3, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols - 1) * 12, rows * h + (rows - 1) * 12), "#888888")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (w + 12), (i // cols) * (h + 12)))
    out = Path(args.out) if args.out else tmp / "theme_preview.png"
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
