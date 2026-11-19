"""테스트 양식 회귀 테스트: 헤드리스 Chrome(CDP)으로 양식을 채우고 inspect.js → form_check.py 로 대조한다.

- 올바르게 채우면 form_check 가 "모두 일치"여야 한다.
- 실제 사이트에서 겪은 실수를 재현하면 form_check 가 잡아내야 한다.
  1) 입력 이벤트 없이 값만 넣기 (React 입력란에서 저장 안 됨)
  2) 드롭다운이 열린 채로 라디오 클릭 (클릭이 무시됨)
  3) 회사명을 검색만 하고 목록에서 고르지 않기
  4) 제출하기 클릭

필요: Google Chrome/Chromium, websocket-client. 없으면 건너뛴다.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "job-apply"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None

CHROME = next((c for c in [os.environ.get("CHROME_PATH", ""), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           shutil.which("google-chrome") or "", shutil.which("chromium") or ""] if c and Path(c).exists()), None)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=20)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr, await_promise=False, repl=False):
        params = dict(expression=expr, returnByValue=True, awaitPromise=await_promise)
        if repl:  # 최상위 await 가 있는 스니펫(hashes.js)
            params["replMode"] = True
        r = self.call("Runtime.evaluate", **params)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", r["exceptionDetails"]))
        return r["result"].get("value")


ROBOT = r"""
(async (A, opt) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const q = (s, r = document) => r.querySelector(s);
  const type = (el, v) => { el.focus(); if (opt.noEvent && el.dataset.bind === "name") { el.value = v; return; } el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); };
  const option = (text) => [...document.querySelectorAll(".pop [role=option]")].find((o) => o.textContent === text);
  const pick = async (btn, text) => { btn.click(); await sleep(30); option(text).click(); await sleep(30); };
  const radio = (key, text) => [...document.querySelectorAll(`[data-radio=${key}] [role=radio]`)].find((r) => r.textContent === text).click();

  type(q("[data-bind=name]"), "홍길동");
  await pick(q("[data-select=gender]"), "남성");
  q("[data-date=birth]").click(); await sleep(30);
  const di = q(".pop input"); di.value = "1999.03.15"; di.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  type(q("[data-bind=email]"), "gildong@example.com"); document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  type(q("[data-bind=phone]"), "01000000000");
  if (opt.openDropdownThenRadio) { q("[data-select=military]").click(); await sleep(30); radio("disability", "비대상"); await sleep(30); }
  await pick(q("[data-select=military]"), "군필");
  if (!opt.openDropdownThenRadio) radio("disability", "비대상");
  radio("veteran", "비대상");

  const box = q(".career");
  await pick(q("[role=combobox]", box), "정규직");
  const ci = q("input[role=combobox]", box); type(ci, "예시물류"); await sleep(30);
  if (!opt.skipCompanyPick) { option("주식회사 예시물류").click(); } else { ci.value = "주식회사 예시물류"; document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); }
  await sleep(30);
  q("[data-start]", box).click(); await sleep(30);
  for (let i = 0; i < 10 && !q(".pop b").textContent.startsWith("2024"); i++) { q(".pop [data-y='-1']").click(); await sleep(10); }
  q(".pop [data-m='3']").click(); await sleep(30);
  q("[data-current]", box).click();
  type(q("[data-bind=department]", box), "운영기획팀");
  type(q("[data-bind=title]", box), "사원");
  type(q("[data-bind=duties]", box), "창고별 출고 지연 알림 파이프라인과 재고 이상치 대시보드를 만들고 운영 지표를 관리합니다.");

  type(q("[data-bind=q_motive]"), A.motive);
  type(q("[data-bind=q_exp]"), A.exp);
  for (const v of ["Data pipeline", "Analytics"]) q(`[data-multi=interests][value='${v}']`).click();
  q("[data-single=language][value=Python]").click();
  type(q("[data-bind=join]"), "협의 후 조정 가능합니다.");
  type(q("[data-bind=route]"), "회사 채용 페이지");
  type(q("[data-bind=github]"), "https://github.com/example");
  for (const k of ["required", "optional", "sensitive"]) q(`[data-consent=${k}]`).click();
  if (opt.clickSubmit) q("#submit").click();
  return "ok";
})(%s, %s)
"""


@unittest.skipUnless(CHROME and websocket, "Chrome 또는 websocket-client 없음")
class Testbed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from serve_testbed import make_server

        cls.tmp = Path(tempfile.mkdtemp(prefix="job-apply-testbed-"))
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "run_example.py"), str(cls.tmp / "example")],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.app = next((cls.tmp / "example" / "home" / "applications").iterdir())
        cls.web_port = free_port()
        cls.srv = make_server(cls.web_port, quiet=True)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.cdp_port = free_port()
        cls.chrome = subprocess.Popen(
            [CHROME, *os.environ.get("JOB_APPLY_CHROME_FLAGS", "").split(), "--headless=new", "--disable-gpu", "--use-mock-keychain", f"--remote-debugging-port={cls.cdp_port}", "--remote-allow-origins=*",
             f"--user-data-dir={cls.tmp / 'profile'}", "--no-first-run", "--no-default-browser-check", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{cls.cdp_port}/json/list"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.1)
        cls.cdp = CDP(page["webSocketDebuggerUrl"])
        md = (cls.app / "final_coverletter.md").read_text(encoding="utf-8")
        sec = lambda h: re.search(rf"^## {re.escape(h)}\s*\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S).group(1).strip()
        cls.answers = {"motive": sec("[웹 답변] 지원 동기"), "exp": sec("[웹 답변] 관련 업무 경험")}

    @classmethod
    def tearDownClass(cls):
        cls.chrome.terminate()
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fill_and_check(self, **opt):
        c = self.cdp
        c.call("Page.navigate", url=f"http://127.0.0.1:{self.web_port}/")
        for _ in range(100):
            if c.js("document.readyState === 'complete' && !!window.__testbed"):
                break
            time.sleep(0.05)
        self.assertEqual(c.js(ROBOT % (json.dumps(self.answers, ensure_ascii=False), json.dumps(opt)), await_promise=True), "ok")
        doc = c.call("DOM.getDocument")["root"]["nodeId"]
        for key, name in (("resume", "이력서"), ("letter", "자기소개서")):
            node = c.call("DOM.querySelector", nodeId=doc, selector=f"[data-file={key}] input[type=file]")["nodeId"]
            pdf = next(self.app.glob(f"*_{name}.pdf"))
            c.call("DOM.setFileInputFiles", nodeId=node, files=[str(pdf)])
        time.sleep(1.6)  # 테스트 양식의 업로드 지연 1.2초
        c.js((SCRIPTS / "browser" / "inspect.js").read_text(encoding="utf-8"))
        rows = c.js("window.__jaRows.join('\\n')")
        hashes = c.js((SCRIPTS / "browser" / "hashes.js").read_text(encoding="utf-8"), await_promise=True, repl=True)
        out = self.tmp / f"rows_{abs(hash(json.dumps(opt)))}.txt"
        out.write_text(rows, encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", str(SCRIPTS / "form_check.py"), str(self.app / "form_plan.yaml"), str(out),
                            "--hashes", hashes], capture_output=True, text=True)
        return r

    def test_correct_fill_matches_plan(self):
        r = self.fill_and_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("모두 일치", r.stdout)
        self.assertIn("해시 일치", r.stdout)

    def test_value_without_input_event_is_caught(self):
        r = self.fill_and_check(noEvent=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("화면·저장 불일치: 'name'", r.stdout)

    def test_click_swallowed_by_open_dropdown_is_caught(self):
        r = self.fill_and_check(openDropdownThenRadio=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("✕ 장애여부", r.stdout)

    def test_company_typed_but_not_picked_is_caught(self):
        r = self.fill_and_check(skipCompanyPick=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("career1.company", r.stdout)

    def test_submit_click_is_caught(self):
        r = self.fill_and_check(clickSubmit=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("제출됨: 'true'", r.stdout)


if __name__ == "__main__":
    unittest.main()
