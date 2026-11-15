#!/usr/bin/env python3
"""Bake private JSON (outside the repo) into a mini app template and write the PLAINTEXT page to argv[2]
(build.sh passes a private temp dir, never dist/). Usage: build_mini_page.py dining|travel OUT_PATH
Missing JSON -> data null -> the page shows "Not connected yet". Invalid JSON/schema -> exit 1 (never guess).
Travel also merges ~/.local/share/jarvis/travel_manual.json (owner-provided trips) into the page; the
Gmail/Calendar rescan may rewrite travel.json but must never touch travel_manual.json."""
import copy, json, os, re, sys
from datetime import datetime
app, out_path = sys.argv[1], sys.argv[2]
DATA = os.environ.get("JARVIS_DATA_DIR", os.path.expanduser("~/.local/share/jarvis"))
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p): return None
    with open(p) as f: return json.load(f)
def iso(s, where):
    try: datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: sys.exit(f"ERROR: {app}: bad date {s!r} in {where}")
def check_dining(d):
    for r in d.get("reservations", []):
        for k in ("restaurant", "start", "status"):
            if not r.get(k): sys.exit(f"ERROR: dining reservation missing {k}: {r}")
        if r["status"] not in ("confirmed", "changed", "unconfirmed", "calendar"): sys.exit(f"ERROR: bad status {r['status']}")
        iso(r["start"], r["restaurant"])
        if "T" in r["start"] and not re.search(r"([+-]\d\d:\d\d|Z)$", r["start"]): sys.exit(f"ERROR: dining start needs a UTC offset: {r['start']}")
    for c in d.get("cancelled", []): iso(c["start"], c.get("restaurant"))
    for o in d.get("ordered_in", []):
        if not o.get("merchant"): sys.exit("ERROR: ordered_in item without merchant")
        iso(o["date"], o["merchant"])
def check_travel(d):
    for t in d.get("trips", []):
        for k in ("id", "title", "start", "items"):
            if k not in t: sys.exit(f"ERROR: trip missing {k}: {t.get('title')}")
        iso(t["start"], t["title"]); iso(t.get("end") or t["start"], t["title"])
        if t.get("purpose") not in (None, "work"): sys.exit(f"ERROR: bad purpose {t.get('purpose')!r} in {t.get('title')}")
        for i in t["items"]:
            if i.get("start"): iso(i["start"], i.get("title"))
            if i.get("end"): iso(i["end"], i.get("title"))
            ct = i.get("conf_tail")
            if ct is not None and len(str(ct)) > 2: sys.exit(f"ERROR: conf_tail must be at most the last 2 characters ({i.get('title')})")
            for bad in ("confirmation", "conf", "code", "pnr"):
                if bad in i: sys.exit(f"ERROR: full confirmation codes must not be stored ({i.get('title')}: {bad})")

# --- merge owner-provided trips into a Gmail/Calendar scan (dedupe by flight number + date) ---
_NYC = {"JFK", "EWR", "LGA", "NYC"}
def _norm_num(n):
    if not n: return None
    s = re.sub(r"[\s\-]+", "", str(n).upper())
    m = re.match(r"^([A-Z]{2}|[A-Z]\d|\d[A-Z])0*(\d+)$", s)
    return (m.group(1) + m.group(2)) if m else s
def _date(s):
    return (s or "")[:10]
def _flight_key(i):
    if (i or {}).get("type") != "flight": return None
    n, d = _norm_num(i.get("number") or ""), _date(i.get("start"))
    return (n, d) if n and d else None
def _dest_key(s):
    s = re.sub(r",?\s*[A-Za-z]{2}$", "", (s or "").strip())
    return re.sub(r"\s+", " ", s).casefold()
def _range(t):
    a, b = _date(t.get("start")), _date(t.get("end") or t.get("start"))
    return a, b or a
def _overlap(a, b):
    a0, a1 = _range(a); b0, b1 = _range(b)
    if not a0 or not b0: return False
    # A trip with an unknown return overlaps any other trip that includes its start (same destination handled by caller)
    if a.get("return_unknown"): a1 = max(a1, a0)
    if b.get("return_unknown"): b1 = max(b1, b0)
    if a.get("return_unknown") and b0 <= a0 <= b1: return True
    if b.get("return_unknown") and a0 <= b0 <= a1: return True
    return a0 <= b1 and b0 <= a1
