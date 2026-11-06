#!/usr/bin/env bash
# Builds the locked site into ./dist: JARVIS (index.html) + Training mini app (training/index.html).
# Never publishes unencrypted HTML (except the data-free OAuth callback page).
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${JARVIS_APP_PASSWORD:-}" ]; then echo "ERROR: JARVIS_APP_PASSWORD is not set. Refusing to build." >&2; exit 1; fi
BUILD_ID="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d)"; chmod 700 "$TMP"; trap 'rm -rf "$TMP"' EXIT
rm -rf dist && mkdir -p dist/training
cp -r src/icons src/manifest.webmanifest dist/
# Public, unencrypted OAuth redirect page (holds no personal data)
cp src/oura-callback.html dist/
SC=(npx -y staticrypt@3 --short --remember 30 --config .staticrypt.json
  --template-instructions "Enter your passphrase" --template-button "Unlock"
  --template-color-primary "#4fd1ff" --template-color-secondary "#0a0d14"
  --template-placeholder "Passphrase" --template-remember "Keep me signed in")
# 1) Central app
"${SC[@]}" src/index.html -d dist -p "$JARVIS_APP_PASSWORD" --template-title "JARVIS" >/dev/null
# 2) Training mini app: bake Oura data (from outside the repo) into a private temp file, then encrypt.
python3 scripts/build_training_data.py "$TMP/index.html"
"${SC[@]}" "$TMP/index.html" -d dist/training -p "$JARVIS_APP_PASSWORD" --template-title "JARVIS · Training" >/dev/null
rm -f "$TMP/index.html"
# Dark, no-white-flash lock screens + embed handoff
BUILD_ID="$BUILD_ID" python3 - <<'PY'
import os
bid=os.environ["BUILD_ID"]
css='<meta name="theme-color" content="#0a0d14"><meta name="color-scheme" content="dark"><meta name="jarvis-build" content="%s"><style>html,body{background:#0a0d14!important;color:#e7ecf5}.staticrypt-form{background:#121826!important;border:1px solid #1e2738;border-radius:20px}.staticrypt-instructions,.staticrypt-title,label{color:#e7ecf5!important}input[type=password],input[type=text]{background:#0a0d14!important;color:#e7ecf5!important;border:1px solid #1e2738!important;border-radius:12px}</style>'%bid
def patch(p,head_extra="",body_extra="",repl=()):
    s=open(p).read()
    s=s.replace("<head>","<head>"+css+head_extra,1).replace("<html","<html style=\"background:#0a0d14\"",1)
    for a,b in repl:
        assert a in s,("patch target missing",p,a); s=s.replace(a,b,1)
    if body_extra: s=s.replace("</body>",body_extra+"</body>",1)
    open(p,"w").write(s)
# Central: also keep the hashed key for this tab session so embedded mini apps open even without "Keep me signed in".
patch("dist/index.html",
  head_extra='<link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/icon-180.png"><meta name="apple-mobile-web-app-capable" content="yes">',
  repl=[("const { isSuccessful } = await staticrypt.handleDecryptionOfPage(password, isRememberChecked);",
         "const { isSuccessful, hashedPassword } = await staticrypt.handleDecryptionOfPage(password, isRememberChecked);\n                try { if (isSuccessful) sessionStorage.setItem(\"jarvis_key\", hashedPassword); } catch (e) {}")])
# Mini app: inside JARVIS (same origin parent), ask for the key and decrypt; alone it keeps its own lock.
handoff='''<script>(function(){if(window.parent===window)return;
function go(k){if(!k||!document.getElementById("staticrypt-form")||window.__jv)return;window.__jv=1;
 staticrypt.handleDecryptionOfPageFromHash(k,false).then(function(r){if(!r||!r.isSuccessful)window.__jv=0})}
addEventListener("message",function(e){if(e.origin!==location.origin||e.source!==window.parent)return;var m=e.data||{};if(m.type==="jarvis:key")go0(m.key)});
var ready=false,pending=null;function go0(k){if(ready)go(k);else pending=k}
addEventListener("load",function(){setTimeout(function(){
 var remembered=false;try{remembered=!!localStorage.getItem("staticrypt_passphrase")}catch(e){}
 if(remembered)return; /* StatiCrypt's own remember-me unlock handles it */
 ready=true;
 var k=pending;try{k=k||sessionStorage.getItem("jarvis_key")}catch(e){}go(k)},0)});
parent.postMessage({type:"jarvis:hello"},location.origin)})();</script>'''
patch("dist/training/index.html",body_extra=handoff)
PY
for f in dist/index.html dist/training/index.html; do
  grep -q "staticrypt" "$f" && grep -q "staticryptConfig" "$f" || { echo "ERROR: $f not encrypted" >&2; rm -rf dist; exit 1; }
done
# Plaintext leak guards: no app source or Oura fields may appear in the published files
if grep -lE 'const APPS=|"readiness":|"sleepScore"|"workouts":|total_sleep_duration|__OURA_DATA__' dist/index.html dist/training/index.html; then
  echo "ERROR: plaintext leaked into dist" >&2; rm -rf dist; exit 1; fi
echo "Built locked site in dist/ (build $BUILD_ID)"
