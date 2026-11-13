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
Pulls newest `main`, fetches Oura, builds every locked page (JARVIS, Training, Dining, Travel), force-pushes only `dist/` to `gh-pages`, then `scripts/verify_live.sh <build-id>` waits for the new build to be live and checks: root, `/training/`, `/dining/` and `/travel/` are lock screens with no plaintext, callback/manifest/icons return 200.
Exit codes: 0 OK · 1 build/deploy/verify failed · 2 deployed but the Oura fetch failed (page shows last-good data with its "updated" time).

## Dining and Travel mini apps — `/dining/`, `/travel/`
- Templates: `src/dining/index.html`, `src/travel/index.html`, sharing `src/_mini_common.css` / `src/_mini_common.js` (inlined at build). No data in git.
- Same lock, salt and embed handoff as Training (`jarvis:hello` → `jarvis:key`, `jarvis:privacy`, `jarvis:height`, `jarvis:touch`). Both are in `PRIVACY_AWARE`: with the eye on they blur every name, date, count and address, hide confirmation codes entirely and disable email links.
- `build.sh` → `scripts/build_mini_page.py dining|travel` validates and bakes these private files (outside the repo, mode 600) into a temp page, then StatiCrypt encrypts it:
  - `~/.local/share/jarvis/dining.json`, `~/.local/share/jarvis/dining_wishlist.json`, `~/.local/share/jarvis/travel.json`
  - Missing file → page shows "Not connected yet". Invalid file (bad dates, missing fields, full confirmation codes) → build fails, nothing is deployed.
- The pages split upcoming vs past themselves at view time, so they stay correct between scans.

## Dining and Travel refresh
Run by an agent that has the read-only Gmail (`user-Gmail`) and Google Calendar (`user-Google-calendar`) tools. **Read-only: never send, draft, label, trash, RSVP, create, edit or delete anything. Never book or pay.** Never invent data: if a field is not stated in an email/event, leave it out; if a reservation's state is unclear, mark it `unconfirmed` or leave it out.

### 1. Scan Gmail (search_emails, then read_email with maxChars 60000 + write_to_file for details; strip URLs before reading)
| What | Query |
|---|---|
| Resy (booked / changed / cancelled / feedback) | `from:noreply@resy.com newer_than:200d` |
| OpenTable (confirm / cancel / reminder / card-hold) | `from:opentable.com (subject:confirmed OR subject:confirmation OR subject:reservation OR subject:cancelled OR subject:canceled OR subject:cancellation OR subject:modified OR subject:updated OR subject:"let") -subject:points -subject:bonus newer_than:200d` |
| Tock / SevenRooms / Yelp / direct | `(from:exploretock.com OR from:tock.com OR from:sevenrooms.com OR from:yelp.com) (reservation OR booking OR confirmed OR cancelled OR canceled) -subject:thanksgiving newer_than:200d` and `(subject:"reservation confirmed" OR subject:"reservation confirmation" OR subject:"booking confirmed" OR subject:"your table" OR subject:"upcoming reservation") -from:resy.com -from:opentable.com newer_than:200d` (ignore fitness, spa, DMV, rides) |
| Restaurant receipts | `(from:toasttab.com OR from:messaging.squareup.com OR from:clover.com) receipt newer_than:200d` (restaurants/cafés only; skip groceries, invoices, clinics) |
| Delivery ("Ordered in") | `((from:doordash.com subject:"Order Confirmation for") OR (from:doordash.com subject:"Group Order from") OR (from:uber.com subject:"order with Uber Eats") OR (from:grubhub.com subject:order) OR (from:seamless.com subject:order)) newer_than:90d` — follow every `nextPageToken`. Merchant = text after "from" in the subject (DoorDash) or "receipt for X. Total" in the snippet (Uber Eats; use the order time in the snippet). Skip "Thanks for tipping" and tip-adjustment mails. |
| Flights | `(from:jetblue.com OR from:united.com OR from:delta.com OR from:aa.com OR from:alaskaair.com OR from:southwest.com OR from:ana.co.jp OR from:expedia.com) (confirmation OR itinerary OR receipt OR "trip" OR booked) -subject:deal -subject:sale newer_than:365d` |
| Stays / trains / buses / cars | `(from:airbnb.com OR from:vrbo.com OR from:marriott.com OR from:hilton.com OR from:hyatt.com OR from:ihg.com OR from:booking.com OR from:hotels.com OR from:amtrak.com OR from:hertz.com OR from:avis.com OR from:enterprise.com OR from:nationalcar.com OR from:sixt.com OR from:peterpanbus.com OR from:cvent.com) (confirmation OR confirmed OR reservation OR itinerary OR receipt OR cancel) newer_than:365d` and `(subject:"your stay" OR subject:"upcoming trip" OR subject:itinerary OR subject:"booking confirmation" OR subject:"reservation confirmation" OR subject:"trip to" OR subject:e-ticket) -from:resy.com -from:opentable.com newer_than:120d` |

