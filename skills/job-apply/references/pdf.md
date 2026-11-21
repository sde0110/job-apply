# PDF 만들기와 검증

HTML/CSS 를 Chrome 헤드리스로 인쇄한다(reportlab 기본 폰트는 "AI가 만든 문서" 같다는 피드백이 있었다).
폰트는 Pretendard(스킬 `assets/fonts`, SIL OFL), 색은 테마 프리셋(`assets/themes`) + 사용자 데이터의 `theme.yaml`.

## 한 번에 만들고 검증하기

```bash
python3 scripts/build_pdfs.py <지원폴더> [--forbid 단어…] [--allow 단어…] [--theme 프리셋] [--only resume_en]
```

- 지원 폴더의 `resume*.yaml`(이력서)과 `letter*.yaml`(자기소개서·경력기술서)을 모두 렌더하고 `pdf_check`로 검증한다.
- 쪽수 상한은 yaml 의 `max_pages`, 없으면 `layout: compact`는 1쪽, 나머지는 2쪽.
- 금지어는 같은 상위 폴더의 다른 지원 폴더(`YYYY-MM-DD_회사_직무`)에서 회사명을 자동으로 모은다. 이번 회사는 빠진다. 다른 직무명이나 놓친 회사명은 `--forbid`로 더하고, 본문에 꼭 필요한 이름(예: 전 직장과 같은 회사)은 `--allow`로 뺀다.
- 결과는 `_build/pdf_check.json`, 미리보기는 `_build/<yaml 이름>.png`. 종료 코드 0이면 모두 통과다.
- 자동 판정을 통과해도 미리보기 PNG 는 Read 로 직접 본다(아래 "눈으로 볼 것").

## 자동 판정 (`scripts/pdf_check.py`)

| 실패 (고쳐야 함) | 잡는 방법 |
|---|---|
| 쪽수 초과, 빈 쪽 | 쪽 수, 바닥글 말고 글이 없는 쪽 |
| 폰트 미포함, 한글 대체 폰트, 깨진 글자 | PDF 폰트 목록, 한글 글자의 폰트가 Pretendard 인지, U+FFFD |
| 원문 문장 누락 | `--source` 확정본 Markdown 의 문장이 PDF 에 있는지 (`## [웹 답변]` 제외) |
| HTML 글 누락 (잘림·가림) | `--html` 렌더 HTML 의 글 조각이 PDF 에 모두 있는지 — 말줄임·overflow 로 잘린 글 |
| 여백 넘침·잘림 | 줄의 끝이 본문 영역(좌우 16mm 여백)을 넘음 — Chrome 은 넘친 글자를 잘라 낸다 |
| 글자 겹침 | 서로 다른 줄의 글자 상자가 포개짐 (예: 연락처 라벨과 값) |
| 고아 제목 | 쪽의 마지막 덩어리가 제목(+제목에 붙은 날짜·회사명 줄)뿐이고 본문은 다음 쪽 |
| 금지어, 영문 문서의 한글 | `--forbid` 단어, `--lang en`일 때 한글 |
| 회귀 | `--compare 이전.pdf`와 텍스트·쪽수·픽셀이 다름 (렌더러를 고친 뒤) |

경고: Pretendard 가 아닌 폰트(고정폭 칩 제외), 줄 첫머리의 가운뎃점·슬래시·쉼표·닫는 괄호, 마지막 쪽이 12% 미만으로 참(조금 줄이면 한 쪽이 준다).

엔진 CSS 가 미리 막는 것: 섹션·경력 제목 뒤 쪽나눔 금지(`break-after: avoid`), 항목·표 줄 안 쪽나눔 금지, `" / "` 앞 줄바꿈 금지(NBSP), 레일 메타 줄의 짧은 조각은 쪼개지 않음, 고정폭 칩의 한글은 Pretendard 로.

### 눈으로 볼 것 (미리보기 PNG)

어색한 줄바꿈(한두 글자만 다음 줄), 큰 빈 공간, 강조색이 너무 많은 곳, 그림 품질. 넘치면 중요도가 낮은 항목 축약 → 자격 줄 묶기 → 칩 생략 순으로 줄인다. 문장 사실은 바꾸지 않는다.

