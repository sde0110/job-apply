#!/usr/bin/env python3
"""사용자 데이터 형식 검사.

사용: python3 profile_check.py [--quiet]

- profile.yaml: 필수 키, 날짜 형식(YYYY-MM 또는 YYYY-MM-DD), verified 값, 경력·학력·자격·수상 필드
- rules.yaml: 허용된 값인지 (scope, humanize, pdf_check, 어학 정책, 동의)
- sources.yaml: base 와 key_files 경로가 실제로 있는지
- 원본으로 확인되지 않은 사실(2차·부분·미확인)을 목록으로 보여 준다 — 지원서에 쓰기 전에 확인할 것

종료 코드: 0 = 통과(경고만), 1 = 오류
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import data_home, load, resolve  # noqa: E402

VERIFIED = {"원본", "사용자", "2차", "부분", "미확인"}
SCOPES = {"문안 작성", "입력 및 임시저장", "제출 전까지", "최종 제출까지"}
SWITCH = {"always", "ask", "never"}
LANG = {"never", "always", "include_unless_expired_forbidden"}
CONSENT = {"check", "never", "ask"}
DATE = re.compile(r"^\d{4}(-\d{2}){0,2}$")

errors: list[str] = []
warnings: list[str] = []
unverified: list[str] = []


def err(m):
    errors.append(m)


def need(d: dict, keys, where):
    for k in keys:
        if d.get(k) in (None, "", []):
            err(f"{where}: '{k}' 가 비어 있음")


def date_ok(v, where, allow_null=False):
    if v is None and allow_null:
        return
    if not isinstance(v, str) or not DATE.match(v):
        err(f"{where}: 날짜 형식은 \"YYYY-MM\" 또는 \"YYYY-MM-DD\" 문자열 (지금: {v!r})")


def verified(item: dict, where: str, label: str):
    v = item.get("verified")
    if v is None:
        warnings.append(f"{where}: verified 없음 → 원본/사용자/2차/부분/미확인 중 하나를 적으세요")
    elif v not in VERIFIED:
        err(f"{where}: verified 값 '{v}' 는 {sorted(VERIFIED)} 중 하나여야 함")
    elif v in {"2차", "부분", "미확인"}:
        unverified.append(f"[{v}] {label}")


def check_profile():
    p = load("profile.yaml")
    need(p, ["name", "contact"], "profile")
    need(p.get("name", {}), ["ko"], "profile.name")
    need(p.get("contact", {}), ["phone", "email"], "profile.contact")
    if p.get("birth_date"):
        date_ok(p["birth_date"], "profile.birth_date")
    for i, ed in enumerate(p.get("education", [])):
        w = f"education[{i}]"
        need(ed, ["school", "period"], w)
        for d in ed.get("period", []) or []:
            date_ok(d, w + ".period")
        verified(ed, w, f"학력 {ed.get('school')}")
    if not p.get("career"):
        warnings.append("career 가 비어 있음 (경력이 없으면 괜찮음)")
    for i, c in enumerate(p.get("career", [])):
        w = f"career[{i}]"
        need(c, ["company", "employment_type", "start"], w)
        date_ok(c.get("start"), w + ".start")
        date_ok(c.get("end"), w + ".end", allow_null=True)
        if not (c.get("display_title") or c.get("title")):
            err(f"{w}: title 또는 display_title 필요")
        verified(c, w, f"경력 {c.get('company')}")
    for i, pg in enumerate(p.get("education_programs", [])):
        w = f"education_programs[{i}]"
        need(pg, ["name", "org", "period"], w)
        verified(pg, w, f"교육 {pg.get('name')}")
    for i, c in enumerate(p.get("certificates", [])):
        w = f"certificates[{i}]"
        need(c, ["name", "date", "issuer"], w)
        date_ok(c.get("date"), w + ".date")
        verified(c, w, f"자격 {c.get('name')}")
    for i, t in enumerate(p.get("language_tests", [])):
        w = f"language_tests[{i}]"
        need(t, ["name", "score", "date"], w)
        date_ok(t.get("date"), w + ".date")
        verified(t, w, f"어학 {t.get('name')} {t.get('score')}")
    for i, a in enumerate(p.get("awards", [])):
        w = f"awards[{i}]"
        need(a, ["date", "title", "prize"], w)
        date_ok(a.get("date"), w + ".date")
        verified(a, w, f"수상 {a.get('title')} {a.get('prize')}")
    for i, a in enumerate(p.get("publications", [])):
        verified(a, f"publications[{i}]", f"논문 {a.get('title')}")
    return p


def check_rules():
    r = load("rules.yaml", required=False)
    if not r:
        warnings.append("rules.yaml 없음 → 기본값(입력 및 임시저장, 윤문·PDF 검증은 요청 시) 사용")
        return
    d = r.get("defaults", {})
    if d.get("scope") and d["scope"] not in SCOPES:
        err(f"rules.defaults.scope '{d['scope']}' 는 {sorted(SCOPES)} 중 하나")
    for k in ("humanize", "pdf_check"):
        if d.get(k) and d[k] not in SWITCH:
            err(f"rules.defaults.{k} '{d[k]}' 는 always/ask/never 중 하나")
    for name, v in (r.get("language_scores") or {}).items():
        if v not in LANG:
            err(f"rules.language_scores.{name} '{v}' 는 {sorted(LANG)} 중 하나")
    for k, v in (r.get("consent") or {}).items():
        if v not in CONSENT:
            err(f"rules.consent.{k} '{v}' 는 check/never/ask 중 하나")
    if (r.get("defaults") or {}).get("submit") not in (None, "never", "ask"):
        warnings.append("rules.defaults.submit 은 never 를 권장 (제출은 사용자가 직접)")


def check_sources():
    s = load("sources.yaml")
    need(s, ["base"], "sources")
    base = resolve(s.get("base", "")) if s.get("base") else None
    if s.get("base") and not base:
        err(f"sources.base 경로가 없음: {s['base']}")
    for r in s.get("evidence_roots", []):
        if not resolve(r):
            warnings.append(f"evidence_roots 경로 없음: {r}")
    if base:
        files = []
        for v in (s.get("key_files") or {}).values():
            files += v if isinstance(v, list) else [v]
        for f in files:
            if isinstance(f, str) and not resolve(os.path.join(base, f)):
                warnings.append(f"key_files 경로 없음: {f}")


def check_theme():
    t = load("theme.yaml", required=False)
    if not t:
        return
    themes = Path(__file__).resolve().parents[1] / "assets" / "themes"
    names = sorted(p.stem for p in themes.glob("*.yaml"))
    if t.get("preset") and t["preset"] not in names:
        err(f"theme.preset '{t['preset']}' 는 {names} 중 하나")
    for k, v in (t.get("colors") or {}).items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
            err(f"theme.colors.{k} '{v}' 는 #rrggbb 형식이어야 함")
    extra = set(t) - {"preset", "colors"}
    if extra:
        warnings.append(f"theme.yaml 에서 쓰지 않는 키: {sorted(extra)} (preset, colors 만 읽음)")


def main():
    quiet = "--quiet" in sys.argv
    print(f"사용자 데이터: {data_home()}")
    check_profile()
    check_rules()
    check_sources()
    check_theme()
    for w in warnings:
        print("경고:", w)
    if unverified and not quiet:
        print(f"\n원본으로 확인되지 않은 사실 {len(unverified)}개 (지원서에 쓰기 전 확인):")
        for u in unverified:
            print("  -", u)
    for e in errors:
        print("오류:", e)
    print("\n결과:", "통과" if not errors else f"오류 {len(errors)}개")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
