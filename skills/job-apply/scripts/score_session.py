#!/usr/bin/env python3
"""지원 세션 채점 — Claude Code 대화 기록(jsonl)에서 job-apply 실행을 찾아 진행 과정을 채점한다.

사용:
  python3 score_session.py                        # ~/.claude/projects 아래 모든 기록에서 job-apply 실행을 찾는다
  python3 score_session.py --since 2026-11-20     # 이 날짜 이후에 시작한 실행만
  python3 score_session.py 기록.jsonl [...]       # 특정 기록 파일만
  python3 score_session.py --detail               # 실행마다 기다린 구간, 지적으로 보이는 메시지, 안전 표시까지
  python3 score_session.py --json 결과.json

실행 구간: '/job-apply' 명령이나 job-apply 스킬 호출에서 시작한다. 다음 실행, --max-idle-hours(기본 3)보다 오래
쉬었다가 온 사람 메시지, 기록 끝 중 먼저 오는 곳에서 끝난다. 한 지원을 며칠에 걸쳐 했다면 --max-idle-hours 를 늘린다.

지표
  작업(분)    에이전트가 일한 시간. 사람 입력으로 끝나지 않는 이벤트 간격의 합(간격마다 10분까지)
  대기(분)    사람을 기다린 시간. 사람 메시지와 질문 답변 직전 간격의 합. 마무리 보고 뒤 사람이 돌아오기까지도 들어간다
  초안 전 대기 그중 첫 초안을 쓰기 전에 기다린 시간. 앞에서 묻고 멈춘 비용이다
  개입        첫 요청 뒤 사람이 입력한 횟수 (메시지 + AskUserQuestion 답 + 중단)
  초안 전 개입 첫 초안(draft·final_coverletter.md, application.md)을 쓰기 전의 개입
  질문        AskUserQuestion 호출 수
  지적        사람 메시지 중 고치라는 말로 보이는 것 (추정. --detail 로 원문을 본다)
  오류        도구 오류 + 권한 거절

점수 = 해당하는 항목 중 통과 비율 × 100 (SKILL.md 규칙에서 온 것)
  초안 전 질문 없음 (§8)   초안 전 개입 0
  질문은 한 번에 (§8)      AskUserQuestion 1번 이하
  윤문 (§5)                자기소개서·답변을 쓴 실행에서 humanize-korean 실행
  글자 수 검사 (§6)        자기소개서·답변을 쓴 실행에서 count.py 실행
  문체 검사 (§6)           자기소개서·답변이나 resume·letter yaml 을 쓴 실행에서 style_check.py 실행
  PDF 검사 (§6)            PDF를 만든 실행에서 pdf_check.py 또는 build_pdfs.py 실행
  알림창 가드 (§7)         양식을 입력한 실행에서 dialogs.js 를 쓰고, 알림창을 직접 덮어쓰지 않음
  입력 대조 (§7)           양식을 입력한 실행에서 form_check.py 실행
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

AGENT_GAP_CAP = 600  # 초. 이보다 긴 작업 간격은 10분으로 센다
DRAFT = re.compile(r"(draft_coverletter|final_coverletter|application)\.md$")
LETTER = re.compile(r"(coverletter|career_text|answers?)[\w-]*\.(md|txt)$")
PDF_MADE = re.compile(r"build_pdfs|render_(?:resume|letter|portfolio)|build_portfolio|weasyprint|write_pdf")
PDF_CHECK = re.compile(r"pdf_check\.py|build_pdfs\.py")
DIALOG_OVERRIDE = re.compile(r"window\.(?:confirm|alert|prompt)\s*=(?!=)")
CORRECTION = re.compile(
    r"(?:^|[\s,.!?])아니(?:[야요고라]|$|[\s,.!?])|아닌데|다시\s*(?:써|해|작성|만들|봐)|틀렸|틀린|잘못|고쳐|"
    r"빼\s*(?:줘|고|라|야)|넣지\s*마|하지\s*마|쓰지\s*마|말고|왜\s|이상해|이상하|어색|별로|AI\s*같|못\s*쓰|싫어|마음에\s*안")
NOISE = ("<local-command", "<task-notification", "<command-", "Caveat:", "<bash-", "<system-reminder")
CHROME = "mcp__claude-in-chrome__"


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def clean_human(s: str) -> str:
    s = re.sub(r"<system-reminder>.*?</system-reminder>", "", s, flags=re.S)
    s = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", "[붙여넣기]", s, flags=re.S)
    return s.strip()


@dataclass
class Event:
    ts: datetime
    kind: str          # human / answer / stop / assistant / tool_result / start
    text: str = ""
    tool: str = ""
    inp: dict = field(default_factory=dict)
    error: bool = False
    denied: bool = False
    msg_id: str = ""
    out_tokens: int = 0


def read_events(path: str) -> list[Event]:
    """기록 파일 → 시간순 이벤트. 서브에이전트 기록(isSidechain)은 뺀다."""
    events: list[Event] = []
    names: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            ts = d.get("timestamp")
            if not ts or d.get("isSidechain"):
                continue
            t = parse_ts(ts)
            msg = d.get("message") or {}
            c = msg.get("content")
            if d.get("isCompactSummary"):
                events.append(Event(t, "compact"))
                continue
            if d.get("type") == "assistant":
                usage = msg.get("usage") or {}
                for b in c or []:
                    if not isinstance(b, dict):
                        continue
                    e = Event(t, "assistant", msg_id=msg.get("id", ""), out_tokens=usage.get("output_tokens", 0) or 0)
                    if b.get("type") == "text":
                        e.text = b.get("text", "")
                    elif b.get("type") == "tool_use":
                        e.tool = b.get("name", "")
                        e.inp = b.get("input") or {}
                        names[b.get("id", "")] = e.tool
                    else:
                        continue
                    events.append(e)
            elif d.get("type") == "user" and not d.get("isMeta"):
                if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                    for b in c:
                        if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                            continue
                        body = b.get("content")
                        body = body if isinstance(body, str) else text_of(body)
                        tool = names.get(b.get("tool_use_id", ""), "")
                        denied = bool(body) and ("doesn't want to proceed" in body or "user rejected" in body.lower())
                        kind = "answer" if tool == "AskUserQuestion" and not b.get("is_error") else "tool_result"
                        events.append(Event(t, kind, text=(body or "")[:400], tool=tool,
                                            error=bool(b.get("is_error")) and not denied, denied=denied))
                    continue
                s = text_of(c)
                if "<command-name>/job-apply" in s:
                    args = re.search(r"<command-args>(.*?)</command-args>", s, re.S)
                    events.append(Event(t, "start", text=(args.group(1) if args else "").strip()))
                    continue
                s = clean_human(s)
                if not s or s.startswith(NOISE):
                    continue
                if s.startswith("[Request interrupted"):
                    events.append(Event(t, "stop", text=s))
                else:
                    events.append(Event(t, "human", text=s))
    return events


def is_skill_start(e: Event) -> bool:
    return e.kind == "assistant" and e.tool == "Skill" and re.search(r"(?:^|:)job-apply$", str(e.inp.get("skill", ""))) is not None


def segments(events: list[Event], max_idle_h: float) -> list[list[Event]]:
    """job-apply 실행 구간으로 나눈다.

    - '/job-apply' 명령은 언제나 새 실행이다.
    - 스킬 호출(Skill job-apply)은 바로 앞이 사람 요청일 때만 새 실행이다(그 요청을 시작으로 본다).
      실행 도중 스킬을 다시 읽은 호출은 같은 실행으로 둔다.
    """
    out: list[list[Event]] = []
    cur: list[Event] | None = None
    for i, e in enumerate(events):
        if e.kind == "start":
            cur = [e]
            out.append(cur)
            continue
        if is_skill_start(e):
            j = i - 1
            while j >= 0 and events[j].kind == "assistant" and not events[j].tool:
                j -= 1
            asked = j >= 0 and events[j].kind == "human"
            if cur is None or asked:
                if cur is not None and any(x is events[j] for x in cur):
                    while cur[-1] is not events[j]:
                        cur.pop()
                    cur.pop()  # 새 요청과 그 뒤 글은 이전 실행에서 뺀다
                head = Event(events[j].ts, "start", text=events[j].text) if asked else Event(e.ts, "start", text=str(e.inp.get("args", "")))
                cur = [head, e]
                out.append(cur)
                continue
        if cur is None:
            continue
        if e.kind == "human" and (e.ts - cur[-1].ts).total_seconds() > max_idle_h * 3600:
            cur = None
            continue
        cur.append(e)
    return [s for s in out if s]


@dataclass
class Score:
    file: str
    start: str
    label: str
    agent_min: float = 0
    wait_min: float = 0
    wait_before_draft_min: float = 0
    interventions: int = 0
    before_draft: int = 0
    questions: int = 0
    corrections: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    denials: int = 0
    compactions: int = 0
    chrome_calls: int = 0
    screenshots: int = 0
    out_tokens: int = 0
    app_folder: str = ""
    checks: dict = field(default_factory=dict)   # 항목 → True/False (해당 없음은 빠짐)
    score: int | None = None
    waits: list = field(default_factory=list)
    correction_msgs: list = field(default_factory=list)
    flags: list = field(default_factory=list)


APP = re.compile(r"(?:^|/)(\d{4}-\d{2}-\d{2}_[^/\"'\s;]+)/")  # init_output.py 가 만드는 YYYY-MM-DD_회사_직무 폴더


def label_of(seg: list[Event]) -> tuple[str, str]:
    """실행 이름: 이번 실행이 파일을 쓴 지원 폴더. 참고로 읽기만 한 예전 폴더는 쓰지 않는다."""
    written: list[str] = []
    mentioned: list[str] = []
    for e in seg:
        if not e.inp:
            continue
        if e.tool in ("Write", "Edit"):
            m = APP.search(str(e.inp.get("file_path", "")))
            if m:
                written.append(m.group(1))
        elif e.tool == "Bash":
            cmd = str(e.inp.get("command", ""))
            m = re.search(r"init_output\.py\s+(\S+)\s+(\S+)", cmd)
            if m:
                mentioned.append(f"{m.group(1)}_{m.group(2)}".strip("\"'"))
            for m in APP.finditer(cmd):
                if re.search(r"(>|tee|cp|mv|mkdir|touch|build_pdfs|render_)\S*\s[^|]*" + re.escape(m.group(1)), cmd):
                    written.append(m.group(1))
    folder = written[0] if written else ""
    args = re.sub(r"\s+", " ", seg[0].text)[:48]
    return (folder or (mentioned[0] if mentioned else "") or args or "(요청 없음)"), folder


def milestone(seg: list[Event]) -> int | None:
    """'초안'으로 볼 첫 결과물의 위치: 자기소개서 초안 → 지원 폴더에 쓴 첫 파일 → 첫 양식 입력 순으로 찾는다.
    이미 쓴 지원을 이어 하는 실행처럼 초안이 없는 실행도 '먼저 일하고 나중에 묻기'를 볼 수 있게 한다."""
    def first(pred):
        return next((i for i, e in enumerate(seg) if e.kind == "assistant" and pred(e)), None)
    for pred in (lambda e: e.tool in ("Write", "Edit") and DRAFT.search(str(e.inp.get("file_path", ""))),
                 lambda e: e.tool in ("Write", "Edit") and APP.search(str(e.inp.get("file_path", ""))),
                 lambda e: e.tool in (CHROME + "form_input", CHROME + "file_upload")
                 or (e.tool == CHROME + "computer" and e.inp.get("action") == "type")):
        i = first(pred)
        if i is not None:
            return i
    return None


def score_segment(path: str, seg: list[Event]) -> Score:
    label, folder = label_of(seg)
    sc = Score(file=os.path.basename(path), start=seg[0].ts.astimezone().strftime("%m-%d %H:%M"),
               label=label, app_folder=folder)
    first_draft = milestone(seg)
    agent = wait = wait_early = 0.0
    seen_msgs: set[str] = set()
    bash: list[str] = []
    js: list[str] = []
    skills: list[str] = []
    form_filled = False
    last_text = ""
    for i, e in enumerate(seg):
        if i:
            gap = (e.ts - seg[i - 1].ts).total_seconds()
            if e.kind in ("human", "answer", "stop"):
                wait += gap
                if first_draft is None or i < first_draft:
                    wait_early += gap
                if gap >= 60:
                    sc.waits.append({"at": e.ts.astimezone().strftime("%m-%d %H:%M"), "min": round(gap / 60, 1),
                                     "after": last_text[-160:].replace("\n", " ")})
            else:
                agent += min(gap, AGENT_GAP_CAP)
        if e.kind in ("human", "answer", "stop") and i:
            sc.interventions += 1
            if first_draft is None or i < first_draft:
                sc.before_draft += 1
        if e.kind == "human" and i and CORRECTION.search(e.text):
            sc.corrections += 1
            sc.correction_msgs.append(e.text[:160].replace("\n", " "))
        if e.kind == "compact":
            sc.compactions += 1
        if e.kind == "tool_result":
            sc.tool_errors += e.error
            sc.denials += e.denied
        if e.kind == "assistant":
            if e.msg_id and e.msg_id not in seen_msgs:
                seen_msgs.add(e.msg_id)
                sc.out_tokens += e.out_tokens
            if e.text.strip():
                last_text = e.text.strip()
            if not e.tool:
                continue
            sc.tool_calls += 1
            if e.tool == "AskUserQuestion":
                sc.questions += 1
                last_text = " / ".join(q.get("question", "") for q in e.inp.get("questions", []))
            elif e.tool == "Bash":
                bash.append(str(e.inp.get("command", "")))
            elif e.tool in ("Skill", "Agent"):
                skills.append(str(e.inp.get("skill") or e.inp.get("subagent_type") or ""))
            elif e.tool.startswith(CHROME):
                sc.chrome_calls += 1
                name = e.tool[len(CHROME):]
                action = e.inp.get("action")
                if name == "computer" and action == "screenshot":
                    sc.screenshots += 1
                if name in ("form_input", "file_upload") or (name == "computer" and action == "type"):
                    form_filled = True
                if name == "javascript_tool":
                    code = str(e.inp.get("text", ""))
                    js.append(code)
                    if re.search(r"\.value\s*=|dispatchEvent|\.click\(\)", code):
                        form_filled = True
    sc.agent_min = round(agent / 60, 1)
    sc.wait_min = round(wait / 60, 1)
    sc.wait_before_draft_min = round(wait_early / 60, 1)

    bash_all, js_all = "\n".join(bash), "\n".join(js)
    for code in js:
        if "__jaGuard" in code:  # 알림창 가드(dialogs.js) 원문
            continue
        if DIALOG_OVERRIDE.search(code) and "__jaDialogs" not in code:
            sc.flags.append("알림창 직접 덮어쓰기: " + DIALOG_OVERRIDE.search(code).group(0) + " … " + code[:100].replace("\n", " "))
        if re.search(r"allowRiskyOnce\(", code):
            sc.flags.append("되돌릴 수 없는 확인 허용(allowRiskyOnce) — 사용자가 맡긴 동작인지 확인: " + code[:100].replace("\n", " "))
        if "제출" in code and ".click()" in code and "__jaRows" not in code:
            sc.flags.append("스크립트로 '제출'이 든 요소 클릭 의심 — 확인: " + code[:100].replace("\n", " "))

    paths = [str(e.inp.get("file_path", "")) for e in seg if e.tool in ("Write", "Edit")]
    wrote_letter = any(DRAFT.search(x) or LETTER.search(x) for x in paths)
    wrote_pdf_data = any(re.search(r"(resume|letter)[\w-]*\.ya?ml$", x) for x in paths)
    checks = {"초안 전 질문 없음": sc.before_draft == 0, "질문은 한 번에": sc.questions <= 1}
    if wrote_letter:  # 이력서만 고친 실행에는 윤문·글자 수를 묻지 않는다
        checks["윤문"] = any("humanize" in s for s in skills)
        checks["글자 수 검사"] = "count.py" in bash_all
    if wrote_letter or wrote_pdf_data:
        checks["문체 검사"] = "style_check.py" in bash_all
    if PDF_MADE.search(bash_all):
        checks["PDF 검사"] = bool(PDF_CHECK.search(bash_all))
    if form_filled:
        checks["알림창 가드"] = "__jaDialogs" in js_all and not any(f.startswith("알림창 직접") for f in sc.flags)
        checks["입력 대조"] = "form_check.py" in bash_all
    sc.checks = checks
    sc.score = round(100 * sum(checks.values()) / len(checks))
    return sc


def find_files(project: str | None) -> list[str]:
    root = os.path.expanduser(project or "~/.claude/projects")
    files = glob.glob(os.path.join(root, "*.jsonl")) + glob.glob(os.path.join(root, "*", "*.jsonl"))
    out = []
    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                if any("job-apply" in line for line in f):
                    out.append(p)
        except OSError:
            continue
    return sorted(out)


def run(files: list[str], since: str | None, max_idle_h: float, include_setup: bool = False) -> list[Score]:
    scores = []
    for p in files:
        for seg in segments(read_events(p), max_idle_h):
            if since and seg[0].ts.astimezone().strftime("%Y-%m-%d") < since:
                continue
            if not include_setup and re.match(r"\s*(?:/?job-apply\s+)?setup\b", seg[0].text):
                continue  # 사용자 데이터 만들기는 지원이 아니다
            scores.append(score_segment(p, seg))
    scores.sort(key=lambda s: s.start)
    return scores


def width(s: str) -> int:
    return sum(2 if ord(c) > 0x1100 else 1 for c in s)


def pad(s: str, n: int) -> str:
    return s + " " * max(0, n - width(s))


def print_table(scores: list[Score], detail: bool):
    cols = ["시작", "실행", "작업(분)", "대기(분)", "초안 전 대기", "개입", "초안 전 개입", "질문", "지적", "오류", "점수"]
    rows = []
    for s in scores:
        lab = s.label if width(s.label) <= 40 else s.label[:20] + "…"
        rows.append([s.start, lab, f"{s.agent_min:g}", f"{s.wait_min:g}", f"{s.wait_before_draft_min:g}",
                     str(s.interventions), str(s.before_draft),
                     str(s.questions), str(s.corrections), str(s.tool_errors + s.denials), str(s.score)])
    ws = [max([width(c)] + [width(r[i]) for r in rows]) for i, c in enumerate(cols)]
    print("  ".join(pad(c, ws[i]) for i, c in enumerate(cols)))
    for r in rows:
        print("  ".join(pad(x, ws[i]) for i, x in enumerate(r)))
    if scores:
        n = len(scores)
        print(f"\n{n}건 평균: 작업 {sum(s.agent_min for s in scores) / n:.1f}분, 대기 {sum(s.wait_min for s in scores) / n:.1f}분"
              f"(초안 전 {sum(s.wait_before_draft_min for s in scores) / n:.1f}분), "
              f"개입 {sum(s.interventions for s in scores) / n:.1f}번, 점수 {sum(s.score for s in scores) / n:.0f}")
        miss: dict[str, int] = {}
        for s in scores:
            for k, v in s.checks.items():
                if not v:
                    miss[k] = miss.get(k, 0) + 1
        if miss:
            print("자주 빠진 항목: " + ", ".join(f"{k} {v}건" for k, v in sorted(miss.items(), key=lambda x: -x[1])))
    flagged = [s for s in scores if s.flags]
    if flagged and not detail:
        print(f"안전 표시가 있는 실행 {len(flagged)}건 — --detail 로 확인")
    if not detail:
        return
    for s in scores:
        print(f"\n■ {s.start} {s.label}  ({s.file})")
        print("  항목: " + ", ".join(f"{k} {'✓' if v else '✗'}" for k, v in s.checks.items()))
        print(f"  도구 {s.tool_calls}번 (브라우저 {s.chrome_calls}, 스크린샷 {s.screenshots}), 오류 {s.tool_errors}, 거절 {s.denials}, "
              f"압축 {s.compactions}, 출력 토큰 {s.out_tokens:,}")
        for w in sorted(s.waits, key=lambda w: -w["min"])[:5]:
            print(f"  대기 {w['min']:g}분 ({w['at']}) ← {w['after'] or '(직전 글 없음)'}")
        for m in s.correction_msgs:
            print(f"  지적? {m}")
        for f in s.flags:
            print(f"  ⚠ {f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="job-apply 세션 채점 (Claude Code 대화 기록)")
    ap.add_argument("files", nargs="*", help="기록 jsonl. 없으면 --project 아래 전부")
    ap.add_argument("--project", help="기록 폴더 (기본: ~/.claude/projects)")
    ap.add_argument("--since", help="YYYY-MM-DD (현지 시각) 이후 시작한 실행만")
    ap.add_argument("--max-idle-hours", type=float, default=3)
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--include-setup", action="store_true", help="'/job-apply setup' 실행도 넣는다")
    ap.add_argument("--json", help="결과를 이 파일에 JSON 으로 쓴다")
    args = ap.parse_args()
    files = args.files or find_files(args.project)
    scores = run(files, args.since, args.max_idle_hours, args.include_setup)
    if not scores:
        print("job-apply 실행을 찾지 못했습니다.")
        return 1
    print_table(scores, args.detail)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in scores], f, ensure_ascii=False, indent=1)
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
