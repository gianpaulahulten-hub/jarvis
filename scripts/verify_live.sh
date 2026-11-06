#!/usr/bin/env bash
# Verify the live site after a deploy: waits for build $1 to be served, then checks every page is locked.
set -uo pipefail
BID="${1:?build id}"; BASE="https://gianpaulahulten-hub.github.io/jarvis"
for i in $(seq 1 40); do
  curl -fsS "$BASE/?v=$BID$i" -o /tmp/jv_root.html 2>/dev/null && curl -fsS "$BASE/training/?v=$BID$i" -o /tmp/jv_tr.html 2>/dev/null \
    && grep -q "$BID" /tmp/jv_root.html && grep -q "$BID" /tmp/jv_tr.html && break
  sleep 15
done
fail=0
grep -q "$BID" /tmp/jv_root.html && grep -q "$BID" /tmp/jv_tr.html || { echo "FAIL: build $BID not live after 10 min"; fail=1; }
for f in /tmp/jv_root.html /tmp/jv_tr.html; do
  grep -q staticryptConfig "$f" && grep -q 'id="staticrypt-form"' "$f" || { echo "FAIL: $f is not a lock screen"; fail=1; }
  grep -qE 'const APPS=|"readiness":|"sleepScore"|"workouts":|total_sleep_duration|Not connected yet' "$f" && { echo "FAIL: plaintext visible in $f"; fail=1; }
done
for u in "$BASE/oura-callback.html" "$BASE/manifest.webmanifest" "$BASE/icons/icon-192.png"; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$u"); [ "$c" = 200 ] || { echo "FAIL: $u -> $c"; fail=1; }
done
rm -f /tmp/jv_root.html /tmp/jv_tr.html
[ $fail = 0 ] && echo "VERIFIED: build $BID live; root + /training/ show only the lock screen; callback/manifest/icons 200"
exit $fail
