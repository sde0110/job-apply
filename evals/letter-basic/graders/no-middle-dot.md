---
type: regex
pattern: '^(?![#<|>-]).*·'
flags: m
match: not_contains
target: { source: file, path: app/final_coverletter.md }
---
