"""PDF 자동 판정 회귀 테스트.

일부러 망가뜨린 HTML 을 실제 Chrome 으로 인쇄해서 pdf_check 가 잡아내는지 본다.
(고아 제목, 글자 겹침, 여백 넘침, 한글 대체 폰트, 잘린 글, 빈 쪽, 쪽수 초과, 영문 문서의 한글, 줄 첫머리 가운뎃점)
그리고 엔진 CSS 가 같은 문제를 실제로 막는지(제목 뒤 쪽나눔 금지)도 확인한다.

필요: Google Chrome/Chromium. 없으면 건너뛴다.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "job-apply"
sys.path.insert(0, str(SKILL / "scripts"))
os.environ["JOB_APPLY_HOME"] = str(SKILL / "examples" / "hong-gildong" / "data")  # 렌더에는 profile·rules 만 필요

import pdf_base  # noqa: E402
import pdf_check  # noqa: E402

try:
    pdf_base.find_chrome()
    HAS_CHROME = True
except SystemExit:
    HAS_CHROME = False

PARA = "창고별 기준으로 지연 건을 골라 담당자별로 알림을 보내는 파이프라인을 만들고 실패하면 재시도하도록 구성했습니다. " * 3


@unittest.skipUnless(HAS_CHROME, "Chrome 없음")
class PdfCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="job-apply-pdf-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, name, body, *extra, css=""):
        html = pdf_base.doc("테스트", "테스트", pdf_base.RESUME_CSS + pdf_base.LETTER_CSS + css, body)
        pdf = pdf_base.render(html, self.tmp / f"{name}.pdf", self.tmp / "_build", f"{name}.html")
        argv = [str(pdf), "--html", str(self.tmp / "_build" / f"{name}.html"), *extra]
        return pdf_check.check(pdf_check.build_parser().parse_args(argv))

    def assertFail(self, r, needle):
        self.assertFalse(r["ok"], r)
        self.assertTrue(any(needle in f for f in r["fails"]), r["fails"])

    def test_clean_document_passes(self):
        r = self.check("clean", f'<section class="sec"><h2>경력</h2><p>{PARA}</p></section>')
        self.assertTrue(r["ok"], r["fails"])
        self.assertEqual(r["warns"], [])

    def test_orphan_heading_is_caught(self):
        body = (f'<div style="height:250mm"></div><h2 style="font-size:12pt;font-weight:800">프로젝트</h2>'
                f'<p style="break-inside:avoid">{PARA * 2}</p>')
        self.assertFail(self.check("orphan", body), "고아 제목")

    def test_engine_css_keeps_heading_with_content(self):
        entry = f'<article class="entry" style="break-inside:avoid"><div class="when">2024.03</div><div class="what"><h3>예시 프로젝트</h3><p>{PARA * 2}</p></div></article>'
        body = f'<div style="height:250mm"></div><section class="sec"><h2>프로젝트</h2>{entry}</section>'
        r = self.check("orphan_guarded", body)
        self.assertFalse(any("고아 제목" in f for f in r["fails"]), r["fails"])

    def test_overlap_is_caught(self):
        body = '<p>연락처 라벨과 값이 겹치는 줄입니다</p><p style="margin-top:-3.4mm;margin-left:6mm">겹쳐서 찍힌 둘째 줄입니다</p>'
        self.assertFail(self.check("overlap", body), "글자 겹침")

    def test_margin_overflow_is_caught(self):
        body = '<p style="white-space:nowrap">' + "github.com/example/very-long-repository-name/" * 5 + "</p>"
        self.assertFail(self.check("overflow", body), "여백 넘침")

    def test_hangul_fallback_font_is_caught(self):
        body = "<p style=\"font-family:'NoSuchFont-xyz',monospace\">대체 폰트로 그려지는 한글 문장입니다</p>"
        self.assertFail(self.check("fallback", body), "대체 폰트")

    def test_clipped_text_is_caught(self):
        body = ('<p style="width:30mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                "잘려서 끝까지 보이지 않는 아주 긴 문장입니다</p>")
        self.assertFail(self.check("clipped", body), "HTML 글 누락")

    def test_blank_page_is_caught(self):
        body = '<p>첫 쪽</p><div style="break-before:page;height:1mm"></div><div style="break-before:page"><p>셋째 쪽</p></div>'
        self.assertFail(self.check("blank", body), "빈 쪽")

    def test_page_limit_and_english_hangul(self):
        body = f"<p>{PARA}</p>" * 30
        r = self.check("long", body, "--max-pages", "1", "--lang", "en")
        self.assertFail(r, "쪽수")
        self.assertFail(r, "영문 문서에 한글")

    def test_scripts_in_printed_html_are_blocked(self):
        r = self.check("csp", "<p>정상 문장입니다</p><script>document.body.innerHTML='<p>HACKED</p>'</script>")
        doc = pdf_check.pymupdf.open(str(self.tmp / "csp.pdf"))
        text = "".join(p.get_text() for p in doc)
        self.assertIn("정상 문장입니다", text)
        self.assertNotIn("HACKED", text)

    def test_markup_in_data_is_printed_as_text(self):
        import render_resume
        from config import profile, rules

        data = {"title": "t", "output": "x.pdf", "eyebrow": "E", "lede": '<b>굵게</b><script>alert(1)</script>',
                "experience": [], "skills": [{"label": "<i>L</i>", "value": "v"}]}
        html = render_resume.Resume(data, profile(), rules()).html()
        self.assertIn("&lt;b&gt;굵게&lt;/b&gt;&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;i&gt;L&lt;/i&gt;", html)

    def test_line_start_middle_dot_warns_and_escape_prevents_it(self):
        r = self.check("dot", "<p>예시물류 운영기획팀<br>· 2024.03–2024.08</p>")
        self.assertTrue(any("줄 첫머리" in w for w in r["warns"]), r["warns"])
        self.assertEqual(pdf_base.e("예시물류 · 2024.03"), "예시물류 · 2024.03")


class Themes(unittest.TestCase):
    def tearDown(self):
        pdf_base.set_theme(None)

    def test_presets_and_override(self):
        self.assertIn("neutral", pdf_base.presets())
        pdf_base.set_theme("forest")
        self.assertEqual(pdf_base.colors()["accent"], "#2f6f4f")
        self.assertIn("--accent:#2f6f4f", pdf_base.root_css())
        with self.assertRaises(SystemExit):
            pdf_base.set_theme("no-such-theme")

    def test_every_preset_defines_every_color(self):
        import yaml

        keys = None
        for p in pdf_base.THEMES.glob("*.yaml"):
            c = yaml.safe_load(p.read_text(encoding="utf-8"))["colors"]
            keys = keys or set(c)
            self.assertEqual(set(c), keys, p.name)


class EnglishResume(unittest.TestCase):
    def test_missing_english_value_is_reported(self):
        import copy

        import yaml

        import render_resume
        from config import profile, rules

        data = yaml.safe_load((SKILL / "examples" / "hong-gildong" / "application" / "resume_en.yaml").read_text(encoding="utf-8"))
        prof = copy.deepcopy(profile())
        del prof["career"][0]["company_en"]
        with self.assertRaises(SystemExit) as cm:
            render_resume.Resume(data, prof, rules()).html()
        self.assertIn("career[0].company_en", str(cm.exception))


class Awards(unittest.TestCase):
    def test_user_confirmed_award_is_kept_and_secondary_is_dropped(self):
        import copy

        import yaml

        import render_resume
        from config import profile, rules

        data = yaml.safe_load((SKILL / "examples" / "hong-gildong" / "application" / "resume.yaml").read_text(encoding="utf-8"))
        prof = copy.deepcopy(profile())
        base = prof["awards"][0]
        prof["awards"] = [dict(base, title="사용자확인 경진대회", verified="사용자"),
                          dict(base, title="이차자료 경진대회", verified="2차")]
        html = render_resume.Resume(data, prof, rules()).html()
        self.assertIn("사용자확인 경진대회", html)
        self.assertNotIn("이차자료 경진대회", html)


class AutoForbid(unittest.TestCase):
    def test_other_application_companies_become_forbidden(self):
        import build_pdfs

        tmp = Path(tempfile.mkdtemp())
        try:
            for n in ("2026-01-02_예시상사_백엔드", "2026-02-03_그린데이터_분석가", "2026-03-04_그린데이터_데이터엔지니어", "메모"):
                (tmp / n).mkdir()
            current, others = build_pdfs.auto_forbid(tmp / "2026-03-04_그린데이터_데이터엔지니어")
            self.assertEqual(current, "그린데이터")
            self.assertEqual(others, ["예시상사"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
