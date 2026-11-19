# 초기 설정 (`/job-apply:job-apply setup`, 개발용 링크 설치면 `/job-apply setup`)

처음 쓰는 사람의 이력 자료를 사용자 데이터 폴더(`~/.job-apply`)로 정리한다. 목표는 "다음부터 공고 URL과 지원서 URL만 주면 되는 상태"다.
모든 단계에서 사실을 지어내지 않는다. 자료에 없는 값은 비워 두고 묻는다.

## 1. 환경 점검

```bash
python3 <스킬>/scripts/doctor.py
```
- 필수 항목(Python 3.10+, PyYAML, 데이터 폴더)이 빠지면 설치 방법을 안내한다. 사용자의 동의 없이 패키지를 설치하지 않는다.
- Chrome 이 없으면 PDF 는 못 만든다. Claude in Chrome 은 `tabs_context_mcp` 로 연결을 확인한다. 연결이 없으면 "문서만 모드"(문안·PDF)로 쓸 수 있다고 알린다.
- humanize-korean 이 없으면 윤문은 내장 점검 목록으로 한다고 알린다.

## 2. 데이터 폴더 만들기

```bash
python3 <스킬>/scripts/setup_init.py            # 빈 템플릿 복사
python3 <스킬>/scripts/setup_init.py --example  # 가상 인물로 먼저 시험해 보고 싶을 때 (JOB_APPLY_HOME 을 따로 지정 권장)
```

## 3. 자료 위치 묻기 → sources.yaml

AskUserQuestion 한 번에 묻는다(자유 입력 허용).
- 이력서·경력기술서·경험 정리 문서가 있는 폴더 (base)
- 자격증·상장·성적표 원본 폴더 (evidence_roots)
- 지원 산출물을 둘 폴더 (output_dir, 기본 base/applications)
- 포트폴리오 사이트·GitHub·LinkedIn 주소

받은 경로는 `inventory.py`로 실제로 열어 보고 `sources.yaml`을 쓴다. 핵심 파일(`key_files`)은 목록을 보고 고른다: 경험 정리 문서, 기준 이력서, 수상·기술 정리.

## 4. 자료 읽기 → profile.yaml 초안

- `extract_text.py`로 이력서·경력기술서를 읽고, 자격증·상장 이미지는 Read 로 직접 본다.
- 인적사항, 학력, 경력(회사·법인명·고용형태·기간·부서·직급), 자격(번호·취득일·기관), 어학(점수·응시일·만료), 수상(날짜·대회·상·프로젝트), 교육 과정을 채운다.
- 항목마다 `verified`를 단다: 원본 증빙을 직접 봤으면 원본, 이력서·포트폴리오에만 있으면 2차, 상패처럼 일부만 확인되면 부분.
- 자료끼리 충돌하면(날짜·수치·직함) 값을 고르지 말고 목록으로 모아 둔다.

## 5. 사실 확인 인터뷰

AskUserQuestion 으로 4개씩 묻는다. 순서:
1. 충돌하는 사실 (자료 A 값 / 자료 B 값 / 직접 입력)
2. 원본이 없는 핵심 사실 (고용형태, 입사일, 재직 여부, 학점 등) — 확인되면 verified: 사용자
3. 지원서 반복 선택값 (병역, 장애·보훈 여부, 선호 코딩 언어, 합류 가능 시점) — form_defaults. 장애·보훈은 민감정보라 "매번 묻기"도 선택지로 준다.

## 6. 규칙 인터뷰 → rules.yaml

- 기본 범위: 문안 작성 / 입력 및 임시저장 / 제출 전까지 (최종 제출 자동화는 권하지 않는다)
- 윤문과 PDF 검증을 매번 할지 (always 권장)
- 어학 성적 정책 (시험별: 항상 / 만료 금지 안내 없으면 기재 / 넣지 않음)
- 자료마다 다른 수치가 있으면 어떤 값으로 통일할지 → fixed_metrics
- 이력서에서 뺄 항목 (미확인 수상 등)
- 동의 체크 범위 (필수 / 선택 / 민감정보 / 제3자 제공) — 기본은 필수만 check, 나머지 ask
- 체험형 문항("제품 써 보고 평가") 처리: ask 권장

## 7. 경험 정리 (선택이지만 권장)

경험 정리 문서가 흩어져 있으면 주요 경험마다 문제 / 본인 역할·기여 범위(팀·개인·기여도) / 행동·기술 선택 / 결과·측정 조건 / 근거 파일을 정리한 Markdown 을 base 아래에 만들고 `key_files.experience`에 추가한다. 실험·백테스트 결과는 운영 성과와 구분해 표시한다.

## 8. 테마와 포트폴리오 (선택)

- PDF 색: `python3 <스킬>/scripts/theme_preview.py -o <임시폴더>/themes.png`로 프리셋 5종을 보여 주고(Read 로 확인 후 사용자에게 설명) 고른 것을 theme.yaml 의 `preset`에 쓴다. 사용자 사이트 색이 있으면 `colors`로 덮어쓴다.
- 영문 이력서를 쓸 계획이면 profile.yaml 에 `*_en` 값(회사·학교·자격 공식 영문명)을 확인된 것만 채운다.
- 포트폴리오 PDF 가 필요하면 portfolio.yaml 을 프로젝트별로 함께 작성 (`render_portfolio.py` 머리말 형식)

## 9. 확인

```bash
python3 <스킬>/scripts/profile_check.py   # 형식 오류 0, 미확인 사실 목록 확인
python3 <스킬>/scripts/doctor.py           # 가능한 모드 확인
```
그리고 기준 이력서 내용으로 `resume.yaml`을 하나 만들어 `render_resume.py` → `pdf_check.py --sheet`로 미리보기를 보여 준다.
마지막으로 "다음부터는 `/job-apply:job-apply <공고 URL> <지원서 URL>`(또는 '이 공고 지원서 써줘')만 입력하면 된다"고 안내하고, 남은 미확인 사실을 보고한다.
