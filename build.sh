#!/usr/bin/env bash
# Builds the locked site into ./dist. Never publishes unencrypted HTML.
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${JARVIS_APP_PASSWORD:-}" ]; then echo "ERROR: JARVIS_APP_PASSWORD is not set. Refusing to build." >&2; exit 1; fi
rm -rf dist && mkdir -p dist
cp -r src/icons src/manifest.webmanifest dist/
npx -y staticrypt@3 src/index.html -d dist -p "$JARVIS_APP_PASSWORD" --short --remember 30 \
  --template-title "JARVIS" --template-instructions "Enter your passphrase" \
  --template-button "Unlock" --template-color-primary "#4fd1ff" --template-color-secondary "#0a0d14" \
  --template-placeholder "Passphrase" --template-remember "Keep me signed in" >/dev/null
# Dark, no-white-flash lock screen: inject inline dark bg + theme-color + manifest into <head>
python3 - <<'PY'
p="dist/index.html";s=open(p).read()
inj='<meta name="theme-color" content="#0a0d14"><meta name="color-scheme" content="dark"><link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/icon-180.png"><meta name="apple-mobile-web-app-capable" content="yes"><style>html,body{background:#0a0d14!important;color:#e7ecf5}.staticrypt-form{background:#121826!important;border:1px solid #1e2738;border-radius:20px}.staticrypt-instructions,.staticrypt-title,label{color:#e7ecf5!important}input[type=password],input[type=text]{background:#0a0d14!important;color:#e7ecf5!important;border:1px solid #1e2738!important;border-radius:12px}</style>'
s=s.replace("<head>","<head>"+inj,1).replace("<html","<html style=\"background:#0a0d14\"",1)
open(p,"w").write(s)
PY
grep -q "staticrypt" dist/index.html || { echo "ERROR: output not encrypted" >&2; rm -rf dist; exit 1; }
echo "Built locked site in dist/"