Promotional mail from restaurants/airlines/hotels (newsletters, points, "book now") is never a reservation.

### 2. Scan Calendar (list_events, timeZone America/New_York, maxResults 250, follow nextPageToken)
Calendars: `primary` and the calendar named "Family" (id from `list_calendars`). Ranges: now−365 d → now+365 d.
- Dining: events titled `Reservation at …` / `Reservation: …` (Gmail-created or invites), or meals with a restaurant in title/location (e.g. "Lunch w/ X" at a named place). Calendar-only items get `status:"calendar"`. Gmail-created calendar events are NOT updated on cancellation — a Gmail cancellation always wins.
- Travel: `Flight to …`, `Stay at …`, `Train to …`, `Bus to …`, `Car rental …`, hotel `Reservation at <hotel>`, and multi-day out-of-town event blocks with real addresses (weddings etc.). Confirmation numbers in event descriptions may be used (store only the last 2 characters).

### 3. Merge rules
- Key a reservation by restaurant + date (+ confirmation # when present). Latest email wins: confirmed → changed → cancelled. Cancelled ones go to `cancelled` (shown collapsed), never to `reservations`.
- OpenTable "One more step / requires a credit card" with no later confirmation → `status:"unconfirmed"` + `note`.
- `dined:true` only with post-meal proof: a Resy/OpenTable "wants your feedback"/"thanks for dining" email or a receipt from that restaurant on that date; put the proof in `evidence`.
- Times: the restaurant's local time with its UTC offset, plus `tz` (IANA). Travel item times: ISO with offset as the calendar gives them (shown in ET); date-only items use `YYYY-MM-DD` + `allday:true`.
- Group travel items into trips by destination and contiguous dates. A booking made for someone else (e.g. a parent’s flights) → `traveler:"<who>"`. If the traveler is unclear, leave it out and list it under `excluded`.
- Confirmation codes: store **only** `conf_tail` (last 2 characters). Never store full codes, card numbers, addresses of home, or passenger IDs.
- Links: `https://mail.google.com/mail/u/0/#all/<threadId>` of the newest relevant email.
- Windows: dining past = 180 days, ordered in = 90 days, travel past = 365 days.

### 4. JSON schema (write atomically, mode 600)
`~/.local/share/jarvis/dining.json`
```json
{"schema":1,"updated":"<ISO now>","sources":{"gmail":"<address>","calendar":["primary","Family"]},
 "window":{"recent_days":180,"ordered_in_days":90},
 "reservations":[{"restaurant":"…","start":"2027-01-15T19:30:00-05:00","tz":"America/New_York","party":2,"seating":"Dining room",
   "platform":"Resy|OpenTable|Tock|SevenRooms|Calendar|…","status":"confirmed|changed|unconfirmed|calendar",
   "address":"…","city":"City, ST","dined":true,"evidence":["Resy feedback request"],"source":["gmail","calendar"],
   "link":"https://mail.google.com/mail/u/0/#all/<threadId>","note":"…"}],
 "cancelled":[{"restaurant":"…","start":"<ISO>","tz":"…","platform":"…","link":"…"}],
 "ordered_in":[{"merchant":"…","date":"<ISO>","platform":"DoorDash|Uber Eats|Grubhub|Seamless","group":false,"link":"…"}]}
```
`~/.local/share/jarvis/dining_wishlist.json` (owner-maintained; only change it when GianPaula asks in chat)
```json
{"schema":1,"places":[{"name":"…","city":"…","note":"…","added":"YYYY-MM-DD"}]}
```
`~/.local/share/jarvis/travel.json`
```json
{"schema":1,"updated":"<ISO now>","window":{"past_days":365},
 "trips":[{"id":"slug","title":"…","destination":"…","start":"YYYY-MM-DD","end":"YYYY-MM-DD","traveler":"(only if not GianPaula)",
   "status":"booked|calendar|unconfirmed","note":"…",
   "items":[{"type":"flight|hotel|rental|train|bus|car|event","title":"United 123 EWR → SFO","start":"<ISO or date>","end":"…","allday":true,
     "frm":"EWR","to":"SFO","number":"UA 123","provider":"United","address":"…","conf_tail":"XY","link":"…","source":["gmail","calendar"]}]}],
 "excluded":["what was skipped and why"]}
```
Omit unknown fields (never `null` placeholders, never guesses).

### 5. Build, deploy, verify
```
cd /workspace/jarvis && scripts/deploy.sh
```
(needs `JARVIS_APP_PASSWORD` and `OURA_CLIENT_SECRET` in env; never print them). It pulls newest `main`, rebuilds and encrypts every page, pushes only `dist/` to `gh-pages`, and `scripts/verify_live.sh` confirms all four pages show only the lock screen. If nothing changed in the JSON since the last run, skip the deploy.
