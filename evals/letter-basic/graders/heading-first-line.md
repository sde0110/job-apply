---
type: regex
pattern: '## \[웹 답변\][^\n]*업무 ?경험[^\n]*\n(?:[ \t]*(?:<!--[^\n]*-->)?[ \t]*\n)*[ \t]*\[[^\[\]\n]{2,}\][ \t]*\n'
target: { source: file, path: app/final_coverletter.md }
---
