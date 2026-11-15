#!/usr/bin/env bash
# Verify the live site after a deploy.
#   verify_live.sh <build-id>  — wait until that build is served, then check every page is locked.
#   verify_live.sh             — check that the current live pages are lock screens (no wait).
set -uo pipefail
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "usage: verify_live.sh [build-id]" >&2
  echo "  With a build id: wait until that build is live, then check every page is a lock screen." >&2
  echo "  With no argument: check the current live pages are lock screens." >&2
  exit 2
fi
BID="${1:-}"
BASE="https://gianpaulahulten-hub.github.io/jarvis"
PAGES=("" "training/" "dining/" "travel/")
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fetch_all(){ local i=$1 n=0; for p in "${PAGES[@]}"; do
  local url="$BASE/$p"
  [ -n "$BID" ] && url="$url?v=$BID$i"
  if ! curl -fsS "$url" -o "$T/$n.html" 2>/dev/null; then return 1; fi
  if [ -n "$BID" ] && ! grep -q "$BID" "$T/$n.html"; then return 1; fi
  n=$((n+1))
done; }
fail=0
ok=0
if [ -n "$BID" ]; then
  for i in $(seq 1 40); do fetch_all "$i" && { ok=1; break; }; sleep 15; done
  [ $ok = 1 ] || { echo "FAIL: build $BID not live on every page after 10 min"; fail=1; }
else
  fetch_all 0 && ok=1 || { echo "FAIL: could not fetch live pages"; fail=1; }
fi
n=0; for p in "${PAGES[@]}"; do f="$T/$n.html"; n=$((n+1))
  [ -s "$f" ] || { echo "FAIL: /$p not fetched"; fail=1; continue; }
  grep -q staticryptConfig "$f" && grep -q 'id="staticrypt-form"' "$f" || { echo "FAIL: /$p is not a lock screen"; fail=1; }
  grep -qE 'const APPS=|"readiness":|"sleepScore"|"workouts":|total_sleep_duration|Not connected yet|"reservations":|"ordered_in":|"trips":|"conf_tail":|mail\.google\.com|Upcoming trips|Places I want to try' "$f" && { echo "FAIL: plaintext visible in /$p"; fail=1; }
done
for u in "$BASE/oura-callback.html" "$BASE/manifest.webmanifest" "$BASE/icons/icon-192.png"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$u"); [ "$c" = 200 ] || { echo "FAIL: $u -> $c"; fail=1; }
done
if [ $fail = 0 ]; then
  if [ -n "$BID" ]; then
    echo "VERIFIED: build $BID live; root, /training/, /dining/, /travel/ show only the lock screen; callback/manifest/icons 200"
  else
    echo "VERIFIED: live root, /training/, /dining/, /travel/ show only the lock screen; callback/manifest/icons 200"
  fi
fi
exit $fail
