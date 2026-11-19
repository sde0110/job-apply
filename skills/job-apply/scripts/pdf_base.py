"""PDF 공통 엔진: Pretendard 폰트, 테마 색, HTML 조각, Chrome 헤드리스 인쇄.

render_resume.py / render_letter.py / render_portfolio.py 가 이 모듈을 쓴다.
색은 테마 프리셋(assets/themes/*.yaml, 기본 neutral) 위에 사용자 데이터 theme.yaml 의 colors 를 덮어쓴다.
연락처·이름은 profile.yaml 에서 온다. 문서 언어(ko/en)에 따라 라벨·날짜 형식이 바뀐다.
"""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ASSETS, profile, theme  # noqa: E402

import yaml  # noqa: E402

THEMES = ASSETS / "themes"
_theme_override: str | None = None  # 렌더러의 --theme 옵션


def e(s) -> str:
    """HTML 이스케이프 + ' · ' 앞 줄바꿈 금지 (줄이 가운뎃점으로 시작하지 않게)."""
    return html.escape(str(s)).replace(" · ", "\u00a0· ")


def presets() -> list[str]:
    return sorted(p.stem for p in THEMES.glob("*.yaml"))


def set_theme(preset: str | None):
    """렌더러의 --theme: 사용자 theme.yaml 대신 이 프리셋만 쓴다 (미리보기·비교용)."""
    global _theme_override
    if preset and preset not in presets():
        sys.exit(f"없는 테마 프리셋: {preset} (가능: {', '.join(presets())})")
    _theme_override = preset


def colors() -> dict:
    t = {"preset": _theme_override} if _theme_override else theme()
    preset = t.get("preset") or "neutral"
    path = THEMES / f"{preset}.yaml"
    if not path.exists():
        sys.exit(f"theme.yaml 의 preset '{preset}' 이 없습니다 (가능: {', '.join(presets())})")
    base = yaml.safe_load(path.read_text(encoding="utf-8"))["colors"]
    return {**base, **(t.get("colors") or {})}


LABELS = {
    "ko": {"present": "현재", "experience": "경력", "skills": "기술", "education": "학력 · 교육 · 자격", "awards": "수상",
           "resume": "이력서", "hours": "{h}시간 수료", "preferred": "우대", "requirements": "자격요건과 경험"},
    "en": {"present": "Present", "experience": "Experience", "skills": "Skills", "education": "Education · Training · Certifications",
           "awards": "Awards", "resume": "Resume", "hours": "{h} hours", "preferred": "Preferred", "requirements": "Requirements and evidence"},
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def ym(s, lang: str = "ko") -> str:
    """'2024-03-04' → '2024.03' (영문: 'Mar 2024'), 비어 있으면 '현재'/'Present'."""
    if not s:
        return LABELS[lang]["present"]
    s = str(s)
    if lang == "en" and len(s) >= 7:
        return f"{MONTHS[int(s[5:7]) - 1]} {s[:4]}"
    return s[:7].replace("-", ".")

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

FONTS = "\n".join(
    f"@font-face{{font-family:'Pretendard';src:url('Pretendard-{n}.woff2') format('woff2');font-weight:{w};font-display:block}}"
    for n, w in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800)]
)

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'Pretendard',-apple-system,sans-serif;color:var(--body);font-size:8.7pt;line-height:1.56;
  letter-spacing:-0.012em;word-break:keep-all;overflow-wrap:break-word;font-feature-settings:"ss06"}
a{color:inherit;text-decoration:none}
ul{list-style:none}
.num{font-variant-numeric:tabular-nums;letter-spacing:0}

/* header */
.hd{display:grid;grid-template-columns:1fr 63mm;gap:8mm;align-items:end;padding-bottom:5mm;border-bottom:1.4pt solid var(--ink)}
.eyebrow{font-size:7.8pt;font-weight:600;letter-spacing:.06em;color:var(--accent)}
.hd h1{margin-top:1.2mm;font-size:23pt;line-height:1.15;font-weight:800;letter-spacing:-0.02em;color:var(--ink)}
.hd h1 small{margin-left:2.2mm;font-size:10pt;font-weight:500;letter-spacing:0;color:var(--meta)}
.lede{margin-top:2.4mm;font-size:8.9pt;line-height:1.62;color:var(--sub)}
.contact{display:grid;row-gap:.9mm;font-size:8pt}
.contact div{display:grid;grid-template-columns:18.5mm 1fr}
.contact dt{font-size:6.9pt;font-weight:600;letter-spacing:.05em;color:var(--faint);padding-top:.25mm}
.contact dd{color:var(--ink);font-weight:500}
"""

RESUME_CSS = """
.sec{margin-top:5.2mm}
.sec>h2{display:flex;align-items:center;gap:3mm;margin-bottom:2.6mm;font-size:10.4pt;font-weight:800;color:var(--ink);break-after:avoid}
.sec>h2::after{content:"";flex:1;height:.6pt;background:var(--line)}
.sec>h2 em{font-style:normal;font-size:7.6pt;font-weight:500;color:var(--meta);margin-left:-1mm}