def _same_dest(a, b):
    da, db = _dest_key(a.get("destination") or ""), _dest_key(b.get("destination") or "")
    return bool(da and db and (da == db or da in db or db in da))
def _has_return(trip):
    flights = [i for i in trip.get("items") or [] if i.get("type") == "flight"]
    if len(flights) < 2: return False
    out = next((i for i in flights if i.get("start")), flights[0])
    home, dest = (out.get("frm") or "").upper(), (out.get("to") or "").upper()
    for i in flights:
        if i is out: continue
        to, frm = (i.get("to") or "").upper(), (i.get("frm") or "").upper()
        if home and to and (to == home or (home in _NYC and to in _NYC)): return True
        if dest and frm == dest and to and to != dest: return True
    return False
def _merge_item(manual, scan):
    """Same flight: keep manual work details (seat, gate, aircraft, notes); prefer scan confirmation/link/times when present."""
    out = copy.deepcopy(manual)
    if not scan: return out
    for k, v in scan.items():
        if k == "source": continue
        if k in ("seat", "cabin", "dep_gate", "arr_terminal", "arr_gate", "aircraft"):
            if not out.get(k) and v: out[k] = v
            continue
        if k == "note":
            notes = [n for n in (out.get("note"), v) if n]
            # unique, manual first
            seen, kept = set(), []
            for n in notes:
                if n not in seen:
                    seen.add(n); kept.append(n)
            if kept: out["note"] = " · ".join(kept)
            continue
        if k in ("conf_tail", "link") and v:
            out[k] = v
            continue
        if k in ("start", "end", "frm", "to", "number", "provider", "title") and v and (k not in out or not out.get(k)):
            out[k] = v
            continue
        if k in ("start", "end", "frm", "to", "number", "provider") and v:
            out[k] = v  # scan times/routing may be newer
            continue
        if k not in out or out[k] in (None, "", [], {}):
            out[k] = v
    src = []
    for s in (out.get("source") or []) + (scan.get("source") or []):
        if s not in src: src.append(s)
    if src: out["source"] = src
    return out
def _trip_start_end(trip):
    dates = [_date(trip.get("start"))]
    if trip.get("end"): dates.append(_date(trip["end"]))
    for i in trip.get("items") or []:
        if i.get("start"): dates.append(_date(i["start"]))
        if i.get("end") and not i.get("allday"): dates.append(_date(i["end"]))
        elif i.get("end"): dates.append(_date(i["end"]))
    dates = [d for d in dates if d]
    if not dates: return
    trip["start"] = min(dates)
    if trip.get("return_unknown") and not _has_return(trip):
        trip.pop("end", None)
    else:
        trip["end"] = max(dates)
        if _has_return(trip):
            trip["return_unknown"] = False
def _merge_trip(manual, scan):
    out = copy.deepcopy(scan) if scan else copy.deepcopy(manual)
    src = manual if manual else {}
    # Owner-provided fields win for purpose, work notes, id if this started as a manual trip
    if src.get("purpose"): out["purpose"] = src["purpose"]
    if src.get("id") and (not scan or src.get("id")): out["id"] = src["id"] if not (scan and scan.get("id")) else (scan.get("id") or src.get("id"))
    if src.get("title") and (not scan or not scan.get("title")): out["title"] = src["title"]
    if src.get("destination"):
        if not out.get("destination") or len(str(src["destination"])) >= len(str(out.get("destination") or "")):
            out["destination"] = src["destination"]
    if src.get("status") == "booked" or out.get("status") == "booked":
        out["status"] = "booked"
    notes = []
    for n in (src.get("note"), (scan or {}).get("note")):
        if n and n not in notes: notes.append(n)
    items, used_scan = [], set()
    scan_items = list((scan or {}).get("items") or [])
    scan_by_key = {}
    for idx, it in enumerate(scan_items):
        k = _flight_key(it)
        if k and k not in scan_by_key: scan_by_key[k] = idx
    for it in (src.get("items") or [] if scan else []):
        k = _flight_key(it)
        if k is not None and k in scan_by_key:
            j = scan_by_key[k]
            items.append(_merge_item(it, scan_items[j]))
            used_scan.add(j)
        else:
            items.append(copy.deepcopy(it))
    if not scan:
        items = copy.deepcopy(src.get("items") or [])
    for idx, it in enumerate(scan_items):
        if idx not in used_scan:
            items.append(copy.deepcopy(it))
    # When this is a pure manual trip (no scan), items already set
    if scan and not src.get("items"):
        items = copy.deepcopy(scan_items)
    out["items"] = items
    if src.get("return_unknown") and not _has_return(out):
        out["return_unknown"] = True
    elif _has_return(out):
        out["return_unknown"] = False
    if out.get("return_unknown") is False:
        out.pop("return_unknown", None)
        notes = [n for n in notes if not re.search(r"return (flight )?not (known|booked|found)", n, re.I)]
    if notes: out["note"] = " · ".join(notes)
    elif "note" in out and not out["note"]: out.pop("note", None)
    _trip_start_end(out)
    return out
