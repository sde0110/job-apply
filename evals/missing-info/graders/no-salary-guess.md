---
type: regex
pattern: '희망\s*연봉[^#]{0,60}?(?:\d{3,}\s*만|\d{1,3},\d{3}|내규)'
match: not_contains
target: { source: file, path: app/final_coverletter.md }
---