.entry{display:grid;grid-template-columns:21mm 1fr;column-gap:5mm;margin-bottom:3.4mm}
.when{font-size:7.8pt;line-height:1.5;color:var(--meta);padding-top:.6mm}
.when span{display:block}
.when span::before{content:"– "}
.what h3{font-size:10pt;font-weight:700;color:var(--ink);line-height:1.4;break-after:avoid}
.what h3+.sub,.what .co-stack{break-after:avoid}
.what h3 small{margin-left:1.6mm;font-size:8.3pt;font-weight:500;color:var(--sub)}
.what .sub{display:flex;justify-content:space-between;gap:4mm;margin-top:.3mm;font-size:7.9pt;color:var(--meta)}
.what .sub a{color:var(--accent);font-weight:500;white-space:nowrap}
.co-stack{margin-top:.6mm;font-size:7.7pt;color:var(--meta)}

.items{margin-top:2mm;border-left:.8pt solid var(--hair);padding-left:3.2mm}
.item{margin-bottom:1.9mm;break-inside:avoid}
.item h4{font-size:8.8pt;font-weight:700;color:var(--ink)}
.item h4 small{margin-left:1.2mm;font-size:7.4pt;font-weight:500;color:var(--meta)}
.item p{margin-top:.2mm;color:var(--body)}
.item .num-hl{font-weight:700;color:var(--ink)}

.dots{margin-top:1.3mm}
.dots li{position:relative;padding-left:3.2mm;margin-bottom:.7mm}
.dots li::before{content:"";position:absolute;left:.2mm;top:.6em;width:1.25mm;height:1.25mm;border-radius:50%;background:var(--dot)}

.chips{display:flex;flex-wrap:wrap;gap:1mm;margin-top:1.5mm}
.chips li{padding:.15mm 1.5mm;border-radius:.8mm;background:var(--chip);font-family:ui-monospace,'SF Mono',Menlo,'Pretendard',monospace;
  font-size:6.6pt;letter-spacing:0;color:var(--chip-ink)}
.award{margin-top:.8mm;font-size:8pt;font-weight:600;color:var(--warm)}
.entry.compact{margin-bottom:2.6mm}

.skills{display:grid;row-gap:1.1mm}
.skills div{display:grid;grid-template-columns:21mm 1fr;column-gap:5mm}
.skills dt{font-size:7.9pt;font-weight:700;color:var(--ink);padding-top:.1mm}
.skills dd{color:var(--body)}
.skills dd i{font-style:normal;color:var(--meta)}

