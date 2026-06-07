#!/usr/bin/env python3
"""aigfs_runner.py — POD-SIDE runner for the ai-models-gfs container (the live-GFS engine).

Unlike fcn_fleet.py (earth2studio), this drives jacob-radford/ai-models-gfs: it pulls LIVE NOAA GFS
analysis from S3 and rolls a model forward, writing GRIB. We then parse the GRIB, pull each city's
local-afternoon daily-MAX 2m temperature, convert K->F, and stream the same record shape the MOS eats.

env: FCN_TARGET=YYYY-MM-DD  FCN_INIT_DATE=YYYYMMDD  FCN_INIT_TIME=0000  FCN_MODELS=graphcast,fourcastnetv2
     FCN_LEAD=240  FCN_OUT=/root/r.jsonl  RUN_ID=...
Model names are ai-models-gfs plugin names: graphcast, panguweather, fourcastnetv2, aurora.
"""
import os, json, glob, subprocess, datetime as dt
import numpy as np

OUT     = os.environ.get("FCN_OUT", "/root/aigfs.jsonl")
TARGET  = os.environ.get("FCN_TARGET", "2026-06-08")
INIT_D  = os.environ.get("FCN_INIT_DATE", TARGET.replace("-", ""))   # default: target day 00z (analysis)
INIT_T  = os.environ.get("FCN_INIT_TIME", "0000")
LEAD    = os.environ.get("FCN_LEAD", "240")
MODELS  = os.environ.get("FCN_MODELS", "graphcast,fourcastnetv2").split(",")
RUN_ID  = os.environ.get("RUN_ID", "norun")

# init datetime (UTC) for local-day conversion
INIT_DT = dt.datetime.strptime(INIT_D + INIT_T[:2], "%Y%m%d%H")

CITIES = {
    "miami": (25.7959, -80.2870, -4), "nyc": (40.6398, -73.7789, -4),
    "lax": (33.9425, -118.4081, -7), "denver": (39.8561, -104.6737, -6),
    "atlanta": (33.6407, -84.4277, -4), "chicago": (41.9742, -87.9073, -5),
    "dallas": (32.8471, -96.8518, -5), "houston": (29.9902, -95.3368, -5),
}


def emit(rec):
    rec["run_id"] = RUN_ID
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"EMIT {rec['model']:14} {rec['status']:6} {rec.get('readings', rec.get('error',''))}", flush=True)


def daily_high_f(ds, t2name, clat, clon, tz):
    """local-afternoon daily-max F for one city from a cfgrib-opened forecast."""
    import xarray as xr  # noqa
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ilat = int(np.abs(lat - clat).argmin())
    ilon = int(np.abs(lon - (clon % 360)).argmin())
    t2 = ds[t2name]
    # step/valid_time → local datetime; keep target-day afternoon frames
    steps = ds["step"].values if "step" in ds else ds["valid_time"].values
    vals = []
    for i, s in enumerate(np.atleast_1d(steps)):
        try:
            if "valid_time" in ds.coords:
                vt = np.datetime64(ds["valid_time"].values.flat[i]).astype("datetime64[s]").astype(dt.datetime)
            else:
                vt = INIT_DT + dt.timedelta(seconds=int(np.timedelta64(s, "s").astype(int)))
        except Exception:
            continue
        loc = vt + dt.timedelta(hours=tz)
        if loc.strftime("%Y-%m-%d") == TARGET and 10 <= loc.hour <= 23:
            try:
                v = float(t2.isel({t2.dims[0]: i}).values[ilat, ilon]) if t2.ndim == 3 else float(t2.values[ilat, ilon])
                vals.append(v)
            except Exception:
                pass
    if not vals:
        return None
    k = max(vals)
    return round((k - 273.15) * 9 / 5 + 32, 1) if k > 200 else round(k * 9 / 5 + 32, 1)


for name in MODELS:
    name = name.strip()
    grib = f"/root/aigfs_{name}.grib"
    try:
        print(f"\n=== {name} : ai-models-gfs --input gfs --date {INIT_D} --time {INIT_T} ===", flush=True)
        cmd = ["ai-models-gfs", "--input", "gfs", "--date", INIT_D, "--time", INIT_T,
               "--lead-time", LEAD, "--path", grib, name]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not os.path.exists(grib):
            tail = (r.stderr or r.stdout or "")[-300:]
            emit({"model": name, "status": "FAIL", "target": TARGET,
                  "error": f"ai-models-gfs rc={r.returncode}: {tail}"[:200]})
            continue
        import xarray as xr
        # t2m param is '2t' in GFS-init GRIB; open the surface field
        ds = None
        for key in ("2t", "t2m"):
            try:
                ds = xr.open_dataset(grib, engine="cfgrib",
                                     backend_kwargs={"filter_by_keys": {"shortName": "2t"}})
                t2name = "t2m" if "t2m" in ds else ("2t" if "2t" in ds else list(ds.data_vars)[0])
                break
            except Exception:
                ds = None
        if ds is None:
            emit({"model": name, "status": "FAIL", "target": TARGET, "error": "no t2m in GRIB"})
            continue
        reads = {c: daily_high_f(ds, t2name, *v) for c, v in CITIES.items()}
        emit({"model": f"{name}-GFS", "status": "GREEN", "init": INIT_DT.isoformat(),
              "target": TARGET, "unit": "F", "readings": reads})
    except Exception as e:
        emit({"model": name, "status": "FAIL", "target": TARGET, "error": f"{type(e).__name__}: {e}"[:200]})

print(f"\nAIGFS DONE · run {RUN_ID} · {OUT}", flush=True)
