#!/usr/bin/env bash
set -euo pipefail
bash "$(dirname "$0")/../_fixtures/seed.sh"
F="$(dirname "$0")/../_fixtures"
cp "$(dirname "$0")/../../skills/job-apply/examples/hong-gildong/application/final_coverletter.md" good.md
cp "$F/bad_final.md" bad.md
