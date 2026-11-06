# JARVIS

GianPaula's password-locked, mobile-first PWA: Budget, Investments, Macros, Training, Pets, Dining, Travel, Daily Newsletter.

- `src/` – unencrypted source (never published directly).
- `build.sh` – encrypts `src/index.html` with StatiCrypt into `dist/` (dark lock screen, title "JARVIS"). Requires `JARVIS_APP_PASSWORD`; fails if unset.
- Only `dist/` (encrypted) may ever be published, e.g. to a `gh-pages` branch. Never deploy without the lock.

## Build
```
JARVIS_APP_PASSWORD='…' ./build.sh   # output: dist/
```

## Deploy (manual)
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

## Training mini app (Oura) — `/training/`
- Source template: `src/training/index.html` (no data in git). Same origin as JARVIS (`/jarvis/training/`), encrypted with the same passphrase and salt (`.staticrypt.json`).
- Opened alone it shows its own lock screen. Inside JARVIS it unlocks via the postMessage handshake (`jarvis:hello` → `jarvis:key`): JARVIS answers with the remembered hashed key, or with the per-tab `sessionStorage.jarvis_key` that `build.sh` makes the JARVIS lock page store on unlock (so it works even without "Keep me signed in").
- It honors the eye (`jarvis:privacy` + same-origin `localStorage["jarvis.hide"]`), blurring every number and chart, so JARVIS doesn't blur the whole slot for it (`PRIVACY_AWARE` in `src/index.html`).
- It posts `jarvis:height` (JARVIS sizes the iframe, the page scrolls normally) and forwards touches (`jarvis:touch`) so pull-to-refresh works over it.

### Data flow (no personal data ever in git)
1. `scripts/oura_fetch.py` reads `~/.config/jarvis/oura_client_id`, `~/.config/jarvis/oura_tokens.json` (600) and env `OURA_CLIENT_SECRET`; refreshes only within 3 days of expiry or on a 401 from the `personal_info` probe (refresh tokens are single-use → new token file written atomically under a lock). Writes `~/.local/share/jarvis/oura.json` (outside the repo, 600). Endpoints that fail are recorded, never faked.
2. `build.sh` → `scripts/build_training_data.py` compacts that data into a private temp file and StatiCrypt encrypts it to `dist/training/index.html`. Build fails if any plaintext app source or Oura field shows up in `dist/`.

## One-command refresh + deploy (used by the scheduled refresh)
```
cd /workspace/jarvis && scripts/deploy.sh
```
Pulls newest `main`, fetches Oura, builds both locked pages, force-pushes only `dist/` to `gh-pages`, then `scripts/verify_live.sh <build-id>` waits for the new build to be live and checks: root and `/training/` are lock screens with no plaintext, callback/manifest/icons return 200.
Exit codes: 0 OK · 1 build/deploy/verify failed · 2 deployed but the Oura fetch failed (page shows last-good data with its "updated" time).
