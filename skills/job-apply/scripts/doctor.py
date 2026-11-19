#!/usr/bin/env python3
"""환경 점검. 무엇이 준비됐고 무엇이 빠졌는지, 그래서 어떤 모드로 돌릴 수 있는지 알려 준다.

사용: python3 doctor.py [--json]

점검 항목
- Python 3.10+ 와 패키지: PyYAML(필수), PyMuPDF·Pillow(PDF 검증), python-docx(DOCX 읽기)
- Chrome/Chromium (PDF 인쇄)
- 번들 폰트 (Pretendard)
- 사용자 데이터 폴더(~/.job-apply 또는 JOB_APPLY_HOME): 필수 파일, 권한, 자료 폴더 경로
- humanize-korean 플러그인 (윤문, 선택)
- Claude in Chrome 은 Python 에서 확인할 수 없다 → Claude 가 tabs_context_mcp 로 확인한다

종료 코드: 0 = 전체 모드 가능, 1 = 일부 모드만 가능, 2 = 필수 항목 부족
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent


def check_python():
    ok = sys.version_info >= (3, 10)
    return ok, f"Python {sys.version.split()[0]}" + ("" if ok else " (3.10 이상 필요)")


def check_module(name, pip_name, required):
    try:
        importlib.import_module(name)
        return True, f"{pip_name} 설치됨"
    except ImportError:
        req = next((d / "requirements.txt" for d in HERE.parents if (d / "requirements.txt").exists()), None)
        hint = f"python3 -m pip install -r {req}" if req else f"python3 -m pip install {pip_name}"
        return (not required), f"{pip_name} 없음 → {hint}"


def check_chrome():
    sys.path.insert(0, str(HERE))
    from pdf_base import CHROME_CANDIDATES  # noqa: E402 (pdf_base 는 yaml 이 필요)

    for c in CHROME_CANDIDATES:
        if c and (shutil.which(c) or Path(c).exists()):
            return True, f"Chrome: {shutil.which(c) or c}"
    return False, "Chrome/Chromium 없음 → 설치하거나 CHROME_PATH 환경변수로 경로 지정 (PDF 인쇄에 필요)"


def check_fonts():
    fonts = sorted((SKILL / "assets" / "fonts").glob("Pretendard-*.woff2"))
    themes = sorted(p.stem for p in (SKILL / "assets" / "themes").glob("*.yaml"))
    return len(fonts) >= 5 and "neutral" in themes, f"Pretendard 폰트 {len(fonts)}개, 테마 프리셋 {len(themes)}개"


def check_data_home():
    """(ok, msg, level) 목록을 돌려준다. ok=False 이고 level='필수'면 시작할 수 없다."""
    home = Path(os.environ.get("JOB_APPLY_HOME", "~/.job-apply")).expanduser()
    if not home.exists():
        return [(False, f"사용자 데이터 폴더 없음: {home} → /job-apply:job-apply setup 또는 python3 scripts/setup_init.py", "필수")]
    rows = [(True, f"위치: {home}", "필수")]
    mode = stat.S_IMODE(home.stat().st_mode)
    if mode & 0o077:
        rows.append((False, f"폴더 권한 {oct(mode)} → chmod 700 {home} 권장 (개인정보)", "권장"))
    for name, required in (("profile.yaml", True), ("sources.yaml", True), ("rules.yaml", False),
                           ("theme.yaml", False), ("portfolio.yaml", False)):
        exists = (home / name).exists()
        rows.append((exists, f"{name} {'있음' if exists else '없음'}", "필수" if required else "선택"))
    if (home / "sources.yaml").exists():
        sys.path.insert(0, str(HERE))
        from config import resolve, sources  # noqa: E402

        src = sources()
        if src.get("base") and not resolve(src["base"]):
            rows.append((False, f"sources.yaml base 경로 없음: {src['base']}", "필수"))
        if src.get("output_dir") and not resolve(src["output_dir"]):
            rows.append((False, f"output_dir 경로 없음(처음 지원 때 만들어짐): {src['output_dir']}", "선택"))
        for r in src.get("evidence_roots", []):
            if not resolve(r):
                rows.append((False, f"evidence_roots 경로 없음: {r}", "선택"))
    return rows


def check_humanize():
    reg = Path("~/.claude/plugins/installed_plugins.json").expanduser()
    try:
        data = json.loads(reg.read_text())
        names = list((data.get("plugins") or data).keys())
    except (OSError, ValueError):
        names = []
    found = any(n.startswith("humanize-korean") for n in names)
    return found, ("humanize-korean 플러그인 설치됨" if found else
                   "humanize-korean 없음 → 윤문은 스킬 내장 점검 목록으로만 한다 (선택 설치)")


def main():
    as_json = "--json" in sys.argv
    rows = []

    def add(group, ok, msg, level):
        rows.append({"group": group, "ok": ok, "level": level, "msg": msg})

    ok, msg = check_python(); add("Python", ok, msg, "필수")
    ok, msg = check_module("yaml", "pyyaml", True); add("패키지", ok, msg, "필수")
    yaml_ok = ok
    ok, msg = check_module("pymupdf", "pymupdf", False)
    if not ok:
        ok, msg = check_module("fitz", "pymupdf", False)
    add("패키지", ok, msg, "PDF 검증")
    ok, msg = check_module("PIL", "pillow", False); add("패키지", ok, msg, "PDF 미리보기")
    ok, msg = check_module("docx", "python-docx", False); add("패키지", ok, msg, "DOCX 읽기")
    if yaml_ok:
        ok, msg = check_chrome(); add("PDF", ok, msg, "PDF 인쇄")
    ok, msg = check_fonts(); add("PDF", ok, msg, "PDF 인쇄")
    if yaml_ok:
        for ok, m, level in check_data_home():
            add("사용자 데이터", ok, m, level)
    ok, msg = check_humanize(); add("윤문", ok, msg, "선택")
    add("브라우저", None, "Claude in Chrome 연결은 Claude 가 tabs_context_mcp 로 확인 (없으면 문서만 모드)", "지원서 입력")

    required_fail = any(r["ok"] is False and r["level"] == "필수" for r in rows)
    pdf_fail = any(r["ok"] is False and r["level"] in ("PDF 인쇄", "PDF 검증") for r in rows)
    modes = []
    if not required_fail:
        modes.append("문안 작성")
        if not pdf_fail:
            modes.append("PDF 생성·검증")
        modes.append("지원서 입력(Claude in Chrome 연결 시)")
    humanize = next(r["ok"] for r in rows if r["group"] == "윤문")

    if as_json:
        print(json.dumps({"checks": rows, "modes": modes, "humanize": humanize}, ensure_ascii=False, indent=2))
    else:
        cur = None
        for r in rows:
            if r["group"] != cur:
                cur = r["group"]
                print(f"\n[{cur}]")
            mark = "○" if r["ok"] else ("-" if r["ok"] is None else "✕")
            print(f"  {mark} {r['msg']}  ({r['level']})")
        print("\n가능한 모드:", ", ".join(modes) if modes else "없음 — 필수 항목부터 해결하세요")
        print("윤문:", "humanize-korean" if humanize else "내장 점검 목록")
    return 2 if required_fail else (1 if pdf_fail else 0)


if __name__ == "__main__":
    sys.exit(main())
