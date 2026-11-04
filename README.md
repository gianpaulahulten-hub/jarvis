# JARVIS

GianPaula's password-locked, mobile-first PWA: Budget, Investments, Macros, Training, Pets, Dining, Travel, Daily Newsletter.

- `src/` – unencrypted source (never published directly).
- `build.sh` – encrypts `src/index.html` with StatiCrypt into `dist/` (dark lock screen, title "JARVIS"). Requires `JARVIS_APP_PASSWORD`; fails if unset.
- Only `dist/` (encrypted) may ever be published, e.g. to a `gh-pages` branch. Never deploy without the lock.

## Build
```
JARVIS_APP_PASSWORD='…' ./build.sh   # output: dist/
```

## Deploy (not done yet)
```
JARVIS_APP_PASSWORD='…' ./build.sh
cd dist && git init -b gh-pages && git add -A && git commit -m deploy
git push -f https://github.com/gianpaulahulten-hub/jarvis.git gh-pages
gh api -X POST repos/gianpaulahulten-hub/jarvis/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'
```
Site: https://gianpaulahulten-hub.github.io/jarvis/

## Tabs and mini apps
Each tab is a live iframe of the mini app's own published page. Set the `url` in the `APPS` registry in `src/index.html`. Empty url shows "Not connected yet". No data, numbers, or sample charts live in JARVIS.

## Letting embedded mini apps open inside JARVIS (but stay locked alone)
Each mini app is its own StatiCrypt page. Two options:
1. **Shared remember-me (simplest):** host mini apps under the same origin (`gianpaulahulten-hub.github.io/<app>`), encrypt them with the same password and `--remember`. StatiCrypt keeps the hashed passphrase in `localStorage` (`staticrypt_passphrase`) per origin, so after unlocking JARVIS, same-origin mini apps unlock automatically. Opened alone on a device that never unlocked, they show their own lock.
2. **postMessage handshake (works across origins):** in the mini app's lock page, when `window.parent !== window`, post `{type:"jarvis:hello"}` to the parent. JARVIS checks the iframe's source/origin and replies `{type:"jarvis:key", key}` (the stored hashed passphrase); the mini app calls StatiCrypt's decrypt with it. JARVIS also sends `{type:"jarvis:privacy", hidden}` so mini apps can blur their numbers when the eye button is on.

## Privacy eye
The header eye blurs everything marked `.private` (all embed slots), persisted in `localStorage` (`jarvis.hide`).
