#!/usr/bin/env python3
"""Fetch GianPaula's Oura data for the JARVIS Training mini app.

- Reads OAuth client id from ~/.config/jarvis/oura_client_id, secret from env OURA_CLIENT_SECRET,
  tokens from ~/.config/jarvis/oura_tokens.json (mode 600).
- Refreshes ONLY when the access token is within 3 days of expiry or a request returns 401.
  Oura refresh tokens are single-use, so the new token file is written atomically (temp + rename, 600)
  immediately after the refresh response, under an exclusive file lock.
- Writes raw data to $JARVIS_DATA_DIR/oura.json (default ~/.local/share/jarvis, OUTSIDE the repo).
- Never prints tokens or secrets. Missing/forbidden endpoints are recorded as unavailable, never faked.
"""
import datetime as dt, fcntl, json, os, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

CFG = os.path.expanduser("~/.config/jarvis")
TOK = os.path.join(CFG, "oura_tokens.json")
LOCK = os.path.join(CFG, ".oura_refresh.lock")
OUT_DIR = os.environ.get("JARVIS_DATA_DIR", os.path.expanduser("~/.local/share/jarvis"))
API = "https://api.ouraring.com/v2/usercollection/"
UA = "JARVIS/1.0"
DAYS = 35

def log(*a): print("[oura]", *a, file=sys.stderr)

def load_tokens():
    with open(TOK) as f: return json.load(f)

def save_tokens(t):
    fd, tmp = tempfile.mkstemp(dir=CFG, prefix=".oura_tokens.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f: json.dump(t, f); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, TOK)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def expires_at(t): return float(t.get("obtained_at", 0)) + float(t.get("expires_in", 0))

def refresh(force=False):
    """Refresh under an exclusive lock; re-read the file inside the lock so a concurrent run never reuses a spent refresh token."""
    with open(LOCK, "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        t = load_tokens()
        if not force and expires_at(t) - time.time() > 3 * 86400:
            return t  # someone else already refreshed, or not needed
        secret = os.environ.get("OURA_CLIENT_SECRET")
        if not secret: raise SystemExit("OURA_CLIENT_SECRET not set; cannot refresh Oura token")
        cid = open(os.path.join(CFG, "oura_client_id")).read().strip()
        body = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                                       "client_id": cid, "client_secret": secret}).encode()
        req = urllib.request.Request("https://api.ouraring.com/oauth/token", data=body, method="POST",
                                     headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r: new = json.load(r)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Oura token refresh failed: HTTP {e.code} (reconnect Oura may be needed)")
        new["obtained_at"] = time.time()
        if "refresh_token" not in new: new["refresh_token"] = t["refresh_token"]
        save_tokens(new)  # immediately, before anything else
        log("access token refreshed")
        return new

state = {"t": None, "refreshed": False}

def token():
    if state["t"] is None:
        t = load_tokens()
        if expires_at(t) - time.time() < 3 * 86400: t = refresh(); state["refreshed"] = True
        state["t"] = t
    return state["t"]["access_token"]

def get(path, params):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(3):
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token(), "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return 200, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401 and path == "personal_info" and not state["refreshed"]:
                # Only the personal_info probe can trigger a 401 refresh: other endpoints answer 401 when
                # a scope/feature isn't granted, and refresh tokens are single-use, so don't waste them.
                state["t"] = refresh(force=True); state["refreshed"] = True; continue
            if e.code == 429 and attempt < 2: time.sleep(5 * (attempt + 1)); continue
            return e.code, None
        except urllib.error.URLError as e:
            if attempt < 2: time.sleep(3); continue
            return -1, None
    return -1, None

def collection(path, params):
    items, p = [], dict(params)
    while True:
        code, j = get(path, p)
        if code != 200: return code, items or None
        items += j.get("data", [])
        nt = j.get("next_token")
        if not nt: return 200, items
        p["next_token"] = nt

def main():
    today = dt.date.today()
    start, end = (today - dt.timedelta(days=DAYS)).isoformat(), (today + dt.timedelta(days=1)).isoformat()
    rng = {"start_date": start, "end_date": end}
    code, pi = get("personal_info", None)  # probe the token first (401 here => refresh once)
    out = {"fetched_at": time.time(), "range": [start, today.isoformat()], "endpoints": {}, "data": {}}
    eps = ["daily_readiness", "daily_sleep", "sleep", "daily_activity", "workout", "session",
           "daily_spo2", "daily_stress", "daily_resilience", "daily_cardiovascular_age", "vO2_max"]
    for ep in eps:
        code, items = collection(ep, rng)
        if ep == "daily_activity" and items:
            for it in items: it.pop("met", None); it.pop("class_5_min", None)
        out["endpoints"][ep] = {"status": code, "count": len(items or [])}
        if items: out["data"][ep] = items
    now = dt.datetime.now(dt.timezone.utc)
    code, items = collection("heartrate", {"start_datetime": (now - dt.timedelta(hours=48)).isoformat(timespec="seconds"),
                                           "end_datetime": now.isoformat(timespec="seconds")})
    out["endpoints"]["heartrate"] = {"status": code, "count": len(items or [])}
    if items: out["data"]["heartrate"] = items
    out["endpoints"]["personal_info"] = {"status": code, "count": 1 if pi else 0}
    if pi: out["data"]["personal_info"] = {k: pi.get(k) for k in ("age", "weight", "height", "biological_sex")}
    os.makedirs(OUT_DIR, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=OUT_DIR, prefix=".oura.")
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(out, f)
    os.replace(tmp, os.path.join(OUT_DIR, "oura.json"))
    for ep, s in out["endpoints"].items(): log(f"{ep}: HTTP {s['status']}, {s['count']} records")
    ok = any(s["status"] == 200 for s in out["endpoints"].values())
    if not ok: raise SystemExit("No Oura endpoint returned data")

if __name__ == "__main__": main()