## 디자인 원칙

- 이력서: 왼쪽 날짜 열(21mm) + 오른쪽 내용. 섹션 제목 옆에 가는 선. 기술 스택은 회색 고정폭 칩. 수상은 강조색 한 가지.
- 자기소개서·경력기술서: 왼쪽 레일(섹션 이름·맥락) + 오른쪽 본문(굵은 한 줄 제목 + 문단). 첫 섹션 뒤에 "공고 요건 ↔ 근거 경험" 표.
- 강조색은 하나만, 굵기·크기로 위계를 만든다. 파란 제목 + 밑줄 반복, 칸마다 테두리 있는 표, 문장마다 불릿은 피한다.
- 이력서·자기소개서는 2쪽 이내(1쪽 이력서는 `layout: compact`). 바닥글에 이름 / 문서 종류와 쪽 번호(n / m).
- 구분자는 가운뎃점(·) 대신 ` / `(종류가 다른 조각: 회사 / 팀 / 기간)와 `, `(같은 종류 나열: 기술, 자격)를 쓴다. 엔진이 만드는 줄도 같은 규칙이고, resume.yaml·letter.yaml 에 쓰는 글은 `style_check.py`가 검사한다.

## 테마 (`theme.yaml`, 사용자 데이터 폴더)

```yaml
preset: neutral        # neutral(기본, 남색), teal(청록), forest(초록), burgundy(자주), mono(흑백 인쇄용)
colors:                # 선택: 바꿀 색만 덮어쓴다. 키 목록은 assets/themes/neutral.yaml
  accent: "#3d5a80"
```

- 프리셋 비교: `python3 scripts/theme_preview.py [내 resume.yaml] -o 미리보기.png` — 이력서 1쪽을 프리셋마다 나란히 그린다.
- 한 번만 다른 색으로 뽑기: 렌더러·`build_pdfs.py`에 `--theme 프리셋` (theme.yaml 무시).
- 색 키: ink(제목) body(본문) sub meta faint(회색 단계) line hair(구분선) accent(강조) dot(불릿) soft·tint·tint2(옅은 배경) warm(수상) chip·chip-ink(기술 칩) foot(바닥글).

## resume.yaml (지원 폴더)

```yaml
title: 홍길동 이력서 — ○○ 백엔드 엔지니어      # PDF 메타 제목
output: 홍길동_○○_백엔드_이력서.pdf
lang: ko                    # 선택: en 이면 영문 이력서 (아래)
layout: standard            # 선택: compact 면 1쪽용 촘촘한 배치 (쪽수 상한 1)
max_pages: 2                # 선택: 쪽수 상한을 직접 정할 때
label: 이력서               # 선택: 바닥글 문서 이름
eyebrow: BACKEND ENGINEER / API, 데이터 파이프라인   # 이름 위 한 줄
lede: 두세 문장 요약 (공고에 맞춘 강점)
experience:                 # 회사명은 profile.yaml career[].company 와 같아야 한다 (기간·직함·고용형태는 profile 에서)
  - company: ○○주식회사
    stack: Python, FastAPI, PostgreSQL
    items:                  # 굵은 소제목 + 설명
      - {title: 결제 정산 배치 개선, tag: "2025.03–06", text: "…"}
  - company: △△
    text: 한 문단 설명       # items 대신 문단 하나
project_sections:
  - heading: 프로젝트
    note: 개인 프로젝트, 공개 저장소      # 선택, 제목 옆 회색 글씨
    entries:
      - when: ["2025.08", "2025.10"]
        title: 서비스 이름
        sub: 한 줄 설명                    # link 가 있으면 아랫줄, 없으면 제목 옆
        link: github.com/user/repo         # 선택
        dots: ["불릿 문장", "…"]            # 또는 text: 문단 하나
        award: 수상명                       # 선택
        stack: [Python, FastAPI]           # 선택, 칩
        compact: false
skills:
  - {label: Backend, value: "FastAPI, REST API", note: "선택 회색 덧붙임"}
exclude_awards: []          # rules.yaml 외에 이번만 뺄 수상 (문자열에 수상명·대회 단어 포함)
```

