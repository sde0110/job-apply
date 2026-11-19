"""사용자 데이터 위치와 설정 파일 로더.

엔진(이 스킬)에는 개인 정보가 없다. 사람마다 다른 값은 모두 사용자 데이터 폴더에 둔다.

- 위치: 환경변수 JOB_APPLY_HOME, 없으면 ~/.job-apply
- profile.yaml  인적사항·학력·경력·자격·어학·수상
- rules.yaml    작성 규칙(어학 정책, 고정 수치, 제외 항목, 동의·제출 정책)
- sources.yaml  근거 자료 폴더, 산출물 폴더
- theme.yaml    PDF 테마(선택)
- portfolio.yaml 포트폴리오 PDF 내용(선택)
"""
from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - doctor 가 안내한다
    sys.exit("PyYAML 이 필요합니다: python3 -m pip install pyyaml")

SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
TEMPLATES = SKILL_DIR / "templates"


def data_home() -> Path:
    return Path(os.environ.get("JOB_APPLY_HOME", "~/.job-apply")).expanduser()


def resolve(path: str | os.PathLike) -> str | None:
    """경로 조각마다 NFC/NFD 차이를 무시하고 실제 이름을 찾는다 (macOS 한글 경로 대응)."""
    path = os.path.expanduser(str(path))
    if os.path.exists(path):
        return path
    parts = os.path.abspath(path).split(os.sep)
    cur = os.sep
    for part in parts[1:]:
        if not part:
            continue
        cand = os.path.join(cur, part)
        if not os.path.exists(cand):
            want = unicodedata.normalize("NFC", part)
            try:
                match = next((n for n in os.listdir(cur) if unicodedata.normalize("NFC", n) == want), None)
            except OSError:
                return None
            if match is None:
                return None
            cand = os.path.join(cur, match)
        cur = cand
    return cur


def load(name: str, required: bool = True) -> dict:
    path = data_home() / name
    if not path.exists():
        if required:
            sys.exit(
                f"{path} 가 없습니다. 처음이라면 `/job-apply:job-apply setup` 으로 사용자 데이터를 만드세요.\n"
                f"(예시: {TEMPLATES / 'data' / name.replace('.yaml', '.example.yaml')})"
            )
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sources() -> dict:
    return load("sources.yaml")


def profile() -> dict:
    return load("profile.yaml")


def rules() -> dict:
    return load("rules.yaml", required=False)


def theme() -> dict:
    return load("theme.yaml", required=False)


def base_dir() -> str:
    src = sources()
    return resolve(src["base"]) or os.path.expanduser(src["base"])


def output_root() -> str:
    src = sources()
    out = src.get("output_dir") or os.path.join(src["base"], "output", "applications")
    return resolve(out) or os.path.expanduser(out)


def evidence_roots() -> list[str]:
    src = sources()
    return [src["base"], *src.get("evidence_roots", [])]


def exclude_dirs() -> set[str]:
    default = {"tmp", "_workspace", "node_modules", ".git", "dist", "__pycache__", ".venv", "static", "assets"}
    return default | set(sources().get("exclude_dirs", []))