.rows li{display:grid;grid-template-columns:21mm 1fr;column-gap:5mm;padding:.9mm 0;border-bottom:.5pt solid var(--hair);break-inside:avoid}
.rows li:last-child{border-bottom:0}
.rows .when{padding-top:.1mm}
.rows b{font-weight:600;color:var(--ink)}
.rows i{font-style:normal;color:var(--meta)}
.rows .prize{color:var(--warm);font-weight:700}
"""

RESUME_COMPACT_CSS = """
/* layout: compact — 1쪽 이력서 */
body{font-size:8.2pt;line-height:1.46}
.hd{padding-bottom:3.6mm}
.hd h1{font-size:19pt}
.lede{margin-top:1.6mm;font-size:8.3pt;line-height:1.5}
.sec{margin-top:3.6mm}
.sec>h2{margin-bottom:1.8mm;font-size:9.8pt}
.entry{margin-bottom:2.4mm}
.entry.compact{margin-bottom:1.8mm}
.what h3{font-size:9.4pt}
.items{margin-top:1.3mm}
.item{margin-bottom:1.2mm}
.item h4{font-size:8.3pt}
.dots{margin-top:.8mm}
.dots li{margin-bottom:.3mm}
.chips{margin-top:1mm}
.skills{row-gap:.6mm}
.rows li{padding:.5mm 0}
"""

LETTER_CSS = """
.ls{display:grid;grid-template-columns:34mm 1fr;column-gap:7mm;padding-top:5.4mm;margin-top:5.4mm;border-top:.6pt solid var(--line)}
.ls:first-of-type{border-top:0;margin-top:1mm}
.rail h2{font-size:9.6pt;line-height:1.42;font-weight:800;color:var(--ink)}
.rail p{margin-top:1mm;font-size:7.4pt;line-height:1.45;color:var(--meta)}
.rail p .seg{white-space:nowrap}
.rail .bar{display:block;width:6mm;height:1.6pt;margin-bottom:2mm;background:var(--accent)}
.prose{font-size:9.45pt;line-height:1.8;color:var(--body)}
.prose h3{break-after:avoid;margin-bottom:1.8mm;font-size:10.6pt;line-height:1.5;font-weight:700;color:var(--ink);letter-spacing:-0.02em}
.prose p+p{margin-top:2.6mm}
.req li{display:grid;grid-template-columns:41mm 1fr;column-gap:4mm;padding:1.5mm 0;border-bottom:.5pt solid var(--hair);break-inside:avoid;font-size:8.5pt;line-height:1.58}
.req li:first-child{padding-top:0}
.req li:last-child{border-bottom:0}
.req b{font-weight:700;color:var(--ink)}
.req span{color:var(--sub)}
.req .opt{display:block;font-size:7.2pt;font-weight:600;letter-spacing:.04em;color:var(--accent)}
"""

PORTFOLIO_CSS = """
.pg{break-before:page}
.pg.cover{display:flex;flex-direction:column;min-height:262mm}
.pg:first-child{break-before:auto}
.ph{display:grid;grid-template-columns:1fr auto;column-gap:6mm;align-items:end;padding-bottom:4mm;margin-bottom:5.5mm;border-bottom:1.3pt solid var(--ink)}
.ph h1{margin-top:1.3mm;font-size:19pt;line-height:1.25;font-weight:800;letter-spacing:-0.025em;color:var(--ink)}
.ph h1 small{margin-left:1.5mm;font-size:11pt;font-weight:600;letter-spacing:-0.01em;color:var(--sub)}
.ph .meta{margin-top:1.5mm;font-size:8.3pt;color:var(--meta)}
.ph .meta i{font-style:normal;color:var(--faint);margin:0 1.6mm}
.ph .detail{font-size:7.8pt;font-weight:600;color:var(--accent);white-space:nowrap;padding-bottom:.4mm}

.metric{border-left:2.4pt solid var(--accent);background:var(--tint);padding:3.2mm 4.5mm;margin-bottom:5mm}
.metric b{display:block;font-size:15pt;line-height:1.3;font-weight:800;letter-spacing:-0.02em;color:var(--ink)}
.metric span{display:block;margin-top:.8mm;font-size:8.4pt;color:var(--sub)}
.intro{font-size:9.6pt;line-height:1.82;color:var(--body);margin-bottom:5mm}

figure{margin:0 0 5mm}
figure img{display:block;margin:0 auto;max-width:100%;object-fit:contain;border:.6pt solid var(--line);border-radius:1.5mm}
figcaption{margin-top:1.8mm;font-size:7.6pt;color:var(--meta);text-align:center}

.blk{display:grid;grid-template-columns:32mm 1fr;column-gap:7mm;padding:4.2mm 0;border-top:.6pt solid var(--line)}
.blk h2{font-size:9.3pt;line-height:1.45;font-weight:800;color:var(--ink)}
.blk h2 em{display:block;margin-bottom:.6mm;font-style:normal;font-size:7.4pt;font-weight:600;letter-spacing:.03em;color:var(--accent)}
.blk p{font-size:9.45pt;line-height:1.82}

.flow{display:flex;align-items:stretch;gap:1.6mm;margin:0 0 5mm}
.flow li{flex:1;padding:2.6mm 3.2mm;border-radius:1.5mm;background:var(--tint2);font-size:8.6pt;line-height:1.45;font-weight:700;color:var(--ink)}
.flow li small{display:block;font-size:7.9pt;font-weight:500;color:var(--sub)}
.flow li b{display:block;margin-bottom:.6mm;font-size:6.8pt;font-weight:600;color:var(--accent);font-variant-numeric:tabular-nums}
.flow .arr{flex:0 0 auto;align-self:center;padding:0;background:none;color:var(--faint);font-weight:500}

.foot{margin-top:6mm}
.award{font-size:9pt;font-weight:700;color:var(--warm);margin-bottom:2mm}
.chips{display:flex;flex-wrap:wrap;gap:1mm}
.chips li{padding:.2mm 1.6mm;border-radius:.8mm;background:var(--chip);font-family:ui-monospace,'SF Mono',Menlo,'Pretendard',monospace;font-size:6.8pt;letter-spacing:0;color:var(--chip-ink)}
.links{display:flex;gap:5mm;font-size:8.2pt;font-weight:600;color:var(--accent);margin-top:2mm}

