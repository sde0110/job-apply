# 지원서 양식별 요령

실제 지원에서 확인한 동작만 적는다. 새 플랫폼에서 확인한 내용은 여기에 추가한다.

## 공통 (Claude in Chrome)

- 시작할 때 `tabs_context_mcp`로 탭을 확인하고, 사용자가 지정하지 않았으면 새 탭에서 연다. 작업에 쓴 보조 탭(공고·데모 등)은 끝나면 닫고, 지원서 탭은 열어 둔다.
- 양식 구조 파악: `read_page`(filter: all)로 라벨·입력란·ref 를 한 번에 본다. 필수 여부는 라벨 HTML 의 `*` 로 확인한다.
  ```js
  [...document.querySelectorAll('form label')].map(l => (/\*/.test(l.innerHTML) ? '[R] ' : '    ') + l.textContent.trim().replace(/\s+/g, ' ').slice(0, 90)).join('\n')
  ```
- **JS 결과 차단**: 결과 문자열에 URL, 이메일, 토큰처럼 보이는 값(`a=b&c`, UUID, 긴 16진수와 다른 값이 섞인 것)이 있으면 `[BLOCKED: Cookie/query string data]`로 막힌다. 검증용 JS 는 길이, 참·거짓, 라벨 텍스트만 돌려준다. URL 은 `https://`, `@`, `=`를 다른 문자로 바꿔 출력하고, 해시는 따로 한 번에 하나만 출력한다.
- **React 입력란**: `computer`의 `type`으로 실제로 타이핑한다. 여러 줄 답변도 `type`에 줄바꿈을 그대로 넣으면 된다(Enter 로 제출되는 단일 입력란은 제외).
- **입력 확인**: 입력 후 값 길이와 사이트 카운터(`970/1000` 같은 텍스트)를 읽고, 답변은 SHA-256 앞 16자리를 확정본과 비교한다.
  ```js
  const h = async s => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
  (await h(document.querySelectorAll('form textarea')[0].value))
  ```
  ```python
  hashlib.sha256(text.encode()).hexdigest()[:16]
  ```
- **라디오·버튼형 선택**: 클릭이 가끔 반영되지 않는다. `aria-checked` 로 다시 확인한다.
  ```js
  [...document.querySelectorAll('form [role=radiogroup]')].map(g => [...g.querySelectorAll('[role=radio]')].map(r => r.textContent.trim() + (r.getAttribute('aria-checked') === 'true' ? '*' : '')).join('/')).join(' | ')
  ```
- **파일**: `find`로 file-input 의 ref 를 찾아 `file_upload`. 같은 칸에 다시 올리면 교체된다. 업로드 직후 진행률(0%)이 보이면 몇 초 기다린 뒤 파일명과 크기를 확인한다.
  ```js
  [...document.querySelectorAll('input[type=file]')].map(x => [...x.files].map(f => f.name.slice(-14) + ' ' + f.size).join('')).join(' ; ')
  ```
- **스크롤**: `scroll`이 먹지 않는 페이지가 있다. `scroll_to`(ref) 또는 `window.scrollTo(0,0)`을 쓴다.
- **알림창**: 삭제·제출 확인처럼 confirm 창을 띄우는 버튼은 누르지 않는다.

## Greeting (greetinghr.com 기반 채용 페이지: 예 careers.upstage.ai, miridih.com/ko/o/…)

- **임시저장 없음.** 입력값은 열린 탭에만 있다. 탭을 닫거나 새로고침하면 사라진다고 보고한다.
- 이메일 입력 시 자동완성 목록이 뜬다 → `Escape`로 닫는다. "이메일 확인" 버튼은 누르지 않는다.
- 성별·병역 등 드롭다운: 클릭 → 목록 스크린샷 → 항목 클릭. 드롭다운이 열린 채로 다음 클릭을 하면 무시될 수 있으니 `Escape` 후 진행.
- **생년월일**: 입력란 클릭 → 달력 위의 텍스트 칸(`1990.01.01` 형식)에 `YYYY.MM.DD` 입력 → Enter → Escape.
- **경력 근무기간**: 월 선택기(연도 + 1~12월 버튼). 연도 화살표로 이동 후 월 클릭. "재직 중" 체크 시 퇴사일 칸이 사라진다.
- **회사명**: 검색 콤보박스. 법인명이 목록에 있으면 고르고(예: "○○유한회사"), 없으면 목록 맨 아래 "직접 입력하기: '…'"를 누른다.
- 경력 항목 추가: "항목 추가" 버튼. 새 항목의 고용형태 목록은 길어서 스크롤해야 "인턴" 등이 보인다.
- 첨부 칸: 이력서는 보통 필수. 자기소개서/경력기술서/포트폴리오/참조 자료 칸은 공고마다 이름이 다르다. 칸마다 "파일 / URL" 토글이 있다.
- 동의: 필수항목 / 선택항목 / 민감정보(장애·보훈 입력 시) / 제3자 제공(두들린 오퍼센트) 4종이 흔하다. 첨부 후 "선택항목" 라벨이 "(필수)"로 바뀌기도 한다.
- 추가질문의 글자 수 제한은 공고마다 다르다(1000, 10000 등). 카운터 텍스트로 확인한다.
- 같은 회사라도 공고마다 필수 항목이 다르다(예: 성별·생년월일·경력 입력란이 있는 공고와 없는 공고).

