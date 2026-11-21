#!/usr/bin/env python3
"""가상 인물(홍길동) 예제로 처음부터 끝까지 실행해 본다 — 깨끗한 계정 시험용.

사용: python3 run_example.py [작업폴더]   (기본: 임시 폴더)

순서: setup_init --example → doctor → profile_check → init_output → style_check(문체 규칙) → build_pdfs(국문 이력서·영문 1쪽 이력서·자기소개서
     렌더 + 자동 검증) → 규칙 적용 확인(미확인 수상 제외, 웹 답변이 PDF 에 안 들어감, 어학 정책, 영문 라벨)
지원서 화면 입력(브라우저)은 이 스크립트 범위 밖이다.
종료 코드: 0 = 모두 통과
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
EXAMPLE = SCRIPTS.parent / "examples" / "hong-gildong"


def run(args, env, ok_codes=(0,)):
    r = subprocess.run([sys.executable, "-B", *map(str, args)], env=env, capture_output=True, text=True)
    name = Path(str(args[0])).name
    status = "통과" if r.returncode in ok_codes else f"실패(exit {r.returncode})"
    print(f"[{status}] {name} {' '.join(map(str, args[1:]))[:80]}")
    if r.returncode not in ok_codes:
        print(r.stdout[-1500:], r.stderr[-1500:])
    return r


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="job-apply-example-"))
    home = work / "home"
    if home.exists():
        shutil.rmtree(home)
    env = {**os.environ, "JOB_APPLY_HOME": str(home)}
    fails = 0

    fails += run([SCRIPTS / "setup_init.py", "--example"], env).returncode != 0
    fails += run([SCRIPTS / "doctor.py"], env, ok_codes=(0, 1)).returncode not in (0, 1)
    fails += run([SCRIPTS / "profile_check.py", "--quiet"], env).returncode != 0

    r = run([SCRIPTS / "init_output.py", "그린데이터", "데이터엔지니어"], env)
    fails += r.returncode != 0
    app = Path(r.stdout.strip().splitlines()[-1])
    for f in (EXAMPLE / "application").iterdir():
        shutil.copy(f, app / f.name)

    resume = app / "홍길동_그린데이터_데이터엔지니어_이력서.pdf"
    letter = app / "홍길동_그린데이터_데이터엔지니어_자기소개서.pdf"
    resume_en = app / "Hong_Gildong_GreenData_Data_Engineer_Resume.pdf"
    fails += run([SCRIPTS / "style_check.py", app / "final_coverletter.md", app / "resume.yaml", app / "resume_en.yaml",
                  app / "letter.yaml"], env).returncode != 0
    fails += run([SCRIPTS / "build_pdfs.py", app, "--forbid", "예시상사"], env).returncode != 0
    for name in ("resume", "resume_en", "letter"):
        src = app / "_build" / f"{name}.png"
        if src.exists():
            shutil.copy(src, work / f"{name}.png")

    missing = [p.name for p in (resume, letter, resume_en) if not p.exists()]
    if missing:
        print(f"[실패] PDF 가 만들어지지 않음: {', '.join(missing)}")
        print("결과: 실패")
        return 1

    # 규칙이 실제로 적용됐는지
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # type: ignore
    rt = "".join(p.get_text() for p in pymupdf.open(resume))
    lt = "".join(p.get_text() for p in pymupdf.open(letter))
    en = pymupdf.open(resume_en)
    et = "".join(p.get_text() for p in en)
    checks = [
        ("원본 미확인(2차) 수상은 이력서에서 빠짐", "교내 캡스톤" not in rt),
        ("원본 수상은 이력서에 들어감", "공공데이터 활용 해커톤" in rt),
        ("어학 정책(include)대로 TOEIC 기재", "TOEIC" in rt),
        ("고등학교 등 학위 없는 학력 제외 / 학사 학력 포함", "한국대학교" in rt),
        ("경력 기간·직함은 profile 에서", "Operations Data Analyst" in rt and "2024.03" in rt),
        ("웹 답변 섹션은 자기소개서 PDF 에 없음", "웹 답변" not in lt),
        ("요건 표의 우대 표시", "우대" in lt),
        ("영문 이력서: 1쪽(compact)·영문 라벨·영문 회사명", en.page_count == 1 and "Experience" in et and "Example Logistics" in et),
        ("영문 이력서: 영문 날짜와 재직 중 표기", "Mar 2024" in et and "Present" in et),
    ]
    for label, ok in checks:
        print(f"[{'통과' if ok else '실패'}] {label}")
        fails += not ok

    print(f"\n작업 폴더: {work}")
    print("결과:", "모두 통과" if not fails else f"실패 {fails}건")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