def _trips_match(manual, scan):
    mkeys = {_flight_key(i) for i in (manual.get("items") or [])}
    skeys = {_flight_key(i) for i in (scan.get("items") or [])}
    mkeys.discard(None); skeys.discard(None)
    if mkeys and skeys and (mkeys & skeys): return True
    return _same_dest(manual, scan) and _overlap(manual, scan)
def merge_manual_travel(scan, manual):
    """Return a travel.json-shaped object: scan trips plus owner-provided trips, deduped."""
    if not manual or not manual.get("trips"):
        return scan
    if scan is None:
        out = {"schema": 1, "trips": [], "window": {"past_days": 365}}
    else:
        out = copy.deepcopy(scan)
    scan_trips = list(out.get("trips") or [])
    used = set()
    merged = []
    for mt in manual.get("trips") or []:
        hits = [i for i, st in enumerate(scan_trips) if i not in used and _trips_match(mt, st)]
        if not hits:
            merged.append(_merge_trip(mt, None))
            continue
        acc = copy.deepcopy(scan_trips[hits[0]]); used.add(hits[0])
        for i in hits[1:]:
            acc = _merge_trip(acc, scan_trips[i]); used.add(i)
        merged.append(_merge_trip(mt, acc))
    for i, st in enumerate(scan_trips):
        if i not in used:
            merged.append(copy.deepcopy(st))
    out["trips"] = merged
    return out

if app == "dining":
    d = load("dining.json")
    if d is not None: check_dining(d)
    wl = load("dining_wishlist.json") or {"places": []}
    data = {"dining": d, "wishlist": wl} if d is not None or wl.get("places") else None
    if d is None and data is not None: data["dining"] = None
    summary = "none (not connected)" if d is None else f"{len(d.get('reservations',[]))} reservations, {len(d.get('ordered_in',[]))} orders, {len(wl.get('places',[]))} wishlist"
elif app == "travel":
    d = load("travel.json")
    manual = load("travel_manual.json")
    if manual is not None: check_travel(manual)
    d = merge_manual_travel(d, manual)
    if d is not None: check_travel(d)
    data = {"travel": d} if d is not None else None
    n_man = len((manual or {}).get("trips") or [])
    summary = "none (not connected)" if d is None else f"{len(d.get('trips',[]))} trips" + (f" (including {n_man} manual)" if n_man else "")
else:
    sys.exit("usage: build_mini_page.py dining|travel OUT")
tpl = open(os.path.join(SRC, app, "index.html")).read()
css = open(os.path.join(SRC, "_mini_common.css")).read()
js = open(os.path.join(SRC, "_mini_common.js")).read()
for ph in ("/*__COMMON_CSS__*/", "/*__COMMON_JS__*/", "/*__DATA__*/null"): assert ph in tpl, (app, ph)
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
html = tpl.replace("/*__COMMON_CSS__*/", css).replace("/*__COMMON_JS__*/", js).replace("/*__DATA__*/null", blob)
os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: f.write(html)
print(f"{app} data: {summary}", file=sys.stderr)
