#!/usr/bin/env python3
"""PDF 검증.

사용: python3 pdf_check.py <pdf> [--max-pages N] [--source final.md] [--html _build/resume.html]
                          [--forbid 회사A 회사B …] [--lang ko|en] [--sheet 미리보기.png] [--compare 이전.pdf]
                          [--json 결과.json]

실패 (하나라도 있으면 종료 코드 1)
- 쪽수: --max-pages 를 넘음 / 내용이 없는 빈 쪽
- 폰트: 포함(embed)되지 않은 폰트, 한글이 Pretendard 가 아닌 대체 폰트로 그려짐, 깨진 글자(U+FFFD)
- 누락: --source Markdown 의 문장('## [웹 답변]'·HUMANIZE-SUMMARY 제외)이나 --html 원본 HTML 의 글이 PDF 에 없음
- 금지어: --forbid 로 준 다른 회사명·이전 직무명이 남음
- 영문 문서(--lang en)에 한글이 남음
- 겹침: 서로 다른 줄의 글자가 포개짐 (예: 연락처 라벨과 값)
- 여백 넘침: 글이 좌우·아래 여백을 넘어감 (nowrap 긴 URL 등)
- 고아 제목: 쪽 맨 아래에 제목만 있고 본문은 다음 쪽에서 시작
- 비교: --compare PDF 와 텍스트·쪽수·픽셀이 다름 (엔진 회귀 확인)

경고 (종료 코드에 영향 없음)
- Pretendard 가 아닌 폰트 사용(한글 외), 줄 첫머리의 가운뎃점·쉼표·닫는 괄호, 마지막 쪽이 거의 빔

--sheet 는 모든 쪽을 이어 붙인 PNG 를 만든다. 자동 판정이 못 보는 것(어색한 줄바꿈, 빈 공간, 그림 품질)은
이 그림을 Read 로 열어 직접 본다.
"""
from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
import unicodedata
from collections import Counter

try:
    import pymupdf
except ImportError:  # 오래된 PyMuPDF
    import fitz as pymupdf  # type: ignore

MM = 72 / 25.4
WEB_PREFIX = "[웹 답변]"
HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")
LINE_START_BAD = tuple("·,.)]」』:;")
BOLD = re.compile(r"(Bold|Black|Heavy)", re.I)  # SemiBold 는 라벨·눈썹 글씨라 제목으로 보지 않는다
NON_PRETENDARD_OK = re.compile(r"(Menlo|SFMono|SF-Mono|Courier|Helvetica|Monaco|DejaVuSansMono|LiberationMono)", re.I)


# ── 쪽 안의 줄 ──────────────────────────────────────────────

def font_name(raw: str) -> str:
    raw = raw.split("+")[-1]
    return "Type3(시스템 대체 글꼴)" if raw.startswith("Type3") else raw


class Line:
    __slots__ = ("text", "x0", "y0", "x1", "y1", "size", "font", "bold", "mono", "footer", "spans")

    def __init__(self, line: dict):
        spans = [s for s in line["spans"] if s["text"]]
        self.spans = [(s["text"], font_name(s["font"])) for s in spans]
        self.text = "".join(s["text"] for s in spans)
        self.x0, self.y0, self.x1, self.y1 = line["bbox"]
        main = max(spans, key=lambda s: len(s["text"].strip()))
        self.size = round(max(s["size"] for s in spans), 2)
        self.font = font_name(main["font"])
        self.bold = bool(BOLD.search(self.font))
        self.mono = bool(NON_PRETENDARD_OK.search(self.font))
        self.footer = False

    @property
    def h(self):
        return self.y1 - self.y0


def page_lines(page, bottom_margin: float) -> list[Line]:
    out = []
    limit = page.rect.height - bottom_margin - 1
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            if not "".join(s["text"] for s in ln["spans"]).strip():
                continue
            x = Line(ln)
            x.footer = x.y0 >= limit
            out.append(x)
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def body_text(doc, bottom_margin: float) -> str:
    """바닥글을 뺀 전체 텍스트 (쪽 경계에서 나뉜 문장도 찾을 수 있게 이어 붙인다)."""
    parts = []
    for p in doc:
        limit = p.rect.height - bottom_margin - 1
        for b in p.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                if ln["bbox"][1] < limit:
                    parts.append("".join(s["text"] for s in ln["spans"]))
    return norm("".join(parts))


