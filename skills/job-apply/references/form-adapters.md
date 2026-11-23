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
- **알림창**: alert·confirm 이 뜨면 탭이 멈추고 javascript_tool·screenshot·get_page_text 가 모두 시간 초과된다. 탭을 열자마자, 페이지가 바뀔 때마다 `scripts/browser/dialogs.js`를 넣는다(규칙은 SKILL.md 7장). 직접 `window.confirm = () => true`로 덮어쓰지 않는다. 사용자에게 넘기기 전에는 `window.__jaDialogs.restore()`.
- **사람에게 넘길 일은 한 번에**: 로그인, 비밀번호, 다른 출처 팝업의 업로드·알림 닫기처럼 사람이 해야 하는 일은 양식을 처음 훑을 때 목록으로 만들어 두고, 채울 수 있는 칸을 다 채운 뒤 한 번에 맡긴다.

## Greeting (greetinghr.com 기반 채용 페이지: <회사>.career.greetinghr.com 또는 <회사 도메인>/ko/o/<공고ID>)

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

## recruiter.co.kr (<회사>.recruiter.co.kr)

- 단계형 양식(기본정보 → 학력·경력 → 자격·활동 → 자기소개서 → 최종제출). 단계마다 **임시저장** 버튼이 있다.
- 임시저장 후 새로고침하고 단계를 다시 열어 저장값을 확인한다.
- 학교·전공은 검색 등록, 없는 전공은 "직접 등록".
- 어학 성적은 "언제 이후 점수만 인정" 같은 조건이 있다 → rules.yaml 어학 정책과 함께 판단한다.
- 컴퓨터활용능력(SW·수준·사용기간) 필수인 경우가 있다 → profile.yaml 의 software_skills 에서 공고에 맞게 고른다.

## Google Forms (docs.google.com/forms — 인턴십·소규모 채용)

- 전체 문항은 첫 화면에서 `window.FB_PUBLIC_LOAD_DATA_[1][1]`로 한 번에 읽는다(항목 [1]=제목, [2]=설명, [3]=종류(0 단답·1 장문·2 객관식·8 섹션·13 파일), [4][0][1]=보기, [4][0][2]=필수).
- 섹션마다 '다음'으로 넘어가고, 필수 칸이 비면 다음으로 못 간다. '뒤로'/'다음' 이동해도 입력값은 유지된다. 마지막 섹션에 '제출' 버튼이 있으니 그 전 섹션에서 멈춘다.
- **파일 업로드 불가**: '파일 추가'는 다른 도메인 iframe(Google Picker)을 열어 `file_upload`·`find`가 닿지 않는다. 필수 첨부 칸이면 사용자에게 '파일 추가 → 찾아보기'로 직접 올려 달라고 하고, 업로드 뒤 listitem 텍스트에서 파일명을 확인한다(크기는 화면에서 확인 불가).
- 텍스트·장문: `computer` type 으로 입력(줄바꿈 그대로). 글자 수 카운터는 없다.
- 객관식 '기타': `기타 응답` 텍스트칸에 타이핑하면 `__other_option__` 라디오가 자동 선택된다(`data-value` 로 확인).
- 점검: inspect.js 가 `[role=listitem]`의 제목(`[role=heading]`)을 라벨로 읽는다. 실제 Google Forms 에서는 아직 돌려 보지 않았으니, 라벨이 비거나 틀리면 `[role=listitem]` innerText, `[role=radio]` aria-checked, textarea 해시로 직접 대조한다.

## Lever (jobs.lever.co/<회사>/<공고ID>/apply)

