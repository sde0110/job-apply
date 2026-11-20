"""브라우저 스니펫 회귀 테스트 (헤드리스 Chrome, CDP).

- inspect.js: [role=group] 이 없는 양식(표, 머리줄 표, fieldset, Lever·Google Forms 형태)의 라벨과 값을 읽는지,
  값 속 | 를 ¦ 로 바꾸는지, 비밀번호·숨은 칸을 내보내지 않는지
- form_check.py: 값에 | 가 든 칸을 맞게 대조하는지 (예전 출력 형식 포함)
- dialogs.js: confirm 기본 취소, 제출 문구는 허락해도 취소, allowOnce 는 한 번만, alert 기록, 같은 출처 팝업 가드, restore

필요: Google Chrome/Chromium, websocket-client. 없으면 건너뛴다.
"""
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_testbed import CDP, CHROME, free_port, websocket  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "job-apply" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import form_check  # noqa: E402


class ParseRows(unittest.TestCase):
    def test_pipe_in_value_old_and_new_format(self):
        old = "#7 | 경험/경력기술서 | text | [예시물류 | Busin… | 1598\n#8 | 지원경로 | radio | 직행 | \n"
        new = "#7 | 경험/경력기술서 | text | [예시물류 ¦ Busin… | 1598\n"
        r_old, r_new = form_check.parse_rows(old), form_check.parse_rows(new)
        self.assertEqual((r_old[0]["value"], r_old[0]["len"]), ("[예시물류 | Busin…", "1598"))
        self.assertEqual((r_old[1]["value"], r_old[1]["len"]), ("직행", ""))
        self.assertEqual((r_new[0]["value"], r_new[0]["len"]), ("[예시물류 ¦ Busin…", "1598"))
        self.assertEqual(form_check.clean("a | b"), "a ¦ b")

    def test_errors_and_testbed_rows(self):
        rows = form_check.parse_rows("errors | 필수 입력 오류 표시 | count | 0 |\ntestbed | 화면·저장 불일치 | list | a;b |")
        self.assertEqual([(r["seq"], r["value"], r["len"]) for r in rows], [("errors", "0", ""), ("testbed", "a;b", "")])


