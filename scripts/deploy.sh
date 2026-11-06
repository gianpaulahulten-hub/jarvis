#!/usr/bin/env bash
# One command for the scheduled refresh: newest main -> fresh Oura data -> locked build -> gh-pages -> live verification.
# Needs env JARVIS_APP_PASSWORD (and OURA_CLIENT_SECRET for token refresh). Never prints either.
# Exit codes: 0 ok, 1 build/deploy/verify failed, 2 deployed with last-good Oura data because the fetch failed.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull -q --ff-only origin main
fetch=0; python3 scripts/oura_fetch.py || { fetch=$?; echo "WARNING: Oura fetch failed (exit $fetch); building with last-good data" >&2; }
./build.sh
BID=$(grep -o 'name="jarvis-build" content="[^"]*' dist/index.html | head -1 | sed 's/.*content="//')
( cd dist && rm -rf .git && git init -q -b gh-pages && git add -A \
  && git -c user.name=gianpaulahulten-hub -c user.email=gianpaulahulten-hub@users.noreply.github.com commit -qm "deploy $BID" \
  && git push -qf https://github.com/gianpaulahulten-hub/jarvis.git gh-pages )
scripts/verify_live.sh "$BID"
[ "$fetch" = 0 ] || exit 2