# ── 원문 ────────────────────────────────────────────────────

def source_sentences(md: str) -> list[str]:
    md = md.split("<!-- HUMANIZE-SUMMARY")[0]
    sents = []
    for blk in re.split(r"^## ", md, flags=re.M):
        if not blk.strip() or blk.startswith(WEB_PREFIX):
            continue
        head, _, body = blk.partition("\n")
        rail, _, headline = head.strip().partition(" — ")
        sents += [rail, headline] if headline else [rail]
        for para in body.split("\n\n"):
            sents += [s for s in re.split(r"(?<=[.!?다])\s+", para.strip()) if s]
    return [s for s in sents if s.strip()]


class _HtmlText(html.parser.HTMLParser):
    SKIP = {"style", "script", "title", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth and data.strip():
            self.chunks.append(data)


def html_chunks(path: str) -> list[str]:
    p = _HtmlText()
    with open(path, encoding="utf-8") as f:
        p.feed(f.read())
    return [c.strip() for c in p.chunks if len(norm(c)) >= 2]


# ── 레이아웃 판정 ───────────────────────────────────────────

def overlaps(lines: list[Line]) -> list[tuple[Line, Line]]:
    found = []
    body = [x for x in lines if not x.footer]
    for i, a in enumerate(body):
        for b in body[i + 1:]:
            ox = min(a.x1, b.x1) - max(a.x0, b.x0)
            oy = min(a.y1, b.y1) - max(a.y0, b.y0)
            if ox > 1.5 and oy > 0.35 * min(a.h, b.h):
                found.append((a, b))
    return found


def overflow(lines: list[Line], page, side: float, top: float) -> list[Line]:
    """본문 영역 밖으로 나간 줄. Chrome 은 본문 영역 밖 글자를 그리지 않고 잘라 내므로, 잘린 줄은
    오른쪽 끝이 본문 경계를 1pt 남짓 넘는 모양으로 남는다 (줄바꿈된 보통 줄은 경계 안에서 끝난다)."""
    w = page.rect.width
    return [x for x in lines if not x.footer and (x.x0 < side - 1 or x.x1 > w - side + 1 or x.y0 < top - 4)]


def orphan_heading(lines: list[Line], body_size: float) -> Line | None:
    """쪽의 마지막 덩어리가 제목(+제목에 붙은 작은 메타 줄)뿐이면 그 제목 줄을 돌려준다.

    제목: 굵은 글씨(Bold 이상)이고 본문 글자보다 10% 이상 큼. 메타 줄: 본문보다 작은 Pretendard 줄
    (날짜·회사명). 고정폭 칩 줄은 내용으로 본다. 메타 줄은 바로 위 줄과 붙어 있을 때만 건너뛴다.
    """
    body = sorted((x for x in lines if not x.footer), key=lambda x: (x.y1, x.x0))
    prev = None
    for x in reversed(body[-6:]):
        if prev is not None and prev.y0 - x.y1 > max(6.0, 1.2 * prev.h):
            return None  # 위 줄과 떨어져 있다 → 쪽 끝 덩어리가 끝났다
        if x.bold and x.size >= body_size * 1.10:
            return x
        if x.size < body_size * 0.95 and not x.mono and not x.bold:
            prev = x
            continue
        return None
    return None


def line_start_punct(lines: list[Line]) -> list[Line]:
    bad = []
    body = [x for x in lines if not x.footer]
    for x in body:
        if not x.text.lstrip().startswith(LINE_START_BAD):
            continue
        # 같은 줄 왼쪽에 바로 붙은 조각이 있으면 줄 첫머리가 아니다 (PDF 가 한 줄을 여러 조각으로 나눈 경우)
        if any(abs(o.y1 - x.y1) < 1.2 and 0 <= x.x0 - o.x1 < 8 for o in body if o is not x):
            continue
        bad.append(x)
    return bad


def last_page_fill(lines: list[Line], page, top: float, bottom: float) -> float:
    body = [x for x in lines if not x.footer]
    if not body:
        return 0.0
    usable = page.rect.height - top - bottom
    return max(0.0, min(1.0, (max(x.y1 for x in body) - top) / usable))


# ── 기타 ────────────────────────────────────────────────────

def contact_sheet(doc, path: str, dpi: int = 80):
    from PIL import Image

    ims = []
    for p in doc:
        pix = p.get_pixmap(dpi=dpi)
        ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    cols = min(4, len(ims))
    rows = (len(ims) + cols - 1) // cols
    w, h = ims[0].size
    sheet = Image.new("RGB", (cols * w + (cols - 1) * 16, rows * h + (rows - 1) * 16), "#888888")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * (w + 16), (i // cols) * (h + 16)))
    sheet.save(path)


def compare(a, b) -> list[str]:
    from PIL import Image, ImageChops

    problems = []
    if a.page_count != b.page_count:
        problems.append(f"쪽수 다름: {a.page_count} vs {b.page_count}")
    if norm("".join(p.get_text() for p in a)) != norm("".join(p.get_text() for p in b)):
        problems.append("텍스트 다름")
    for i in range(min(a.page_count, b.page_count)):
        pa, pb = a[i].get_pixmap(dpi=50), b[i].get_pixmap(dpi=50)
        ia = Image.frombytes("RGB", (pa.width, pa.height), pa.samples)
        ib = Image.frombytes("RGB", (pb.width, pb.height), pb.samples)
        if ia.size != ib.size or ImageChops.difference(ia, ib).getbbox():
            problems.append(f"{i + 1}쪽 픽셀 다름")
    return problems


def short(s: str, n: int = 40) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def check(args) -> dict:
    doc = pymupdf.open(args.pdf)
    top, side, bottom = (float(v) * MM for v in args.margins.split(","))
    fails, warns, info = [], [], {}

    info["pages"] = doc.page_count
    if args.max_pages and doc.page_count > args.max_pages:
        fails.append(f"쪽수 {doc.page_count} > {args.max_pages}")

    pages = [page_lines(p, bottom) for p in doc]
    sizes = Counter()
    for lines in pages:
        for x in lines:
            if not x.footer:
                sizes[x.size] += len(x.text)
    body_size = sizes.most_common(1)[0][0] if sizes else 9.0
    info["body_size"] = body_size

    # 폰트
    fonts = {}
    for p in doc:
        for f in p.get_fonts():
            name = f[3].split("+")[-1]
            if name:
                fonts[name] = f[1]
    info["fonts"] = sorted(fonts)
    for name, ext in fonts.items():
        if ext in ("n/a", ""):
            fails.append(f"폰트가 PDF 에 포함되지 않음: {name}")
    hangul_fallback: dict[str, list[str]] = {}
    for lines in pages:
        for x in lines:
            for font in {f for t, f in x.spans if HANGUL.search(t) and not f.startswith("Pretendard")}:
                hangul_fallback.setdefault(font, []).append(x.text.strip())
    for name, where in hangul_fallback.items():
        fails.append(f"한글이 대체 폰트 {name} 로 그려짐: '{short(where[0], 30)}' 등 {len(where)}곳 — font-family 에 Pretendard 가 있는지 확인")
    odd = [f for f in fonts if not f.startswith("Pretendard") and not NON_PRETENDARD_OK.search(f)
           and not f.startswith("Type3") and f not in hangul_fallback]
    if odd:
        warns.append(f"Pretendard 가 아닌 폰트: {odd}")
    if any("�" in x.text for lines in pages for x in lines):
        fails.append("깨진 글자(U+FFFD)가 있음")

    # 쪽별 레이아웃
    for i, (p, lines) in enumerate(zip(doc, pages), start=1):
        body = [x for x in lines if not x.footer]
        if not body and not p.get_images():
            fails.append(f"{i}쪽: 빈 쪽")
            continue
        for a, b in overlaps(lines)[:5]:
            fails.append(f"{i}쪽: 글자 겹침 '{short(a.text, 20)}' ↔ '{short(b.text, 20)}'")
        for x in overflow(lines, p, side, top)[:5]:
            fails.append(f"{i}쪽: 여백 넘침·잘림 '{short(x.text, 30)}' (x {x.x0:.1f}–{x.x1:.1f}pt, 본문 영역 {side:.1f}–{p.rect.width - side:.1f}pt)")
        if i < doc.page_count:
            h = orphan_heading(lines, body_size)
            if h:
                fails.append(f"{i}쪽: 고아 제목 '{short(h.text, 30)}' — 쪽 끝에 제목만 있고 본문은 다음 쪽")
        for x in line_start_punct(lines)[:5]:
            warns.append(f"{i}쪽: 줄 첫머리 문장부호 '{short(x.text, 30)}'")
    if doc.page_count > 1:
        fill = last_page_fill(pages[-1], doc[-1], top, bottom)
        info["last_page_fill"] = round(fill, 2)
        if fill < args.min_last_fill:
            warns.append(f"마지막 쪽이 {fill:.0%}만 참 — 조금 줄이면 {doc.page_count - 1}쪽에 들어감")

    # 누락
    full = body_text(doc, bottom)
    if args.source:
        sents = source_sentences(open(args.source, encoding="utf-8").read())
        missing = [s for s in sents if norm(s) not in full]
        info["source"] = {"sentences": len(sents), "missing": len(missing)}
        for s in missing:
            fails.append(f"원문 문장 누락: {short(s, 50)}")
    if args.html:
        chunks = html_chunks(args.html)
        missing = [c for c in chunks if norm(c) not in full]
        info["html"] = {"chunks": len(chunks), "missing": len(missing)}
        for c in missing[:10]:
            fails.append(f"HTML 글 누락(잘림·가림): {short(c, 50)}")

    raw = "".join(p.get_text() for p in doc)
    for word in args.forbid:
        if word and word in raw:
            fails.append(f"금지어 발견: {word}")
    if args.lang == "en":
        ko = sorted({m.group(0) for x in (ln for lines in pages for ln in lines if not ln.footer)
                     for m in re.finditer(r"\S*[가-힣]\S*", x.text)})
        if ko:
            fails.append(f"영문 문서에 한글: {', '.join(ko[:8])}")

    if args.sheet:
        contact_sheet(doc, args.sheet)
        info["sheet"] = args.sheet
    if args.compare:
        problems = compare(pymupdf.open(args.compare), doc)
        info["compare"] = problems or "동일"
        fails += problems

    return {"pdf": args.pdf, "ok": not fails, "fails": fails, "warns": warns, "info": info}


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--source", help="윤문 확정본 Markdown (자기소개서·경력기술서)")
    ap.add_argument("--html", help="렌더러가 _build 에 남긴 HTML — 화면에 있어야 할 글이 PDF 에 모두 있는지")
    ap.add_argument("--forbid", nargs="*", default=[])
    ap.add_argument("--lang", choices=["ko", "en"], default="ko")
    ap.add_argument("--margins", default="14,16,15", help="위,좌우,아래 여백(mm) — pdf_base.page_css 와 같게")
    ap.add_argument("--min-last-fill", type=float, default=0.12)
    ap.add_argument("--sheet")
    ap.add_argument("--compare")
    ap.add_argument("--json", help="결과를 JSON 파일로도 저장")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    r = check(args)
    i = r["info"]
    print(f"쪽수: {i['pages']}" + (f" (마지막 쪽 {i['last_page_fill']:.0%})" if "last_page_fill" in i else ""))
    print("폰트:", ", ".join(i["fonts"]))
    if "source" in i:
        print(f"원문 대조: 문장 {i['source']['sentences']}개 중 누락 {i['source']['missing']}개")
    if "html" in i:
        print(f"HTML 대조: 글 조각 {i['html']['chunks']}개 중 누락 {i['html']['missing']}개")
    if "sheet" in i:
        print(f"미리보기: {i['sheet']}")
    if "compare" in i:
        print("비교:", "동일" if i["compare"] == "동일" else "; ".join(i["compare"]))
    for w in r["warns"]:
        print("경고:", w)
    for f in r["fails"]:
        print("실패:", f)
    print("결과:", "통과" if r["ok"] else "실패")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