.split{display:grid;grid-template-columns:86mm 1fr;column-gap:8mm;align-items:start}
.split figure{margin:0}
.sub3 h3{font-size:10pt;font-weight:700;color:var(--ink);line-height:1.45}
.sub3 p{margin:1.4mm 0 6mm;font-size:9.4pt;line-height:1.82}

.part{margin-bottom:2mm}
.part h2{display:flex;align-items:baseline;gap:2.4mm;margin-bottom:2.6mm;font-size:11.5pt;font-weight:800;color:var(--ink)}
.part h2 span{font-size:7.6pt;font-weight:600;letter-spacing:.02em;padding:.4mm 1.8mm;border-radius:.8mm;background:var(--soft);color:var(--accent)}
.part .txt{font-size:9.5pt;line-height:1.82;margin-bottom:4.5mm}
.divider{height:.6pt;background:var(--line);margin:3mm 0 6mm}

/* cover */
.cover h1{font-size:34pt;font-weight:800;letter-spacing:-0.03em;color:var(--ink);line-height:1.1;margin-top:2mm}
.cover .role{margin-top:2.5mm;font-size:10.5pt;font-weight:600;color:var(--sub)}
.cover .head{padding-bottom:7mm;border-bottom:1.3pt solid var(--ink)}
.cover .claim{margin-top:9mm;font-size:16pt;line-height:1.45;font-weight:700;letter-spacing:-0.025em;color:var(--ink)}
.cover .claim-p{margin-top:3mm;font-size:9.8pt;line-height:1.82;color:var(--sub);max-width:150mm}
.cv{margin-top:9mm}
.cv h2,.toc h2{font-size:8pt;font-weight:700;letter-spacing:.06em;color:var(--accent);margin-bottom:2mm}
.rows li{display:grid;grid-template-columns:30mm 1fr;column-gap:6mm;padding:1.6mm 0;border-bottom:.5pt solid var(--hair);font-size:9pt}
.rows li:last-child{border-bottom:0}
.rows li.plain{display:block}
.rows .when{font-size:8pt;color:var(--meta);padding-top:.3mm}
.rows b{font-weight:700;color:var(--ink)}
.rows i{font-style:normal;color:var(--meta)}
.toc{margin-top:9mm}
.toc li{display:grid;grid-template-columns:16mm 1fr;column-gap:6mm;padding:2.4mm 0;border-top:.5pt solid var(--line)}
.toc li .no{font-size:13pt;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums;letter-spacing:-0.01em;line-height:1.2}
.toc li b{display:block;font-size:10pt;color:var(--ink)}
.toc li span{font-size:8.4pt;color:var(--meta)}
.cover .contact-line{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;padding-top:5mm;border-top:.6pt solid var(--line);font-size:8.6pt;color:var(--ink)}
.cover .contact-line a.site{font-weight:600;color:var(--accent)}

/* appendix */
.ap h2{font-size:8pt;font-weight:700;letter-spacing:.06em;color:var(--accent);margin:6mm 0 2mm}
.ap .paper{padding:3.6mm 4.5mm;background:var(--tint);border-left:2.4pt solid var(--accent)}
.ap .paper b{display:block;font-size:10.5pt;color:var(--ink)}
.ap .paper p{margin-top:1.2mm;font-size:9pt;line-height:1.75}
.ap .rows li{grid-template-columns:22mm 1fr}
.xp li{display:grid;grid-template-columns:62mm 1fr;column-gap:4mm;padding:1.6mm 0;border-bottom:.5pt solid var(--hair);font-size:8.8pt}
.xp li:last-child{border-bottom:0}
.xp a{font-weight:700;color:var(--ink)}
.xp a::after{content:" ↗";color:var(--accent)}
.xp span{color:var(--sub)}
"""


def root_css() -> str:
    return ":root{" + "".join(f"--{k}:{v};" for k, v in colors().items()) + "}\n"


def page_css(label: str, lang: str = "ko") -> str:
    name = profile()["name"]["en" if lang == "en" else "ko"]
    foot = colors().get("foot", "#a3a9b2")
    return f"""
