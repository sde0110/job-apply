---
type: regex
pattern: '## \[웹 답변\][^\n]*지원 ?동기[^\n]*\n[\s\S]{200,}'
target: { source: file, path: app/final_coverletter.md }
---
