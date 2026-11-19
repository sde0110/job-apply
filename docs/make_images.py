#!/usr/bin/env python3
"""README 그림 만들기 — 가상 인물(홍길동) 예제로 PDF 를 만들어 docs/images/ 에 PNG 로 저장한다.

사용: python3 docs/make_images.py
- pdf-samples.png : 이력서 · 자기소개서 · 영문 1쪽 이력서 (각 쪽 위쪽)
- themes.png      : 테마 프리셋 5종으로 그린 이력서 윗부분
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "job-apply"
SCRIPTS = SKILL / "scripts"
OUT = ROOT / "docs" / "images"
BG = (0.945, 0.953, 0.961)
SHADOW = (0.82, 0.84, 0.86)


def compose(items, clip_ratio, scale, gap, pad, dpi, out_path, labels=None):
    """items: [(pdf 경로, 쪽 번호)] — 각 쪽의 위쪽 clip_ratio 만큼을 가로로 나란히 놓는다."""
    import pymupdf

    A4 = pymupdf.paper_rect("a4")
    clip = pymupdf.Rect(0, 0, A4.width, A4.height * clip_ratio)
    w, h = clip.width * scale, clip.height * scale
    label_h = 20 if labels else 0
    doc = pymupdf.open()
    page = doc.new_page(width=pad * 2 + len(items) * w + (len(items) - 1) * gap, height=pad * 2 + h + label_h)
    page.draw_rect(page.rect, color=None, fill=BG)
    for i, (pdf, pno) in enumerate(items):
        x, y = pad + i * (w + gap), pad + label_h
        if labels:
            page.insert_text((x + 2, pad + 12), labels[i][0], fontsize=9.5, fontname="helv", color=(0.25, 0.27, 0.3))
            page.draw_rect(pymupdf.Rect(x + w - 12, pad + 3, x + w - 2, pad + 13), color=None, fill=labels[i][1])
        page.draw_rect(pymupdf.Rect(x + 2, y + 3, x + w + 2, y + h + 3), color=None, fill=SHADOW)
        page.draw_rect(pymupdf.Rect(x, y, x + w, y + h), color=None, fill=(1, 1, 1))
        with pymupdf.open(pdf) as src:
            page.show_pdf_page(pymupdf.Rect(x, y, x + w, y + h), src, pno, clip=clip)
    page.get_pixmap(dpi=dpi).save(out_path)
    print(out_path, f"{Path(out_path).stat().st_size // 1024}KB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="job-apply-images-"))
    r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "run_example.py"), str(work)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stdout + r.stderr)
    app = next((work / "home" / "applications").iterdir())
    resume = next(app.glob("*_이력서.pdf"))
    letter = next(app.glob("*_자기소개서.pdf"))
    resume_en = next(app.glob("*_Resume.pdf"))
    compose([(resume, 0), (letter, 0), (resume_en, 0)], clip_ratio=0.68, scale=0.62, gap=22, pad=26, dpi=150,
            out_path=OUT / "pdf-samples.png")

    os.environ["JOB_APPLY_HOME"] = str(work / "home")
    sys.path.insert(0, str(SCRIPTS))
    import yaml

    import render_resume
    from pdf_base import colors, presets, render, set_theme

    data = yaml.safe_load((app / "resume.yaml").read_text(encoding="utf-8"))
    items, labels = [], []
    for name in presets():
        set_theme(name)
        pdf = render(render_resume.build_html(data), work / f"theme_{name}.pdf", work / "_build", f"theme_{name}.html")
        items.append((pdf, 0))
        hexc = colors()["accent"]
        labels.append((name, tuple(int(hexc[k:k + 2], 16) / 255 for k in (1, 3, 5))))
    order = ["neutral", "teal", "forest", "burgundy", "mono"]
    idx = sorted(range(len(items)), key=lambda i: order.index(labels[i][0]) if labels[i][0] in order else 99)
    compose([items[i] for i in idx], clip_ratio=0.5, scale=0.42, gap=14, pad=20, dpi=150,
            out_path=OUT / "themes.png", labels=[labels[i] for i in idx])


if __name__ == "__main__":
    main()