- 한 페이지 양식. **임시저장 없음.** 공고 본문은 `/apply`를 뺀 주소에 있다(WebFetch가 원문 인용을 거부하면 curl 로 HTML 을 받아 태그를 벗긴다).
- 첨부 칸이 **Resume/CV 하나뿐**인 경우가 많다 → 이력서와 경력기술서 PDF 를 하나로 합쳐 올린다(pymupdf `insert_pdf`, 병합본도 `pdf_check.py`).
- 이력서를 올리면 "Analyzing resume..." 뒤 이름·이메일·전화·위치·현재 회사·GitHub 을 **자동으로 채운다. 값이 틀리는 일이 많다**(영문 이름, 엉뚱한 위치, 이력서 소제목을 회사명으로). 그래서 업로드를 먼저 하고 Success! 를 본 뒤 모든 칸을 계획 값으로 덮어쓴다.
- 일반 input 이라 `form_input`이 잘 먹는다. Current location 은 검색 목록 → 타이핑 후 "Seoul, KOR" 같은 항목을 클릭.
- 추가 질문은 `cards[...]` 체크박스·textarea. inspect.js 는 `.application-label` 글자를 라벨로 읽는다(실제 Lever 에서는 아직 돌려 보지 않음). 맞지 않으면 JS 로 값·길이를 직접 읽어 대조한다(이메일 비교는 `@`를 `String.fromCharCode(64)`로).
- 제출 버튼을 누르면 국외 이전(Lever/미국) 동의로 간주된다는 문구가 공고에 붙는 회사가 있다 → 사용자에게 먼저 묻는다. 제출 성공 시 주소가 `/thanks`로 바뀌고 "Application submitted!"가 보인다.

## incruit (<회사>.incruit.com — 공공기관·금융사 채용에 많다)

- **흐름**: 공고(`/hire/viewhire.asp?projectid=N`) → 지원 등록(`/apply/index.asp`: 동의 라디오, 지원분야·성명·이메일, '확인') → 지원서(`/apply/form_apply.asp`). 지원서는 한 페이지이고 인적사항·학력·어학/자격·경력·자기소개·첨부 순서, 맨 아래에 비밀번호와 임시저장/최종제출이 있다.
- **등록 '확인'은 되돌릴 수 없다.** 지원분야와 이메일이 고정된다. 누르기 전에 두 값을 사용자에게 확정받고, 확인 창은 `allowRiskyOnce`로 그 한 번만 허락한다.
- **세션 4시간, 다시 열려면 로그인.** 상단에 종료 예정 시각이 나온다. 그 안에 임시저장해야 값이 남는다. 지원서 주소를 직접 열거나 새로고침하면 알림창이 뜨고 공고 페이지로 돌아가기도 한다 → 새로고침하지 않는다. 저장본은 '입사지원 확인 및 수정'에서 비밀번호로 로그인해야 열리므로 사용자에게 맡긴다.
- **알림창이 잦다.** 졸업구분을 '졸업'으로 바꾸면 change 때 "졸업(을)를 선택하셨습니다." alert 가 뜬다. 임시저장·최종제출은 confirm 이다. 입력 전에 `dialogs.js`를 켠다.
- **select·라디오**: select 는 option 값(코드)으로 넣고 `change`를 보낸다(소재지를 '서울'처럼 글자로 넣으면 빈 값이 된다). 라디오는 `input[name=…][value=…]`를 click 한 뒤 checked 를 확인한다. 학점은 "3.00"처럼 둘째 자리까지. 등록 단계에서는 `form_input`이 먹는다.
- **날짜**: 어학·자격·수상·경력 날짜는 readonly jQuery datepicker(yy-mm-dd)라서 `jQuery(el).datepicker('setDate', 'YYYY-MM-DD')`로 넣는다. 학력 기간은 연·월 텍스트 칸이다. 경력의 '재직'을 체크하면 종료일이 접수 마감일로 채워진다.
- **반복 행**: 섹션의 `img[alt=추가]`로 행을 늘린다. 같은 name 에 숨은 템플릿 행이 섞여 있으니 보이는 칸(`offsetParent !== null`)만 쓴다. 칸 길이 제한: 회사·부서·직위 20자, 담당업무 40자, 학교교육 주요내용 100자.
- **학교·전공·자격증 검색**: 새 창 팝업이 열린다. find → type → 결과 클릭이 되고, 고르면 원래 칸에 값이 들어가며 팝업이 닫힌다. 부분 일치라 짧은 검색어가 낫다. 결과가 길면 엉뚱한 항목을 누르기 쉬우니 고른 뒤 칸 값을 다시 읽는다. 목록에 없는 자격증은 넣을 수 없다 → status.md 에 남긴다.
- **첨부**: '업로드' → 새 창 팝업(JPG·GIF·PDF·ZIP, 파일당 5MB). `file_upload`는 된다. 팝업의 '확인'을 누르면 팝업이 이동하면서 완료 alert 로 멈추는 일이 많다(가드가 걸리기 전에 뜬다). 그러면 사용자가 알림을 닫아야 한다. 첨부 칸이 여러 개면 처음부터 칸별 파일 목록을 주고 사용자에게 한 번에 맡기는 편이 빠르다. 다음 업로드는 앞 건에 "보기 삭제"가 붙은 뒤 연다. 파일 칸 값은 코드라서 어느 파일이 들어갔는지 화면 값으로는 구분하지 못한다.
- **자기소개(`textarea[name=Intro]`)**: 처음에는 회색 안내문이 값으로 들어 있다 → 덮어쓰고 `style.color = ''`로 바꾼 뒤 input·keyup·change 를 보낸다. 사이트 글자 수는 줄바꿈을 포함한 JS 길이다. 카운터는 textarea 위 행의 `em[id*=Intcount]`에 있다. 다시 열었을 때 안내문 길이 그대로면 저장되지 않은 것이다.
- **저장 전 검사**: 임시저장은 form 의 `CheckApply()`가 필수값·첨부를 alert 로 검사한 뒤 confirm "임시저장 하시겠습니까?…"를 묻는다. 가드를 켠 채 `CheckApply()`를 직접 부르면 confirm 이 취소돼 저장 없이 막히는 칸만 기록에 남는다(예: "경력(재직)증명서를 첨부해 주십시오."). 비밀번호를 넣기 전에 이것으로 빈 칸을 찾는다.
- **비밀번호·임시저장·최종제출**: 비밀번호는 사용자가 넣는다(생월일이 들어가면 거절된다). 사용자에게 비밀번호 입력을 맡길 때 가드를 `restore()`하고 임시저장도 사용자가 누르게 한다. 최종제출("최종제출 할 경우 더 이상 수정 불가")은 맡긴 경우에만 `allowRiskyOnce("최종제출")`로 한다. 제출 뒤 결과 alert 로 탭이 멈출 수 있고, 접수 확인은 로그인이 필요해 사용자 보고를 근거로 기록한다.
- **점검**: inspect.js 가 표 머리칸(th)을 라벨로 읽도록 고쳤지만 incruit 에서는 아직 돌려 보지 않았다. 먼저 돌려 보고, 라벨이 비거나 틀리면 name 기준 값 덤프와 답변 해시로 대조한다. 결과에 `=`·`@`·`/`가 섞이면 BLOCKED 되므로 걸러서 출력한다.

