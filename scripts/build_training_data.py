#!/usr/bin/env python3
"""Turn raw Oura data (outside the repo) into the compact JSON the Training mini app renders, and
inject it into src/training/index.html. Writes the PLAINTEXT page to the path given as argv[1]
(build.sh passes a private temp dir, never dist/). Missing data stays null -> the page shows "No data".
"""
import json, os, sys, collections
RAW = os.path.join(os.environ.get("JARVIS_DATA_DIR", os.path.expanduser("~/.local/share/jarvis")), "oura.json")
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "..", "src", "training", "index.html")).read()
out_path = sys.argv[1]

def compact(raw):
    d, ep = raw.get("data", {}), raw.get("endpoints", {})
    pick = lambda o, ks: {k: o.get(k) for k in ks}
    res = {"updated": raw.get("fetched_at"), "endpoints": {k: v.get("status") for k, v in ep.items()},
           "counts": {k: v.get("count") for k, v in ep.items()}}
    res["readiness"] = [pick(x, ["day", "score", "contributors", "temperature_deviation"]) for x in d.get("daily_readiness", [])]
    res["sleepScore"] = [pick(x, ["day", "score", "contributors"]) for x in d.get("daily_sleep", [])]
    res["activity"] = [pick(x, ["day", "score", "steps", "active_calories", "total_calories", "target_calories",
                                "high_activity_time", "medium_activity_time", "low_activity_time", "sedentary_time",
                                "equivalent_walking_distance", "target_meters", "contributors"]) for x in d.get("daily_activity", [])]
    # main sleep per day = longest long_sleep (fallback: longest period)
    by = collections.defaultdict(list)
    for s in d.get("sleep", []): by[s["day"]].append(s)
    sl = []
    for day in sorted(by):
        s = max(by[day], key=lambda x: (x.get("type") == "long_sleep", x.get("total_sleep_duration") or 0))
        sl.append(pick(s, ["day", "bedtime_start", "bedtime_end", "total_sleep_duration", "time_in_bed", "deep_sleep_duration",
                           "rem_sleep_duration", "light_sleep_duration", "awake_time", "efficiency", "latency",
                           "average_heart_rate", "lowest_heart_rate", "average_hrv", "average_breath"]))
    if sl:
        last = max(by[sl[-1]["day"]], key=lambda x: (x.get("type") == "long_sleep", x.get("total_sleep_duration") or 0))
        sl[-1]["phases"] = last.get("sleep_phase_5_min")
    res["sleep"] = sl
    res["spo2"] = [{"day": x["day"], "avg": (x.get("spo2_percentage") or {}).get("average"),
                    "bdi": x.get("breathing_disturbance_index")} for x in d.get("daily_spo2", [])]
    res["stress"] = [pick(x, ["day", "stress_high", "recovery_high", "day_summary"]) for x in d.get("daily_stress", [])]
    res["workouts"] = sorted([pick(x, ["activity", "start_datetime", "end_datetime", "calories", "distance", "intensity", "source", "label"])
                              for x in d.get("workout", [])], key=lambda w: w["start_datetime"], reverse=True)
    # heart rate: 15-min averages over the last 48h
    hr = collections.defaultdict(list)
    for h in d.get("heartrate", []):
        m = int(h["timestamp"][14:16])
        t = h["timestamp"][:14] + "%02d" % (m // 15 * 15)
        hr[t].append(h["bpm"])
    res["hr"] = [[t + ":00Z", round(sum(v) / len(v))] for t, v in sorted(hr.items())]
    return res

data = None
if os.path.exists(RAW):
    with open(RAW) as f: data = compact(json.load(f))
js = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
assert "/*__OURA_DATA__*/null" in tpl
html = tpl.replace("/*__OURA_DATA__*/null", js)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: f.write(html)
print("training data:", "none (not connected)" if data is None else f"{len(data['readiness'])} readiness days, {len(data['workouts'])} workouts", file=sys.stderr)
