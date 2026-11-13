#!/usr/bin/env python3
"""Bake private JSON (outside the repo) into a mini app template and write the PLAINTEXT page to argv[2]
(build.sh passes a private temp dir, never dist/). Usage: build_mini_page.py dining|travel OUT_PATH
Missing JSON -> data null -> the page shows "Not connected yet". Invalid JSON/schema -> exit 1 (never guess)."""
import json, os, sys, re
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
        for i in t["items"]:
            if i.get("start"): iso(i["start"], i.get("title"))
            if i.get("end"): iso(i["end"], i.get("title"))
            ct = i.get("conf_tail")
            if ct is not None and len(str(ct)) > 2: sys.exit(f"ERROR: conf_tail must be at most the last 2 characters ({i.get('title')})")
            for bad in ("confirmation", "conf", "code", "pnr"):
                if bad in i: sys.exit(f"ERROR: full confirmation codes must not be stored ({i.get('title')}: {bad})")
if app == "dining":
    d = load("dining.json")
    if d is not None: check_dining(d)
    wl = load("dining_wishlist.json") or {"places": []}
    data = {"dining": d, "wishlist": wl} if d is not None or wl.get("places") else None
    if d is None and data is not None: data["dining"] = None
    summary = "none (not connected)" if d is None else f"{len(d.get('reservations',[]))} reservations, {len(d.get('ordered_in',[]))} orders, {len(wl.get('places',[]))} wishlist"
elif app == "travel":
    d = load("travel.json")
    if d is not None: check_travel(d)
    data = {"travel": d} if d is not None else None
    summary = "none (not connected)" if d is None else f"{len(d.get('trips',[]))} trips"
else:
    sys.exit("usage: build_mini_page.py dining|travel OUT")
tpl = open(os.path.join(SRC, app, "index.html")).read()
css = open(os.path.join(SRC, "_mini_common.css")).read()
js = open(os.path.join(SRC, "_mini_common.js")).read()
for ph in ("/*__COMMON_CSS__*/", "/*__COMMON_JS__*/", "/*__DATA__*/null"): assert ph in tpl, (app, ph)
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
html = tpl.replace("/*__COMMON_CSS__*/", css).replace("/*__COMMON_JS__*/", js).replace("/*__DATA__*/null", blob)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: f.write(html)
print(f"{app} data: {summary}", file=sys.stderr)