@unittest.skipUnless(CHROME and websocket, "Chrome 또는 websocket-client 없음")
class Snippets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="job-apply-snippets-"))
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        handler = functools.partial(Quiet, directory=str(FIXTURES))
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.cdp_port = free_port()
        cls.chrome = subprocess.Popen(
            [CHROME, *os.environ.get("JOB_APPLY_CHROME_FLAGS", "").split(), "--headless=new", "--disable-gpu", "--use-mock-keychain",
             f"--remote-debugging-port={cls.cdp_port}", "--remote-allow-origins=*", "--disable-popup-blocking",
             f"--user-data-dir={cls.tmp / 'profile'}", "--no-first-run", "--no-default-browser-check", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(300):  # CI 에서 Chrome 을 처음 띄우면 10초를 넘기기도 한다
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{cls.cdp_port}/json/list"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.1)
        if page is None:
            cls.chrome.terminate()
            raise RuntimeError("Chrome 디버깅 포트에 30초 안에 연결하지 못함")
        cls.cdp = CDP(page["webSocketDebuggerUrl"])

    @classmethod
    def tearDownClass(cls):
        cls.chrome.terminate()
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def open(self, name):
        c = self.cdp
        c.call("Page.navigate", url=f"{self.base}/{name}")
        for _ in range(100):
            if c.js("document.readyState === 'complete' && location.pathname.endsWith(%s)" % json.dumps(name)):
                return
            time.sleep(0.05)
        self.fail(f"{name} 를 열지 못함")

    def rows(self):
        self.open("generic_form.html")
        c = self.cdp
        doc = c.call("DOM.getDocument")["root"]["nodeId"]
        node = c.call("DOM.querySelector", nodeId=doc, selector="#file1")["nodeId"]
        c.call("DOM.setFileInputFiles", nodeId=node, files=[str(FIXTURES / "dialogs.html")])
        c.js((SCRIPTS / "browser" / "inspect.js").read_text(encoding="utf-8"))
        return c.js("window.__jaRows.join('\\n')")

    def test_inspect_reads_forms_without_role_group(self):
        out = self.rows()
        size = (FIXTURES / "dialogs.html").stat().st_size
        for want in ["| 성명 | text | 홍길동 | 3", "| 생년월일 | text | 1999-03-15 | 10", "| 병역 | select | 군필 |",
                     "| 장애여부 | radio | 비대상 |", "| 학교명 | text | 예시대학교 | 5", "| 전공 | text | 산업공학 | 4",
                     "| 졸업구분 | select | 졸업 |", "| 한 줄 소개 | text | 예시물류 ¦ 운영기획팀 | 12",
                     "| 경력기술서 | text | [예시물류 ¦ 운영기획팀] 창고별 출… | 53", "| 코딩테스트 언어 | radio | Python |",
                     "| 관심 분야 | checks | Analytics |", "| Full name | text | Gildong Hong | 12",
                     "| 지원 경로 | radio | 회사 채용 페이지 |", f"| 이력서 첨부 | file | dialogs[.]html {size} |",
                     "| 개인정보 수집·이용 동의 (필수) 동의함 | consent | true |",
                     "| 개인정보 제3자 제공 동의 (선택) 동의함 | consent | false |"]:
            self.assertIn(want, out)
        self.assertNotIn("secret", out)
        self.assertNotIn("비밀번호", out)
        self.assertNotIn("보이지 않음", out)
        self.assertNotIn("[object Object]", out)
        seqs = [int(line.split(" | ")[0][1:]) for line in out.splitlines() if line.startswith("#")]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_form_check_matches_values_with_pipe(self):
        out = self.rows()
        hashes = self.cdp.js((SCRIPTS / "browser" / "hashes.js").read_text(encoding="utf-8"), await_promise=True, repl=True)
        app = self.tmp / "app"
        app.mkdir(exist_ok=True)
        career = self.cdp.js("document.querySelector('[name=career]').value")
        (app / "final_coverletter.md").write_text(f"## [웹 답변] 경력기술서\n\n{career}\n\n<!-- limit: 500자 -->\n", encoding="utf-8")
        (app / "form_plan.yaml").write_text(
            "fields:\n"
            "  - {label: 한 줄 소개, kind: text, value: \"예시물류 | 운영기획팀\"}\n"
            "  - {label: 경력기술서, kind: text, text_from: \"final_coverletter.md#[웹 답변] 경력기술서\"}\n"
            "  - {label: 병역, kind: select, value: 군필}\n"
            "  - {label: 지원 경로, kind: radio, value: 회사 채용 페이지}\n"
            "consents:\n"
            "  - {label: 수집·이용 동의 (필수), value: true}\n"
            "  - {label: 제3자, value: false}\n", encoding="utf-8")
        (self.tmp / "rows.txt").write_text(out, encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "form_check.py"), str(app / "form_plan.yaml"),
                            str(self.tmp / "rows.txt"), "--hashes", hashes], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("해시 일치", r.stdout)

    def test_dialog_guard(self):
        self.open("dialogs.html")
        c = self.cdp
        c.js("sessionStorage.clear()")
        guard = (SCRIPTS / "browser" / "dialogs.js").read_text(encoding="utf-8")
        self.assertIn("켜짐", c.js(guard))
        self.assertIn("이미 켜짐", c.js(guard))
        out = lambda: c.js("document.getElementById('out').textContent")

        c.js("document.getElementById('save').click()")
        self.assertEqual(out(), "cancel")  # 허락하지 않은 확인은 취소
        c.js("window.__jaDialogs.allowOnce('임시저장')")
        c.js("document.getElementById('save').click()")
        self.assertEqual(out(), "saved")
        c.js("document.getElementById('save').click()")
        self.assertEqual(out(), "cancel")  # 한 번만
        c.js("window.__jaDialogs.allowOnce('제출')")
        c.js("document.getElementById('submit').click()")
        self.assertEqual(out(), "kept")  # 제출 문구는 허락해도 취소
        c.js("window.__jaDialogs.allowRiskyOnce('최종 제출')")  # 사용자가 최종제출을 맡긴 경우
        c.js("document.getElementById('submit').click()")
        self.assertEqual(out(), "submitted")
        c.js("document.getElementById('submit').click()")
        self.assertEqual(out(), "kept")
        c.js("document.getElementById('pw').click()")

        c.js("document.getElementById('pop').click()")
        for _ in range(60):
            if c.js("!!(window.__p && window.__p.__jaGuard)"):
                break
            time.sleep(0.05)
        c.js("window.__p.document.getElementById('pick').click()")
        self.assertEqual(c.js("window.__p.document.title"), "not-picked")
        c.js("window.__p.close()")

        log = c.js("window.__jaDialogs.read()")
        self.assertIn("confirm | 임시저장 하시겠습니까? 임시저장 시 서류마감시간까지 수정이 가능하나, 추후 최종제출을 하여야 입사지원이 완료됩니다. | true", log)
        self.assertIn("confirm | 최종 제출하시겠습니까? 제출 후에는 수정할 수 없습니다. | false", log)
        self.assertIn("alert | 비밀번호가 일치하지 않습니다. | -", log)
        self.assertIn("popup | confirm | 이 학교를 선택하시겠습니까? | false", log)
        self.assertEqual(c.js("window.__jaDialogs.read()"), "(새 알림 없음)")

        self.assertIn("원래대로", c.js("window.__jaDialogs.restore()"))
        self.assertTrue(c.js("window.confirm.toString().includes('[native code]') && !window.__jaGuard"))

        self.open("dialogs.html")  # 같은 탭·같은 출처면 이동 뒤에도 기록이 이어진다
        self.assertFalse(c.js("!!window.__jaDialogs"))
        self.assertIn("지난 기록 8건", c.js(guard))
        c.js("window.__jaDialogs.restore()")

    def test_guard_restores_real_dialogs_after_old_override(self):
        self.open("dialogs.html")
        c = self.cdp
        c.js("window.confirm = () => false")  # 예전 세션처럼 직접 덮어쓴 상태
        c.js((SCRIPTS / "browser" / "dialogs.js").read_text(encoding="utf-8"))
        c.js("window.__jaDialogs.restore()")
        self.assertNotEqual(c.js("window.confirm.toString()"), "() => false")


if __name__ == "__main__":
    unittest.main()