## recruiter.co.kr (예: ahnlab.recruiter.co.kr)

- 단계형 양식(기본정보 → 학력·경력 → 자격·활동 → 자기소개서 → 최종제출). 단계마다 **임시저장** 버튼이 있다.
- 임시저장 후 새로고침하고 단계를 다시 열어 저장값을 확인한다.
- 학교·전공은 검색 등록, 없는 전공은 "직접 등록".
- 어학 성적은 "언제 이후 점수만 인정" 같은 조건이 있다 → rules.yaml 어학 정책과 함께 판단한다.
- 컴퓨터활용능력(SW·수준·사용기간) 필수인 경우가 있다 → profile.yaml 의 software_skills 에서 공고에 맞게 고른다.

## 공고 사이트

- 집계 사이트(예: inthiswork.com)는 WebFetch 로 내용이 잘릴 수 있다 → 원 공고(회사 채용 페이지)를 찾아 읽는다.
- 이미지로만 된 공고는 크롬 스크린샷으로 읽는다.

## 입력 계획 → 입력 → 점검 → 대조 (모든 사이트 공통 절차)

1. **입력 계획**: 지원 폴더에 `form_plan.yaml`을 쓴다(형식은 `scripts/form_check.py` 머리말, 예시는 `examples/hong-gildong/application/form_plan.yaml`). 칸마다 라벨 일부, 종류(text/select/radio/checks/file), 넣을 값을 적는다. 긴 답변은 값 대신 `text_from: "final_coverletter.md#[웹 답변] …"`로 확정본을 가리킨다. `python3 scripts/form_check.py <plan> --show`로 기대값을 본다.
2. **입력**: 위의 사이트별 요령대로 칸을 채운다. 값은 계획 그대로 넣는다(즉석에서 고쳐 쓰지 않는다. 고칠 일이 생기면 계획과 확정본을 먼저 고친다).
3. **점검**: `scripts/browser/inspect.js` 내용을 javascript_tool 에 넣는다. 결과는 15줄씩 나뉘어 나오므로 안내대로 `window.__jaPage(1)`, `window.__jaPage(2)` … 를 실행해 모든 쪽을 한 파일(예: 지원 폴더의 `inspect.txt`)에 이어 붙인다. 이어서 `scripts/browser/hashes.js`를 실행해 해시 줄을 받는다.
4. **대조**: `python3 scripts/form_check.py <plan> inspect.txt --hashes "<hashes.js 출력>"`. ✕ 가 있으면 그 칸만 다시 입력하고 3~4를 반복한다. 결과(모두 일치 / 남은 불일치)를 status.md 에 적는다.

- 출력이 `[TRUNCATED]`로 끝나면 줄 수가 많아서다 → 쪽 단위로 받는다. `[BLOCKED: …]`면 값에 URL·토큰 같은 문자열이 섞인 것이다 → 스니펫의 clean() 을 거친 값만 출력한다.
- 시험할 때는 로컬 테스트 양식을 쓴다: `python3 scripts/serve_testbed.py` → `http://127.0.0.1:8791/`, 계획은 `examples/hong-gildong/application/form_plan.yaml`(PDF 는 `run_example.py`가 만든다). 테스트 양식은 입력 이벤트 없이 넣은 값, 열린 목록 때문에 무시된 클릭, 고르지 않은 회사명, 제출하기·이메일 확인 클릭을 `testbed` 줄로 알려 준다.