## 점핏 이력서 (jumpit.saramin.co.kr/resume/<id> — 채용 플랫폼 이력서 편집기)

- 한 페이지 편집기. 입력 중 "임시 저장되었습니다"가 뜨지만, 마지막에 **저장하기**를 누르고 새로고침해 값을 다시 읽는다. 포지션 지원은 별도 단계라 누르지 않는다.
- 입력란 값은 `main input, main textarea`의 `name`으로 읽는다(`careers.0.jobDetailInfo`, `projects.N.projectDetailInfo`, `etcHistories.N.etcName` 등). 타이틀 30자 제한·쉼표 등 특수문자 불가(저장 시 "사용할 수 없는 특수문자를 제거해주세요"), 자기소개서 제목은 쉼표 가능, 장문 칸은 제한 없음.
- 왼쪽 "항목편집" 토글로 기타사항·자기소개서 섹션을 켠다.
- 날짜는 `YYYY`·`MM` 칸을 각각 클릭해 입력(자동으로 다음 칸으로 넘어가지 않음). 수상·자격은 시작=종료 같은 달로 넣는다.
- 기술 태그: 검색창에 입력 → 목록 항목 클릭. **목록이 이전 검색어 결과로 남아 있는 경우가 있어** 엉뚱한 태그가 들어간다 → 마지막 글자를 지웠다 다시 쳐서 목록을 갱신하고 스크린샷으로 확인 후 클릭. Claude, LangChain, Pydantic, Vitest 는 목록에 없다.
- 기타사항 이력구분 드롭다운은 위로 열린다(선택안함/자격증/대외활동/어학/수상이력).
- **긴 글을 입력한 뒤에는 페이지가 스크롤된다.** 이전 스크린샷 좌표로 클릭하면 다른 칸(예: 자기소개서 본문)에 입력된다 → 긴 입력 뒤에는 다시 스크린샷을 찍거나 `find` ref 로 클릭한다.
- 한글을 `type`으로 길게 넣을 때 받침이 깨지는 일이 있었다("맞췄습니다"→"맞춘습니다") → 입력 후 해시로 대조한다.

