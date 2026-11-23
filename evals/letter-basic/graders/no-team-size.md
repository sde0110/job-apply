---
type: regex
pattern: '(?:\d+|두|세|네|다섯)\s*(?:명|인)\s*(?:팀|규모|이서|이\s*함께|으로\s*구성)|팀원\s*(?:\d+|두|세|네|다섯)\s*명|(?:팀|조)\s*\(\s*\d+\s*(?:명|인)'
match: not_contains
target: { source: file, path: app/final_coverletter.md }
---
