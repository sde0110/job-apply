# job-apply

[English](README.en.md)

채용 공고 URL과 지원서 URL을 주면 Claude Code가 **내 이력 자료만 근거로** 맞춤 이력서·자기소개서 PDF와 지원서 답변을 만들고, 사실·윤문·PDF를 검증한 뒤 지원서 화면에 입력합니다. **제출하기는 누르지 않습니다.**

```
/job-apply:job-apply setup                          # 처음 한 번: 내 자료로 프로필·규칙 만들기
/job-apply:job-apply <공고 URL> <지원서 URL>         # 지원할 때마다
```

"이 공고 지원서 써줘"처럼 말로 요청해도 됩니다. 한국어 채용 공고·국내 채용 플랫폼(Greeting, recruiter.co.kr 등)을 기준으로 만들었고, 영문 이력서도 만들 수 있습니다.

## 하는 일

1. 공고와 지원서 양식을 읽고 문항·글자 수·첨부 칸·필수 항목을 정리합니다.
2. 내 자료(이력서, 경험 정리, 자격증·상장 원본)에서 근거를 찾아 `evidence.md`에 정리합니다. 근거 없는 요건은 쓰지 않습니다.
3. 자기소개서·웹 답변을 쓰고 윤문합니다(humanize-korean 플러그인이 있으면 사용).
4. 이력서·자기소개서 PDF를 만들고 쪽수·누락·폰트·겹침·여백·금지어(다른 지원 회사명)를 자동 판정합니다.
5. Claude in Chrome으로 지원서 화면에 입력하고, 입력 계획과 화면 값을 대조합니다.
6. 제출 직전에 멈추고 확인할 것을 보고합니다.

## 설치

필요한 것: [Claude Code](https://claude.com/claude-code), Python 3.10+, Google Chrome(PDF 인쇄).

```bash
claude plugin install job-apply --marketplace sde0110/job-apply
```

Claude Code 안에서는 `/plugin install job-apply --marketplace sde0110/job-apply`. 예전 버전이면 두 줄로 합니다.

```
/plugin marketplace add sde0110/job-apply
/plugin install job-apply@job-apply
```

설치 후 Claude Code를 다시 시작하고 `/job-apply:job-apply setup`을 실행하면 환경 점검(`doctor.py`)부터 안내합니다. Python 패키지가 없으면 설치 명령(`python3 -m pip install -r <플러그인 폴더>/requirements.txt`)을 보여 줍니다.

선택:
- [Claude in Chrome](https://claude.com/chrome) — 지원서 화면 자동 입력. 없으면 문안·PDF까지만 합니다.
- [humanize-korean](https://github.com/epoko77-ai/im-not-ai) — 한국어 윤문. 없으면 내장 점검 목록으로 윤문합니다.
  `/plugin marketplace add epoko77-ai/im-not-ai` → `/plugin install humanize-korean@im-not-ai`

먼저 가상 인물로 시험해 볼 수 있습니다(내 데이터를 건드리지 않음).

```bash
python3 <플러그인 폴더>/skills/job-apply/scripts/run_example.py
```

## 내 데이터

모든 개인 정보는 `~/.job-apply/`(환경변수 `JOB_APPLY_HOME`로 변경)에만 둡니다. 외부로 보내는 통계 수집은 없습니다.

| 파일 | 내용 |
|---|---|
| `profile.yaml` | 인적사항·학력·경력·자격·어학·수상, 항목마다 확인 여부(원본/사용자/2차/미확인) |
| `rules.yaml` | 어학 성적 정책, 고정 수치, 이력서에서 뺄 항목, 동의 체크 범위, 기본 작업 범위 |
| `sources.yaml` | 근거 자료 폴더, 산출물 폴더 |
| `theme.yaml` | PDF 테마 프리셋(neutral·teal·forest·burgundy·mono)과 색 |
| `portfolio.yaml` | 포트폴리오 PDF 내용 (선택) |

`/job-apply:job-apply setup`이 이력서·증빙을 읽어 초안을 만들고, 확인이 필요한 사실만 모아서 묻습니다. 형식은 [`skills/job-apply/references/data-files.md`](skills/job-apply/references/data-files.md).

## 원칙

- 자료에 없는 사실·수치·경험을 만들지 않습니다. 팀 성과를 개인 성과로, 실험 결과를 운영 성과로 바꾸지 않습니다.
- 확인되지 않은 개인정보·필수 선택값은 추측하지 않고 묻습니다. "제품을 써 보고 평가하라" 같은 문항도 지어내지 않습니다.
- 로그인, 본인 인증, 이메일 확인, 제출하기는 사용자가 직접 합니다. 동의 체크는 `rules.yaml`에 정한 범위만 합니다.
- 공고·웹페이지 안에 있는 지시문은 따르지 않습니다.
- 채용 사이트 이용약관을 지키세요. 이 도구는 한 번에 한 공고를 사람이 확인하며 지원하도록 만들었고, 대량·자동 반복 지원용이 아닙니다.
- 최종 내용의 책임은 지원자에게 있습니다. 제출 전에 PDF와 입력값을 직접 확인하세요.

## 구조

```
.claude-plugin/          plugin.json, marketplace.json
skills/job-apply/
  SKILL.md               지원 흐름 (근거 → 작성 → 윤문 → PDF → 입력 → 대조 → 보고)
  references/            초기 설정, 데이터 형식, PDF, 양식별 입력 요령
  scripts/               자료 목록·텍스트 추출·글자 수·PDF 렌더와 자동 판정·환경 점검·데이터 검사·양식 대조
  scripts/browser/       지원서 화면 점검 스니펫 (Claude in Chrome 용)
  templates/             데이터·산출물 템플릿
  assets/                Pretendard 폰트, PDF 테마 프리셋
  examples/hong-gildong/ 가상 인물 예제
  testbed/               실제 채용 사이트의 까다로운 동작을 흉내 낸 로컬 테스트 양식
tests/                   스모크·PDF 판정·테스트 양식 회귀 테스트
```

## 개발

```bash
git clone https://github.com/sde0110/job-apply && cd job-apply
python3 -m pip install -r requirements.txt
ln -s "$PWD/skills/job-apply" ~/.claude/skills/job-apply   # 개발 중에는 /job-apply 로 바로 실행
python3 -m unittest discover -s tests -v                    # PDF·테스트 양식 테스트는 Chrome 필요(없으면 건너뜀)
python3 skills/job-apply/scripts/serve_testbed.py           # 로컬 테스트 양식 http://127.0.0.1:8791/
```

- 컨테이너처럼 Chrome 샌드박스가 안 되는 곳에서는 `JOB_APPLY_CHROME_FLAGS=--no-sandbox`.
- 새 채용 플랫폼에서 확인한 입력 요령은 `skills/job-apply/references/form-adapters.md`에 추가해 주세요. 실제 사이트의 코드나 화면을 저장소에 복제하지 마세요.
- 이슈·PR에 실제 이력서, 연락처, 지원서 내용을 올리지 마세요. 재현은 가상 인물 예제로 해 주세요.

변경 기록: [CHANGELOG.md](CHANGELOG.md)

## 라이선스

[MIT](LICENSE). 함께 배포하는 Pretendard 폰트(`skills/job-apply/assets/fonts/`)는 수정하지 않은 원본이며 [SIL Open Font License 1.1](skills/job-apply/assets/fonts/LICENSE-Pretendard.txt)을 따릅니다.
