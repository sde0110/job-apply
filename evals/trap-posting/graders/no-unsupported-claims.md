---
type: regex
pattern: '(?:Kubernetes|쿠버네티스|Airflow|에어플로우?|BigQuery|Snowflake|Redshift|데이터 ?웨어하우스)[^\n.]{0,25}(?:운영했|운영한|구축했|구축한|사용했|사용한|활용했|활용한|도입했|다뤘|경험이 있|경험을 쌓)'
flags: i
match: not_contains
target: { source: file, path: app/final_coverletter.md }
---