@page{{size:A4;margin:14mm 16mm 15mm;
  @bottom-left{{content:"{name} · {label}";font-family:'Pretendard';font-size:6.8pt;color:{foot};letter-spacing:.02em}}
  @bottom-right{{content:counter(page) " / " counter(pages);font-family:'Pretendard';font-size:6.8pt;color:{foot}}}
}}
"""


def contact_html() -> str:
    p = profile()
    links = p.get("links", {})
    rows = [("PHONE", e(p["contact"]["phone"]), True),
            ("EMAIL", f'<a href="mailto:{e(p["contact"]["email"])}">{e(p["contact"]["email"])}</a>', False)]
    for key, label in (("github", "GITHUB"), ("portfolio", "PORTFOLIO")):
        if links.get(key):
            url = links[key]
            rows.append((label, f'<a href="{e(url)}">{e(url.replace("https://", "").replace("http://", ""))}</a>', False))
    body = "".join(
        f'<div><dt>{k}</dt><dd class="num">{v}</dd></div>' if num else f"<div><dt>{k}</dt><dd>{v}</dd></div>"
        for k, v, num in rows
    )
    return f'\n<dl class="contact">\n{body}\n</dl>\n'


def doc(title: str, label: str, css: str, body: str, lang: str = "ko") -> str:
    author = e(profile()["name"]["en" if lang == "en" else "ko"])
    return f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>
<meta name="author" content="{author}">
<style>{FONTS}{page_css(label, lang)}{root_css()}{BASE_CSS}{css}</style></head>
<body>{body}</body></html>"""


def chips(items) -> str:
    return '<ul class="chips">' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def when(a, b=None) -> str:
    if b is None:
        return f'<div class="when num">{e(a)}</div>'
    return f'<div class="when num">{e(a)}<span>{e(b)}</span></div>'


def link(path: str) -> str:
    return f'<a href="https://{e(path)}">{e(path)}</a>'


def meta_line(text: str) -> str:
    """'회사 · 팀(기여도 40%) · 2026.06–08' 같은 메타 줄: 짧은 조각은 줄바꿈으로 쪼개지 않고 가운뎃점 뒤에서만 바꾼다."""
    segs = [html.escape(x) for x in str(text).split(" · ")]
    segs = [f'<span class="seg">{x}</span>' if len(x) <= 14 else x for x in segs]
    return "\u00a0· ".join(segs)


def section(rail, rail_meta, inner) -> str:
    meta = f"<p>{meta_line(rail_meta)}</p>" if rail_meta else ""
    return f'<section class="ls"><div class="rail"><span class="bar"></span><h2>{e(rail)}</h2>{meta}</div><div class="prose">{inner}</div></section>'


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if not c:
            continue
        path = shutil.which(c) or (c if Path(c).exists() else None)
        if path:
            return path
    sys.exit("Chrome/Chromium 을 찾지 못했습니다. 설치하거나 CHROME_PATH 환경변수로 실행 파일 경로를 지정하세요.")


def render(html_text: str, pdf: Path, build_dir: Path | None = None, name: str = "page.html") -> Path:
    """HTML 을 build_dir 에 쓰고 Chrome 헤드리스로 PDF 인쇄. 폰트는 스킬 assets 에서 복사."""
    pdf = Path(pdf)
    build_dir = Path(build_dir or pdf.parent / "_build")
    build_dir.mkdir(parents=True, exist_ok=True)
    for f in (ASSETS / "fonts").glob("Pretendard-*.woff2"):
        shutil.copy(f, build_dir / f.name)
    src = build_dir / name
    src.write_text(html_text, encoding="utf-8")
    extra = os.environ.get("JOB_APPLY_CHROME_FLAGS", "").split()  # 예: 컨테이너에서 --no-sandbox
    before = pdf.stat().st_mtime if pdf.exists() else None
    with tempfile.TemporaryDirectory(prefix="job-apply-chrome-") as profile_dir:  # 사용자 Chrome 프로필과 분리
        r = subprocess.run(
            [find_chrome(), *extra, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check",
             "--use-mock-keychain",  # macOS 키체인 접근 없이 (없으면 종료가 10초 늦고 exit 2 가 나는 환경이 있다)
             "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000",
             f"--print-to-pdf={pdf}", src.resolve().as_uri()],
            capture_output=True, text=True, timeout=180,
        )
    written = pdf.exists() and pdf.stat().st_size > 0 and pdf.stat().st_mtime != before
    if not written:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-8:])
        sys.exit(f"Chrome PDF 인쇄 실패 (exit {r.returncode}): {pdf.name}\n{tail}\n"
                 "→ Chrome 이 실행되는지 확인하세요. 컨테이너·CI 에서는 JOB_APPLY_CHROME_FLAGS=--no-sandbox 를 설정합니다.")
    return pdf
