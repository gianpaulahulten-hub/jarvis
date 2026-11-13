#!/usr/bin/env bash
# Verify the live site after a deploy: waits for build $1 to be served, then checks every page is locked.
set -uo pipefail
BID="${1:?build id}"; BASE="https://gianpaulahulten-hub.github.io/jarvis"
PAGES=("" "training/" "dining/" "travel/")
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fetch_all(){ local i=$1 n=0; for p in "${PAGES[@]}"; do
  curl -fsS "$BASE/$p?v=$BID$i" -o "$T/$n.html" 2>/dev/null && grep -q "$BID" "$T/$n.html" || return 1; n=$((n+1)); done; }
ok=0; for i in $(seq 1 40); do fetch_all "$i" && { ok=1; break; }; sleep 15; done
fail=0
[ $ok = 1 ] || { echo "FAIL: build $BID not live on every page after 10 min"; fail=1; }
n=0; for p in "${PAGES[@]}"; do f="$T/$n.html"; n=$((n+1))
  [ -s "$f" ] || { echo "FAIL: /$p not fetched"; fail=1; continue; }
  grep -q staticryptConfig "$f" && grep -q 'id="staticrypt-form"' "$f" || { echo "FAIL: /$p is not a lock screen"; fail=1; }
  grep -qE 'const APPS=|"readiness":|"sleepScore"|"workouts":|total_sleep_duration|Not connected yet|"reservations":|"ordered_in":|"trips":|"conf_tail":|mail\.google\.com|Upcoming trips|Places I want to try' "$f" && { echo "FAIL: plaintext visible in /$p"; fail=1; }
done
for u in "$BASE/oura-callback.html" "$BASE/manifest.webmanifest" "$BASE/icons/icon-192.png"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$u"); [ "$c" = 200 ] || { echo "FAIL: $u -> $c"; fail=1; }
done
[ $fail = 0 ] && echo "VERIFIED: build $BID live; root, /training/, /dining/, /travel/ show only the lock screen; callback/manifest/icons 200"
exit $fail
