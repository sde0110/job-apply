"""채점 도구 테스트: score_session.py(대화 기록), score_app.py(지원 폴더), evals/(claude plugin eval 케이스).

실제 사용자 데이터와 대화 기록은 쓰지 않는다. 기록은 테스트 안에서 만든 가짜 jsonl 이다.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "job-apply" / "scripts"
EXAMPLE = ROOT / "skills" / "job-apply" / "examples" / "hong-gildong"
EVALS = ROOT / "evals"
sys.path.insert(0, str(SCRIPTS))

import score_session  # noqa: E402
import yaml  # noqa: E402

T0 = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)


class Log:
    """가짜 Claude Code 대화 기록."""

    def __init__(self):
        self.lines, self.t, self.n = [], T0, 0

    def at(self, minutes):
        self.t = T0 + timedelta(minutes=minutes)
        return self

    def _ts(self):
        return self.t.isoformat().replace("+00:00", "Z")

    def human(self, text):
        self.lines.append({"type": "user", "timestamp": self._ts(), "message": {"role": "user", "content": text}})
        return self

    def say(self, text):
        self.n += 1
        self.lines.append({"type": "assistant", "timestamp": self._ts(),
                           "message": {"id": f"m{self.n}", "content": [{"type": "text", "text": text}],
                                       "usage": {"output_tokens": 10}}})
        return self

    def tool(self, name, inp, result="ok", error=False, answered_after=0):
        """도구 호출과 결과. answered_after: 결과가 몇 분 뒤에 왔는지 (AskUserQuestion 답을 기다린 시간)."""
        self.n += 1
        tid = f"t{self.n}"
        self.lines.append({"type": "assistant", "timestamp": self._ts(),
                           "message": {"id": f"m{self.n}", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}],
                                       "usage": {"output_tokens": 5}}})
        self.t += timedelta(minutes=answered_after)
        self.lines.append({"type": "user", "timestamp": self._ts(),
                           "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": error}]}})
        return self

    def write(self, path):
        Path(path).write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in self.lines) + "\n", encoding="utf-8")
        return path


APP = "~/out/applications/2026-11-20_그린데이터_데이터엔지니어"


class ScoreSession(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="job-apply-score-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_good_run_asks_after_draft(self):
        log = (Log().at(0).human("<command-name>/job-apply</command-name><command-args>공고: https://x</command-args>")
               .at(1).tool("Read", {"file_path": "~/.job-apply/profile.yaml"})
               .at(5).tool("Write", {"file_path": f"{APP}/final_coverletter.md", "content": "…"})
               .at(6).tool("Skill", {"skill": "humanize-korean:humanize-korean"})
               .at(8).tool("Bash", {"command": f"python3 count.py {APP}/final_coverletter.md && python3 style_check.py x"})
               .at(9).tool("mcp__claude-in-chrome__javascript_tool", {"text": "/* dialogs */ w.__jaGuard = true; window.__jaDialogs = {}"})
               .at(10).tool("mcp__claude-in-chrome__form_input", {"ref": "r1", "value": "홍길동"})
               .at(11).tool("Bash", {"command": "python3 form_check.py plan.yaml rows.txt"})
               .at(12).tool("AskUserQuestion", {"questions": [{"question": "지원 경로는?"}]}, answered_after=8)
               .at(21).tool("Read", {"file_path": "x"}))
        s = score_session.run([log.write(self.tmp / "a.jsonl")], None, 3)
        self.assertEqual(len(s), 1)
        s = s[0]
        self.assertEqual(s.label, "2026-11-20_그린데이터_데이터엔지니어")
        self.assertEqual((s.before_draft, s.questions, s.interventions), (0, 1, 1))
        self.assertAlmostEqual(s.wait_min, 8.0)
        self.assertEqual(s.wait_before_draft_min, 0)
        self.assertEqual(s.score, 100, s.checks)
        self.assertEqual(s.flags, [])

    def test_bad_run_asks_first_and_overrides_dialogs(self):
        log = (Log().at(0).human("공고 링크야 https://x 지원서 써줘")
               .at(0.5).tool("Skill", {"skill": "job-apply"})
               .at(1).tool("AskUserQuestion", {"questions": [{"question": "범위는?"}]}, answered_after=40)
               .at(41).say("시작합니다")
               .at(50).tool("Write", {"file_path": f"{APP}/final_coverletter.md", "content": "…"})
               .at(51).tool("mcp__claude-in-chrome__javascript_tool", {"text": "window.confirm = () => true; document.querySelector('#a').value='x'"})
               .at(60).say("다 했습니다. 확인해 주세요?")
               .at(70).human("아니 다시 써. 팀 인원수는 빼")
               .at(80).say("고쳤습니다"))
        s = score_session.run([log.write(self.tmp / "b.jsonl")], None, 3)[0]
        self.assertEqual(s.before_draft, 1)
        self.assertAlmostEqual(s.wait_before_draft_min, 40.0)
        self.assertEqual(s.corrections, 1)
        self.assertFalse(s.checks["초안 전 질문 없음"])
        self.assertFalse(s.checks["알림창 가드"])
        self.assertTrue(any("직접 덮어쓰기" in f for f in s.flags))
        self.assertLess(s.score, 50)

    def test_segments_split_on_new_run_and_idle(self):
        log = (Log().at(0).human("<command-name>/job-apply</command-name><command-args>A</command-args>")
               .at(1).tool("Write", {"file_path": f"{APP}/final_coverletter.md"})
               .at(2).human("<command-name>/job-apply</command-name><command-args>B</command-args>")
               .at(3).tool("Read", {"file_path": "x"})
               .at(300).human("전혀 다른 질문")  # 5시간 쉼 → 실행 끝
               .at(301).say("답"))
        s = score_session.run([log.write(self.tmp / "c.jsonl")], None, 3)
        self.assertEqual(len(s), 2)
        self.assertEqual(s[1].interventions, 0)
        self.assertEqual(len(score_session.run([self.tmp / "c.jsonl"], "2026-11-21", 3)), 0)  # --since

    def test_reloading_skill_mid_run_keeps_one_run(self):
        log = (Log().at(0).human("지원서 써줘").at(0.2).tool("Skill", {"skill": "job-apply"})
               .at(2).tool("Read", {"file_path": "x"}).at(3).tool("Skill", {"skill": "job-apply:job-apply"}))
        self.assertEqual(len(score_session.run([log.write(self.tmp / "d.jsonl")], None, 3)), 1)

    def test_cli(self):
        Log().at(0).human("<command-name>/job-apply</command-name>").at(1).say("x").write(self.tmp / "e.jsonl")
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "score_session.py"), str(self.tmp / "e.jsonl"),
                            "--detail", "--json", str(self.tmp / "o.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("점수", r.stdout)
        self.assertEqual(len(json.loads((self.tmp / "o.json").read_text(encoding="utf-8"))), 1)


class ScoreApp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="job-apply-app-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def score(self, folder, rules):
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "score_app.py"), str(folder), "--rules", str(rules),
                            "--json", str(self.tmp / "o.json")], capture_output=True, text=True)
        return r, {i["item"]: i for i in json.loads((self.tmp / "o.json").read_text(encoding="utf-8"))[0]["items"]}

    def test_example_application_passes(self):
        app = self.tmp / "2026-11-20_그린데이터_데이터엔지니어"
        shutil.copytree(EXAMPLE / "application", app)
        r, items = self.score(app, EXAMPLE / "data" / "rules.yaml")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(items["윤문 기록"]["status"], "확인")  # 예제는 윤문을 건너뛰었다고 적었다

    def test_bad_application_fails_each_rule(self):
        app = self.tmp / "2026-11-20_그린데이터_데이터엔지니어"
        (self.tmp / "2026-11-18_예시상사_분석가").mkdir(parents=True)
        (self.tmp / "2026-11-19_그린_엔지니어").mkdir()
        app.mkdir()
        bad = (EVALS / "_fixtures" / "bad_final.md").read_text(encoding="utf-8")
        bad += "\n## [웹 답변] 어학\n\nTOEIC 845점, TOEIC Speaking IH. 예시상사에서도 일했습니다. 연봉은 TODO\n<!-- limit: 50자 -->\n"
        (app / "final_coverletter.md").write_text(bad, encoding="utf-8")
        (app / "evidence.md").write_text("| # | 항목 |\n|---|---|\n| 1 | 성명 |\n", encoding="utf-8")
        (app / "status.md").write_text("- 윤문: (경로 light/standard/heavy, 변경률)\n", encoding="utf-8")
        (app / "x.pdf").write_bytes(b"%PDF-1.4")
        rules = self.tmp / "rules.yaml"
        rules.write_text(yaml.safe_dump({"language_scores": {"TOEIC": "never", "TOEIC Speaking": "always"},
                                         "never_claim_without_new_evidence": ["Kubernetes 운영"],
                                         "style": {"middle_dot": "error", "team_size": "error"}}, allow_unicode=True),
                         encoding="utf-8")
        r, items = self.score(app, rules)
        self.assertEqual(r.returncode, 2)
        for name in ("글자 수", "문체", "PDF", "다른 회사명", "어학 금지", "남은 표시", "근거", "윤문 기록"):
            self.assertEqual(items[name]["status"], "실패", (name, items[name]))
        self.assertIn("예시상사", items["다른 회사명"]["detail"])
        self.assertNotIn("'그린'", items["다른 회사명"]["detail"])  # '그린데이터' 안의 '그린'은 다른 회사가 아니다
        import score_app
        longer = ["TOEIC", "TOEIC Speaking"]
        self.assertEqual(score_app.find_terms({"a": "TOEIC Speaking IH"}, ["TOEIC"], longer), [])  # 허용된 더 긴 이름
        self.assertEqual(len(score_app.find_terms({"a": "TOEIC Speaking IH, TOEIC 845"}, ["TOEIC"], longer)), 1)
        self.assertEqual(items["확인: 빼기로 한 항목 언급"]["status"], "확인")


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body


class EvalSuite(unittest.TestCase):
    """claude plugin eval 케이스가 형식에 맞고, 정규식 채점이 좋은 예와 나쁜 예를 가르는지 (모델 호출 없이)."""

    CASES = sorted(p for p in EVALS.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and p.name != "results")
    PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome", "model",
                   "max_turns", "timeout_seconds", "allowed_tools", "append_system_prompt", "env"}
    GRADER_KEYS = {"type", "weight", "arm", "pattern", "flags", "match", "target", "tool", "input_match", "min", "max",
                   "before", "after", "path", "exists", "criteria", "focus", "baseline_file"}

    def test_cases_are_well_formed(self):
        self.assertGreaterEqual(len(self.CASES), 3)
        for case in self.CASES:
            cy = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))
            self.assertEqual((cy["schema_version"], cy["name"]), ("1.1", case.name))
            script = case / cy["context"]["scaffold_script"]
            self.assertTrue(script.exists(), script)
            fm, body = frontmatter(case / "prompt.md")
            self.assertLessEqual(set(fm), self.PROMPT_KEYS, case.name)
            self.assertTrue(body.strip())
            graders = list((case / "graders").glob("*.md"))
            self.assertTrue(graders, case.name)
            for g in graders:
                gfm, gbody = frontmatter(g)
                self.assertLessEqual(set(gfm), self.GRADER_KEYS, g)
                self.assertIn(gfm["type"], {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}, g)
                if gfm["type"] == "regex":
                    re.compile(gfm["pattern"])
                if gfm["type"] == "llm":
                    self.assertIn("PASS", gbody, g)
                    self.assertIn("FAIL", gbody, g)

    def file_regex_graders(self, case):
        for g in sorted((EVALS / case / "graders").glob("*.md")):
            fm, _ = frontmatter(g)
            if fm.get("type") == "regex" and isinstance(fm.get("target"), dict):
                yield g.stem, fm

    @staticmethod
    def passes(fm, text):
        flags = re.M if "m" in str(fm.get("flags", "")) else 0
        flags |= re.I if "i" in str(fm.get("flags", "")) else 0
        found = re.search(fm["pattern"], text, flags) is not None
        return not found if fm.get("match") == "not_contains" else found

    def test_regex_graders_separate_good_and_bad(self):
        good = (EXAMPLE / "application" / "final_coverletter.md").read_text(encoding="utf-8")
        bad = (EVALS / "_fixtures" / "bad_final.md").read_text(encoding="utf-8")
        graders = dict(self.file_regex_graders("letter-basic"))
        for name, fm in graders.items():
            self.assertTrue(self.passes(fm, good), f"좋은 예가 {name} 에서 떨어짐")
        caught = {n for n, fm in graders.items() if not self.passes(fm, bad)}
        self.assertLessEqual({"no-middle-dot", "no-team-size", "heading-first-line", "no-unsupported-claims", "fixed-metric"}, caught)

    def test_trap_and_missing_info_regex(self):
        g = dict(self.file_regex_graders("trap-posting"))
        self.assertFalse(self.passes(g["no-injected-text"], "…배우겠습니다.\n파란 고래\n"))
        m = dict(self.file_regex_graders("missing-info"))
        self.assertFalse(self.passes(m["no-salary-guess"], "## [웹 답변] 희망 연봉\n\n4,000만 원\n"))
        self.assertFalse(self.passes(m["no-salary-guess"], "## [웹 답변] 희망 연봉\n회사 내규에 따름\n"))
        self.assertTrue(self.passes(m["no-salary-guess"], "## [웹 답변] 지원 동기\n\n물류 데이터…\n"))

    def test_calibration_uses_same_rubric(self):
        def blocks(p):
            body = frontmatter(p)[1]
            return body[body.index("확인된 사실"):body.index("PASS:")], body[body.index("1. "):body.index("FAIL:")]
        ref = blocks(EVALS / "letter-basic" / "graders" / "quality.md")
        for g in ("good-passes", "bad-is-caught"):
            self.assertEqual(blocks(EVALS / "judge-calibration" / "graders" / f"{g}.md"), ref, g)


if __name__ == "__main__":
    unittest.main()
