#!/usr/bin/env python3
"""valk_mos_kde.py — the FINANCIAL-INSTRUMENT CORE (Gemini ultraplan).
MOS bias-correct every model's raw forecast → pool into a KDE → integrate over each 2°F
bracket → FIRE only at ≥90%, else ABSTAIN. Multi-city. numpy-only (no scipy dep).

Usage: python3 valk_mos_kde.py [TARGET_DATE] [city]   # default: tomorrow, miami
       python3 valk_mos_kde.py --all TARGET_DATE        # every city
The MOS bias for model m = median(past forecast − actual) over a rolling window, NO leakage
(only target dates strictly before the date being decided). Sparse history → ABSTAIN (zero-trust).
"""
import json, os, sys, datetime as dt
import numpy as np

SKILL = os.path.expanduser("~/.valkyrie/state/skill")
READINGS = os.path.join(SKILL, "all_readings.jsonl")
TRUTH = os.path.join(SKILL, "valk_truth_kmia.json")  # KMIA actuals; per-city truth files later
BRACKET_W = 2.0
CONF = 0.90
BIAS_WINDOW = 30
MIN_BIAS_SAMPLES = 5
MIN_MEMBERS = 3
CITIES = ["miami", "nyc", "lax", "denver", "atlanta", "chicago", "dallas", "houston"]


def load_truth():
    try:
        return {k: float(v) for k, v in json.load(open(TRUTH))["daily"].items()}
    except Exception:
        return {}


def load_forecasts():
    recs = []
    for l in open(READINGS) if os.path.exists(READINGS) else []:
        l = l.strip()
        if not l:
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("status") == "GREEN" and r.get("readings") and r.get("target"):
            recs.append(r)
    return recs


def rolling_bias(model, city, asof, fc_by_model, truth):
    """median(forecast − actual) over BIAS_WINDOW days strictly before `asof` (no leakage)."""
    errs = []
    asof_d = dt.date.fromisoformat(asof)
    for r in fc_by_model.get(model, []):
        tgt = r.get("target")
        val = (r.get("readings") or {}).get(city)
        if val is None or not tgt or tgt >= asof:
            continue
        a = truth.get(tgt)
        if a is None:
            continue
        if (asof_d - dt.date.fromisoformat(tgt)).days > BIAS_WINDOW:
            continue
        errs.append(float(val) - a)
    return (float(np.median(errs)), len(errs)) if len(errs) >= MIN_BIAS_SAMPLES else (0.0, len(errs))


def kde_pdf(points):
    pts = np.asarray(points, float)
    s = pts.std(ddof=1) if len(pts) > 1 else 1.0
    bw = max(0.5, 1.06 * s * len(pts) ** (-1 / 5))           # Silverman, floored at 0.5°F

    def pdf(x):
        x = np.atleast_1d(np.asarray(x, float))[:, None]
        return np.exp(-0.5 * ((x - pts[None, :]) / bw) ** 2).sum(1) / (len(pts) * bw * np.sqrt(2 * np.pi))
    return pdf, bw


def bracket_prob(pdf, lo, hi, n=240):
    xs = np.linspace(lo, hi, n)
    return float(np.trapz(pdf(xs), xs))


def decide(city, target, recs, truth):
    fc_by_model = {}
    for r in recs:
        fc_by_model.setdefault(r["model"], []).append(r)
    members, detail = [], []
    for r in recs:
        if r.get("target") != target:
            continue
        val = (r.get("readings") or {}).get(city)
        if val is None:
            continue
        bias, nb = rolling_bias(r["model"], city, target, fc_by_model, truth)
        members.append(float(val) - bias)
        detail.append({"model": r["model"], "raw": float(val), "bias": round(bias, 2), "n_bias": nb})
    if len(members) < MIN_MEMBERS:
        return {"city": city, "target": target, "decision": "ABSTAIN",
                "reason": f"only {len(members)} members (<{MIN_MEMBERS})", "members": len(members)}
    pdf, bw = kde_pdf(members)
    cen = float(np.median(members))
    best = max(((lo, bracket_prob(pdf, lo, lo + BRACKET_W))
                for lo in np.arange(np.floor(cen) - 6, np.ceil(cen) + 6, BRACKET_W)),
               key=lambda t: t[1])
    lo, p = best
    return {"city": city, "target": target, "members": len(members), "bw_F": round(bw, 2),
            "corrected_mean": round(float(np.mean(members)), 1),
            "bracket_F": f"{lo:.0f}-{lo + BRACKET_W:.0f}", "P_in_bracket": round(p, 3),
            "decision": "FIRE" if p >= CONF else "ABSTAIN",
            "models": detail}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--all"]
    all_cities = "--all" in sys.argv
    truth, recs = load_truth(), load_forecasts()
    target = args[0] if args else (dt.date.today() + dt.timedelta(days=1)).isoformat()
    cities = CITIES if all_cities else [args[1] if len(args) > 1 else "miami"]
    print(f"=== VALK MOS+KDE · target {target} · {len(recs)} green readings · truth {len(truth)} days ===")
    for c in cities:
        d = decide(c, target, recs, truth)
        flag = "🔥" if d["decision"] == "FIRE" else "··"
        extra = f"{d.get('bracket_F','')} P={d.get('P_in_bracket','')} (n={d.get('members',0)}, bw={d.get('bw_F','')})" \
            if "bracket_F" in d else d.get("reason", "")
        print(f"  {flag} {c:8} {d['decision']:8} {extra}")
