# 사용자 데이터 폴더

위치: 환경변수 `JOB_APPLY_HOME`, 없으면 `~/.job-apply`. 엔진(스킬)에는 개인 정보를 두지 않는다.
권한은 폴더 700, 파일 600을 권장한다. 이 폴더는 저장소에 커밋하지 않는다.

| 파일 | 필수 | 예시 |
|---|---|---|
| profile.yaml | 예 | `templates/data/profile.example.yaml` |
| sources.yaml | 예 | `templates/data/sources.example.yaml` |
| rules.yaml | 아니오 (없으면 엔진 기본: 입력 및 임시저장, 윤문·PDF 검증은 요청 시) | `templates/data/rules.example.yaml` |
| theme.yaml | 아니오 (없으면 neutral) | `templates/data/theme.example.yaml` — `preset` + 덮어쓸 `colors` |
| portfolio.yaml | 아니오 | `scripts/render_portfolio.py` 머리말 |

## 원칙

- profile.yaml 의 모든 사실에 `verified`를 단다. 지원서에는 원본·사용자 확인 값을 우선 쓰고, 2차·미확인 값은 확인 후 쓴다.
- 자료마다 수치가 다르면 사용자에게 하나를 고르게 하고 `rules.yaml` `fixed_metrics`에 남긴다.
- 사용자가 "앞으로는 …" 형태로 정한 것은 rules.yaml 에, 지원서 반복 선택값은 profile.yaml `form_defaults`에 쓴다.
- 문체 지적("이런 표기 쓰지 마", "이 글처럼 써")은 rules.yaml `style`에 쓴다. 키와 기본값은 `scripts/style_check.py` 머리말과 `templates/data/rules.example.yaml`에 있다. 사용자가 좋다고 한 글은 `style.examples`에 경로로 남긴다.
- 지원별 산출물(resume.yaml, letter.yaml, md, PDF)은 sources.yaml `output_dir` 아래 지원 폴더에 둔다.