학력·교육·자격·어학·수상은 profile.yaml 에서 자동으로 만든다.
- 학력: degree 가 있는 항목만 (고등학교 제외)
- 자격: 같은 기관·같은 해면 한 줄로 묶음
- 어학: rules.yaml `language_scores` 가 never 인 시험 제외
- 수상: verified 가 원본·사용자·부분인 것만, rules.yaml `exclude_from_resume_and_letter` 와 맞는 것 제외 (남는 수상이 없으면 섹션을 뺀다)

### 영문 이력서 (`lang: en`)

- 섹션 이름·날짜(`Mar 2024 – Present`)·바닥글이 영문이 되고, 이름은 `name.en`을 쓴다.
- profile.yaml 의 한글 값은 같은 항목의 `<키>_en`으로 바꿔 쓴다: `company_en`, `display_title_en`(또는 `department_en`·`title_en`), `employment_type_en`, `school_en`, `major_en`, `degree_en`, `status_en`, 자격 `name_en`·`issuer_en`, 수상 `title_en`·`prize_en`·`project_en`, 교육 `name_en`·`official_name_en`·`org_en`.
- 한글이 든 값에 `_en`이 없으면 렌더러가 필요한 키 목록(`career[0].company_en (현재 값: …)`)을 보여 주고 멈춘다. 영문 값은 지어내지 말고 공식 영문 명칭(학교·기관 홈페이지, 증명서)을 확인하거나 사용자에게 묻는다.
- resume.yaml 본문(eyebrow, lede, items, 프로젝트)은 영문으로 쓴다. 수치·역할 범위는 국문 확정본과 같아야 한다.
- 예시: `examples/hong-gildong/application/resume_en.yaml` (영문 + 1쪽)

## letter.yaml (지원 폴더)

```yaml
title: 홍길동 자기소개서 — ○○ 백엔드 엔지니어
output: 홍길동_○○_백엔드_자기소개서.pdf
label: 자기소개서            # 바닥글 (지원서 첨부 칸 이름에 맞춰 '경력기술서' 등)
lang: ko                     # 선택: en 이면 'Preferred' 등 영문 라벨
eyebrow: 자기소개서 / BACKEND ENGINEER
subtitle: ○○ 지원
source: final_coverletter.md   # 윤문 확정본. '## [웹 답변] …' 섹션은 PDF 에서 빠진다
requirements:
  heading: 자격요건과 경험
  meta: 공고 요건마다 근거가 되는 경험
  after_section: 1               # 몇 번째 섹션 뒤에 넣을지
  rows:
    - {req: "Python 백엔드 개발", evidence: "…"}
    - {req: "Kubernetes 운영", evidence: "…", optional: true}   # optional → '우대' 표시
rail_meta:                       # 섹션 레일 이름 → 아래 회색 맥락 (' / '로 조각을 나누면 조각 단위로 줄바꿈)
  결제 정산 배치 개선: ○○주식회사 / 2025.03–06
```

경력기술서처럼 문서를 하나 더 만들려면 `letter_career.yaml`처럼 `letter`로 시작하는 이름으로 하나 더 둔다.

## portfolio.yaml (사용자 데이터 폴더)

블록 종류와 구조는 `scripts/render_portfolio.py` 머리말 참고. 표지 → 프로젝트별 한 쪽 → 부록. 그림 경로는 `images` 기준.
포트폴리오는 쪽마다 직접 나눈 문서라 `build_pdfs.py`가 아니라 `pdf_check.py <pdf> --html <_build/portfolio.html> --sheet …`로 따로 검증한다.

## 렌더러를 고쳤을 때

```bash
python3 scripts/render_resume.py <폴더>/resume.yaml -o /tmp/new.pdf
python3 scripts/pdf_check.py /tmp/new.pdf --compare <폴더>/<기존 이력서>.pdf
```
픽셀이 달라졌으면 달라진 영역이 의도한 곳뿐인지 확인한다.