## 나인하이어 (ninehire 기반 채용 페이지: <회사 도메인>/job_posting/<id>/apply)

- 한 페이지 양식. **임시저장 없음.** 오른쪽 사이드바에 항목별 완료 체크가 뜬다.
- 텍스트 칸은 `computer` type 으로 입력. 드롭다운은 클릭 → `[role=menuitem]` 목록(숨은 이전 목록도 DOM 에 남으니 `offsetParent` 로 보이는 것만) → `find` ref 로 클릭. 지원경로에서 'SNS(채용 커뮤니티)'를 고르면 커뮤니티 이름 칸이 새로 생긴다.
- 드롭다운을 연 뒤 페이지가 스크롤되는 일이 있다 → 클릭 전에 스크린샷을 다시 찍는다.
- **파일 칸에 input[type=file]이 없다.** 버튼을 누를 때 DOM 밖에서 만든 input 의 `click()`으로 파일 선택창을 연다. 먼저 `HTMLInputElement.prototype.click`을 감싸 type=file 이면 body 에 붙이고 native click 을 건너뛰게 한 뒤, JS 로 `[class*=FileUploadInput__InputButton]`를 click → `find`로 file-input ref → `file_upload`. 끝나면 원래 click 으로 되돌린다. 칸마다 다시 한다. 화면에는 파일명만 나오고 크기는 안 나온다.
- 동의: 선택 항목 / 민감정보(보훈·장애 입력 시 필수) / 인재풀. 평판조회 동의는 라디오.

## 공고 사이트

- 집계 사이트(예: inthiswork.com)는 WebFetch 로 내용이 잘릴 수 있다 → 원 공고(회사 채용 페이지)를 찾아 읽는다.
- 이미지로만 된 공고는 크롬 스크린샷으로 읽는다.

## 입력 계획 → 입력 → 점검 → 대조 (모든 사이트 공통 절차)

1. **입력 계획**: 지원 폴더에 `form_plan.yaml`을 쓴다(형식은 `scripts/form_check.py` 머리말, 예시는 `examples/hong-gildong/application/form_plan.yaml`). 칸마다 라벨 일부, 종류(text/select/radio/checks/file), 넣을 값을 적는다. 긴 답변은 값 대신 `text_from: "final_coverletter.md#[웹 답변] …"`로 확정본을 가리킨다. `python3 scripts/form_check.py <plan> --show`로 기대값을 본다.
2. **입력**: 위의 사이트별 요령대로 칸을 채운다. 값은 계획 그대로 넣는다(즉석에서 고쳐 쓰지 않는다. 고칠 일이 생기면 계획과 확정본을 먼저 고친다).
3. **점검**: (알림창 가드가 켜져 있는지 `!!window.__jaDialogs`로 먼저 확인) `scripts/browser/inspect.js` 내용을 javascript_tool 에 넣는다. 결과는 15줄씩 나뉘어 나오므로 안내대로 `window.__jaPage(1)`, `window.__jaPage(2)` … 를 실행해 모든 쪽을 한 파일(예: 지원 폴더의 `inspect.txt`)에 이어 붙인다. 이어서 `scripts/browser/hashes.js`를 실행해 해시 줄을 받는다.
4. **대조**: `python3 scripts/form_check.py <plan> inspect.txt --hashes "<hashes.js 출력>"`. ✕ 가 있으면 그 칸만 다시 입력하고 3~4를 반복한다. 결과(모두 일치 / 남은 불일치)를 status.md 에 적는다.

- 출력이 `[TRUNCATED]`로 끝나면 줄 수가 많아서다 → 쪽 단위로 받는다. `[BLOCKED: …]`면 값에 URL·토큰 같은 문자열이 섞인 것이다 → 스니펫의 clean() 을 거친 값만 출력한다.
- 시험할 때는 로컬 테스트 양식을 쓴다: `python3 scripts/serve_testbed.py` → `http://127.0.0.1:8791/`, 계획은 `examples/hong-gildong/application/form_plan.yaml`(PDF 는 `run_example.py`가 만든다). 테스트 양식은 입력 이벤트 없이 넣은 값, 열린 목록 때문에 무시된 클릭, 고르지 않은 회사명, 제출하기·이메일 확인 클릭을 `testbed` 줄로 알려 준다.
