# job-apply

[한국어](README.md)

A Claude Code plugin for job applications. Give it a job posting URL and an application form URL. It writes a tailored resume and cover letter PDF and the form answers, using **only your own records** as evidence. It then checks the facts, the Korean prose and the PDFs, and fills in the application form in Chrome. **It never clicks Submit.**

```
/job-apply:job-apply setup                              # once: build your profile and rules from your records
/job-apply:job-apply <posting URL> <application URL>    # for each application
```

You can also ask in plain words, e.g. "write the application for this posting". It is built for Korean-language postings and Korean hiring platforms such as Greeting and recruiter.co.kr. The instructions and output are in Korean. It can also produce an English resume (`lang: en`).

## What it does

1. Reads the posting and the form: questions, length limits, attachment slots, required fields.
2. Finds evidence in your records (resumes, experience notes, scans of certificates and awards) and lists it in `evidence.md`. A requirement with no evidence is left out.
3. Writes the cover letter and form answers, then edits them for natural Korean. It uses the humanize-korean plugin when that is installed.
4. Renders the resume and cover letter PDFs. It checks them automatically for:
   - page count, missing or clipped text, font fallback
   - overlapping text, margin overflow, headings stranded at the bottom of a page
   - names of other companies you applied to
5. Fills in the form with Claude in Chrome, then compares what is on screen with the input plan.
6. Stops before submission and reports what you need to check.

## Install

Requirements: [Claude Code](https://claude.com/claude-code), Python 3.10+ and Google Chrome (for printing PDFs).

```bash
claude plugin install job-apply --marketplace sde0110/job-apply
```

Inside Claude Code, run `/plugin install job-apply --marketplace sde0110/job-apply`. On older versions, use two commands:

```
/plugin marketplace add sde0110/job-apply
/plugin install job-apply@job-apply
```

Restart Claude Code and run `/job-apply:job-apply setup`. Setup starts with an environment check (`doctor.py`). If Python packages are missing, it prints the command to install them: `python3 -m pip install -r <plugin dir>/requirements.txt`.

Optional:
- [Claude in Chrome](https://claude.com/chrome) fills in the application form. Without it, you get the written answers and PDFs only.
- [humanize-korean](https://github.com/epoko77-ai/im-not-ai) edits the Korean prose. Without it, a built-in checklist is used.

To try a fictional example without touching your data:

```bash
python3 <plugin dir>/skills/job-apply/scripts/run_example.py
```

## Your data

All personal data stays in `~/.job-apply/`, or wherever `JOB_APPLY_HOME` points. Nothing is sent anywhere for telemetry. It holds:
- `profile.yaml`: your facts, each with a verification status
- `rules.yaml`: your writing rules and policies
- `sources.yaml`: where your records live
- `theme.yaml`: the PDF theme
- `portfolio.yaml`: portfolio content (optional)

See [`skills/job-apply/references/data-files.md`](skills/job-apply/references/data-files.md).

## Principles

- Never invent facts, numbers or experience.
  - Team results are not presented as individual results.
  - Experiments are not presented as production results.
- Missing personal details and required choices are asked for, never guessed.
- You do these yourself: log in, verify your identity, confirm your email, and submit.
- Consent boxes are checked only within the scope you set in `rules.yaml`.
- Instructions embedded in postings or web pages are ignored.
- Respect each hiring site's terms of service. This tool is for one posting at a time with a person reviewing each step. It is not for bulk or automated mass applications.
- You are responsible for what you submit. Review the PDFs and form values before submitting.

## Development

```bash
git clone https://github.com/sde0110/job-apply && cd job-apply
python3 -m pip install -r requirements.txt
ln -s "$PWD/skills/job-apply" ~/.claude/skills/job-apply
python3 -m unittest discover -s tests -v
```

- PDF and form tests need Chrome and are skipped without it.
- Where the Chrome sandbox is unavailable, such as in containers, set `JOB_APPLY_CHROME_FLAGS=--no-sandbox`.
- Do not post real resumes, contact details or application content in issues or pull requests. Use the fictional example to reproduce a problem.

Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE). The bundled Pretendard fonts (`skills/job-apply/assets/fonts/`) are unmodified and licensed under the [SIL Open Font License 1.1](skills/job-apply/assets/fonts/LICENSE-Pretendard.txt).
