"""스모크 테스트: python3 -m unittest discover -s tests

실제 사용자 데이터(~/.job-apply)는 건드리지 않는다. 모든 테스트는 임시 JOB_APPLY_HOME 에서 돈다.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "job-apply" / "scripts"
HAS_CHROME = any(
    p and (shutil.which(p) or Path(p).exists())
    for p in [os.environ.get("CHROME_PATH", ""), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "google-chrome", "chromium", "chromium-browser"]
)


def run(*args, home=None):
    env = {**os.environ}
    if home:
        env["JOB_APPLY_HOME"] = str(home)
    return subprocess.run([sys.executable, "-B", *map(str, args)], env=env, capture_output=True, text=True)


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="job-apply-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_count(self):
        r = run(SCRIPTS / "count.py", "--text", "가나 다")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("공백 포함 4자", r.stdout)

    def test_missing_home_is_reported(self):
        r = run(SCRIPTS / "doctor.py", home=self.tmp / "none")
        self.assertEqual(r.returncode, 2)
        self.assertIn("사용자 데이터 폴더 없음", r.stdout)

    def test_profile_check_rejects_bad_date(self):
        home = self.tmp / "home"
        run(SCRIPTS / "setup_init.py", "--example", home=home)
        p = home / "profile.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace('start: "2024-03-04"', "start: 2024.03"), encoding="utf-8")
        r = run(SCRIPTS / "profile_check.py", home=home)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("날짜 형식", r.stdout)

    @unittest.skipUnless(HAS_CHROME, "Chrome/Chromium 없음")
    def test_example_end_to_end(self):
        r = run(SCRIPTS / "run_example.py", self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("모두 통과", r.stdout)


if __name__ == "__main__":
    unittest.main()
