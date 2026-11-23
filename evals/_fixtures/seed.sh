#!/usr/bin/env bash
# 평가 실행 공간에 가상 인물(홍길동)의 사용자 데이터와 공고를 깐다. 각 케이스의 scaffold.sh 가 부른다.
# - ~/.job-apply/        profile.yaml, rules.yaml, sources.yaml (예제 데이터, 경로만 실행 공간에 맞춤)
# - ~/materials/         경험정리.md, 이력서.md, 증빙/
# - ~/postings/          greendata.md(예제 공고) + 이 폴더의 posting_*.md
# 평가 실행의 HOME 은 임시 폴더라 실제 사용자 데이터에는 닿지 않는다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EX="$HERE/../../skills/job-apply/examples/hong-gildong"
mkdir -p "$HOME/.job-apply" "$HOME/materials" "$HOME/postings"
cp -R "$EX/materials/." "$HOME/materials/"
cp "$EX/data/profile.yaml" "$EX/data/rules.yaml" "$HOME/.job-apply/"
sed -e "s#{EXAMPLE_DIR}/materials#$HOME/materials#g" -e "s#{HOME}/applications#$PWD#g" \
  "$EX/data/sources.yaml" > "$HOME/.job-apply/sources.yaml"
cp "$EX/posting.md" "$HOME/postings/greendata.md"
cp "$HERE"/posting_*.md "$HOME/postings/"
