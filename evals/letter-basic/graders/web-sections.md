---
type: regex
pattern: '## \[웹 답변\][^\n]*지원 ?동기[\s\S]*## \[웹 답변\][^\n]*업무 ?경험|## \[웹 답변\][^\n]*업무 ?경험[\s\S]*## \[웹 답변\][^\n]*지원 ?동기'
target: { source: file, path: app/final_coverletter.md }
---
