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

    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # type: ignore

    import render_resume
    from pdf_base import colors, presets, render, set_theme

    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    names = args.presets or presets()
    tmp = Path(tempfile.mkdtemp(prefix="job-apply-themes-"))
    pdfs = []
    for name in names:
        set_theme(name)
        pdf = render(render_resume.build_html(data), tmp / f"{name}.pdf", tmp / "_build", f"{name}.html")
        pdfs.append((name, colors()["accent"], pdf))

    # 1쪽씩 새 PDF 한 장에 나란히 놓고(벡터 그대로) 이름표를 단 뒤 PNG 로 굽는다
    A4 = pymupdf.paper_rect("a4")
    scale, label_h, gap = 0.5, 22, 12
    tw, th = A4.width * scale, A4.height * scale + label_h
    cols = min(3, len(pdfs))
    rows = (len(pdfs) + cols - 1) // cols
    out = pymupdf.open()
    page = out.new_page(width=cols * tw + (cols - 1) * gap, height=rows * th + (rows - 1) * gap)
    page.draw_rect(page.rect, color=None, fill=(0.53, 0.53, 0.53))
    for i, (name, accent, pdf) in enumerate(pdfs):
        x, y = (i % cols) * (tw + gap), (i // cols) * (th + gap)
        page.draw_rect(pymupdf.Rect(x, y, x + tw, y + th), color=None, fill=(1, 1, 1))
        rgb = tuple(int(accent[k:k + 2], 16) / 255 for k in (1, 3, 5))
        page.draw_rect(pymupdf.Rect(x + 8, y + 7, x + 18, y + 17), color=None, fill=rgb)
        page.insert_text((x + 24, y + 16), name, fontsize=10, fontname="helv")
        with pymupdf.open(pdf) as src_doc:
            page.show_pdf_page(pymupdf.Rect(x, y + label_h, x + tw, y + th), src_doc, 0)
    target = Path(args.out) if args.out else tmp / "theme_preview.png"
    page.get_pixmap(dpi=120).save(target)
    print(target)


if __name__ == "__main__":
    main()
