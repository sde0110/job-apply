# Changelog

## 0.1.1 — 보안 점검

- 의존성: Pillow 를 빼고 미리보기·픽셀 비교를 PyMuPDF 로 대체(Pillow 12.x 의 알려진 취약점 42건 제거, 수정본은 Python 3.11 이상만 지원), 하한을 취약점이 고쳐진 버전으로 올림(pymupdf 1.26.7, lxml 6.1.0)
- PDF: 인쇄용 HTML 에 Content-Security-Policy(스크립트·외부 요청 차단, 글꼴·그림은 로컬 파일만), 포트폴리오 링크·그림 속성값 이스케이프, Chrome 을 매번 새 임시 프로필로 실행
- 테스트 양식: 팝업에 넣는 입력값 이스케이프
- CI: 토큰 읽기 전용, 액션을 커밋 SHA 로 고정(checkout v7.0.1, setup-python v7.1.0), `pip-audit` 단계, Dependabot(pip·GitHub Actions 주간)
- SECURITY.md(비공개 취약점 신고, 위험과 대응), README 개편(예시 그림, 흐름도, 검사 항목)

## 0.1.0 — 첫 공개 버전 (미출시)

- 개인정보 분리: 이름·경로·규칙을 엔진에서 빼고 사용자 데이터 폴더(`~/.job-apply`, `JOB_APPLY_HOME`)의 profile·rules·sources·theme·portfolio YAML 로 옮김
- 초기 설정: `/job-apply:job-apply setup` 흐름, `doctor.py`(환경 점검·가능한 모드), `profile_check.py`(형식 오류·미확인 사실), `setup_init.py`, 가상 인물 예제와 `run_example.py`
- PDF: Pretendard + HTML/CSS → Chrome 헤드리스 인쇄. 이력서·자기소개서·경력기술서·포트폴리오 렌더러, 1쪽 이력서(`layout: compact`), 영문 이력서(`lang: en`)
- PDF 자동 판정 `build_pdfs.py`·`pdf_check.py`: 쪽수, 빈 쪽, 폰트 미포함·한글 대체 폰트, 원문·HTML 누락, 여백 넘침, 글자 겹침, 고아 제목, 금지어(다른 지원 회사명 자동), 영문 문서의 한글, 이전 PDF 와 픽셀 비교
- 테마 프리셋 5종(neutral·teal·forest·burgundy·mono)과 `theme_preview.py`
- 지원서 입력: 입력 계획(`form_plan.yaml`) → 입력 → 화면 점검(`browser/inspect.js`·`hashes.js`) → 대조(`form_check.py`). Greeting·recruiter.co.kr 입력 요령
- 로컬 테스트 양식(`testbed/`)과 헤드리스 Chrome 회귀 테스트: 입력 이벤트 없는 값, 열린 목록에 먹힌 클릭, 고르지 않은 회사명, 제출하기 클릭을 잡아냄
- 라이선스: MIT, Pretendard 는 SIL OFL 1.1
