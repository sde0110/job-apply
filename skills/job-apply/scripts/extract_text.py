#!/usr/bin/env python3
"""PDF / DOCX / MD / TXT 에서 텍스트를 뽑는다. 이미지·스캔본은 Read 도구로 직접 본다.

사용: python3 extract_text.py <파일> [--pages 1-3]
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventory import resolve  # noqa: E402

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".heic", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


def parse_pages(spec: str | None, total: int) -> list[int]:
    if not spec:
        return list(range(total))
    out: list[int] = []
    for chunk in spec.split(","):
        if "-" in chunk:
            a, b = chunk.split("-")
            out.extend(range(int(a) - 1, min(int(b), total)))
        else:
            out.append(int(chunk) - 1)
    return [p for p in out if 0 <= p < total]


def pdf_text(path: str, pages: str | None) -> str:
    import pymupdf

    doc = pymupdf.open(path)
    parts = []
    for i in parse_pages(pages, doc.page_count):
        parts.append(f"--- page {i + 1}/{doc.page_count} ---\n{doc[i].get_text().strip()}")
    text = "\n\n".join(parts)
    if len(text.replace("-", "").split()) < 10 * max(1, len(parts)) // 2:
        text += "\n\n[경고] 텍스트가 거의 없습니다. 스캔본일 수 있으니 Read 도구(pages 지정)로 페이지 이미지를 직접 확인하세요."
    return text


def docx_text(path: str) -> str:
    import docx

    d = docx.Document(path)
    out = [p.text for p in d.paragraphs if p.text.strip()]
    for ti, table in enumerate(d.tables, 1):
        out.append(f"\n--- table {ti} ---")
        for row in table.rows:
            cells = []
            for c in row.cells:
                t = c.text.strip().replace("\n", " / ")
                if not cells or cells[-1] != t:  # 병합 셀 중복 제거
                    cells.append(t)
            out.append(" | ".join(cells))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--pages")
    args = ap.parse_args()

    path = resolve(args.file)
    if not path:
        print(f"파일을 찾지 못함: {args.file}", file=sys.stderr)
        return 1
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        print(f"[이미지] Read 도구로 직접 확인하세요: {path}")
        return 0
    if ext == ".pdf":
        print(pdf_text(path, args.pages))
    elif ext == ".docx":
        print(docx_text(path))
    elif ext in {".doc", ".rtf", ".odt", ".pages"}:
        print(subprocess.run(["textutil", "-convert", "txt", "-stdout", path], capture_output=True, text=True).stdout)
    elif ext == ".hwp":
        print("[HWP] 직접 추출할 수 없습니다. 같은 내용의 PDF/DOCX 를 찾거나 사용자에게 변환을 요청하세요.")
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            print(f.read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
