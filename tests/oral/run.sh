#!/usr/bin/env bash
# 구술 테스트 회귀 시험: 빌드 → 가짜 서버(:8000, 생각 시간 25초) + 웹(:8080) → 휴대폰·PC·마이크 끊김 흐름
# 일부만: run.sh smoke.py  /  run.sh "flow.py mobile"
# 필요: deno, python3 + playwright, google-chrome, PDFLIB(html2canvas·jspdf가 든 node_modules 경로)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DENO="${DENO:-deno}"
WEB=/tmp/002web
cd "$ROOT" && node scripts/build.mjs | tail -1 || exit 1
pkill -f "unstable-sloppy-imports index.ts" 2>/dev/null; pkill -f "m http.server 8080" 2>/dev/null; sleep 1
( cd "$ROOT/supabase/functions/api" && ORAL_THINK_SEC=25 ORAL_THINK_MIN_SEC=10 FAKE_DB=1 POST_DELAY_SEC=3 FAKE_MAIL=1 FAKE_PUSH=1 FAKE_AI="$(cat "$ROOT/tests/oral/fakeai.json")" FAKE_AI_MAP="$(cat "$ROOT/tests/oral/fakeai_map.json")" FAKE_NL="$(cat "$ROOT/tests/oral/fakenl.json")" FAKE_ART="$(cat "$ROOT/tests/oral/fakeart.json")" FAKE_GOOGLE="$(cat "$ROOT/tests/oral/fakegoogle.json")" \
  setsid nohup "$DENO" run -A --unstable-sloppy-imports index.ts > /tmp/api.log 2>&1 < /dev/null & ) > /dev/null 2>&1
rm -rf "$WEB" && cp -r "$ROOT/dist" "$WEB"
sed -i 's#"api":"[^"]*"#"api":"http://localhost:8000"#' "$WEB/runtime/config.js"
( cd "$WEB" && setsid nohup python3 -m http.server 8080 > /tmp/web.log 2>&1 < /dev/null & ) > /dev/null 2>&1
for i in $(seq 30); do curl -s -o /dev/null -X POST localhost:8000 -d '{}' && break; sleep 1; done
fail=0
if [ $# = 0 ]; then echo "=== px/unit.js"; node "$ROOT/tests/px/unit.js" | grep -vE '^PASS'; [ "${PIPESTATUS[0]}" = 0 ] || fail=1; fi
if [ $# = 0 ]; then echo "=== rubric_unit.ts"; ( cd "$ROOT/supabase/functions/api" && FAKE_DB=1 "$DENO" run -A --unstable-sloppy-imports "$ROOT/tests/rubric_unit.ts" ) | grep -vE '^PASS'; [ "${PIPESTATUS[0]}" = 0 ] || fail=1; fi
if [ $# = 0 ]; then echo "=== books_unit.ts"; ( cd "$ROOT/supabase/functions/api" && FAKE_DB=1 "$DENO" run -A --unstable-sloppy-imports "$ROOT/tests/books_unit.ts" ) | grep -vE '^PASS'; [ "${PIPESTATUS[0]}" = 0 ] || fail=1; fi
TESTS=("${@}"); [ ${#TESTS[@]} = 0 ] && TESTS=("../e2e.py" "smoke.py" "shelf.py" "qref.py" "essay.py" "flow.py mobile" "flow.py desktop" "miclost.py" "google.py" "admin.py" "post.py" "guide.py")
for t in "${TESTS[@]}"; do
  echo "=== $t"; python3 "$ROOT/tests/oral/"$t 2>&1 | grep -E '^(PASS|FAIL)|^[0-9]+/[0-9]+|^errors' | grep -vE '^PASS' ; r=${PIPESTATUS[0]}
  [ "$r" = 0 ] || fail=1
done
[ $fail = 0 ] && echo "ALL PASS" || echo "SOME FAILED"
exit $fail
