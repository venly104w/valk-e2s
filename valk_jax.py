#!/usr/bin/env python3
"""valk_jax.py — isolated JAX runner for GenCast (probabilistic, 50 members) + GraphCast (deterministic).
Gemini's equal-partner call: the KDE needs GenCast's distribution, not just point forecasts.

Runs INSIDE the persistent jax_env (numpy<2, jax[cuda12], jaxlib==0.4.28, graphcast) on /workspace,
on LIVE GFS analysis via the ai-models-gfs ecosystem (free, no-auth). Extracts the SAME 8 cities as
fcn_fleet.py and appends each member as a KDE input to the shared results sink.

Invoke:  source /workspace/jax_env/bin/activate && python /workspace/valk_jax.py
Env: VALK_INIT (YYYYMMDD), VALK_TIME (0000), VALK_TARGET (YYYY-MM-DD), VALK_LEAD (48),
     VALK_SINK (/workspace/valk_results_temp.json)
"""
import os, json, glob, subprocess, datetime as dt
import numpy as np

CITIES = {  # same coords as fcn_fleet.py (lat, lon, tz-hours)
    "miami": (25.7959, -80.2870, -4), "nyc": (40.6398, -73.7789, -4),
    "lax": (33.9425, -118.4081, -7), "denver": (39.8561, -104.6737, -6),
    "atlanta": (33.6407, -84.4277, -4), "chicago": (41.9742, -87.9073, -5),
    "dallas": (32.8471, -96.8518, -5), "houston": (29.9902, -95.3368, -5),
}
INIT_D = os.environ.get("VALK_INIT", dt.date.today().strftime("%Y%m%d"))
TIME = os.environ.get("VALK_TIME", "0000")
TARGET = os.environ.get("VALK_TARGET", "")
LEAD = os.environ.get("VALK_LEAD", "48")
SINK = os.environ.get("VALK_SINK", "/workspace/valk_results_temp.json")
INIT = dt.datetime.strptime(INIT_D + TIME, "%Y%m%d%H%M")


def city_high_f(ds, clat, clon, tz, target):
    """local-afternoon daily-max °F for one city across lead steps of one ensemble member."""
    import xarray as xr  # noqa
    la = ds["latitude"].values
    lo = ds["longitude"].values
    var = ds["t2m"] if "t2m" in ds else ds["2t"] if "2t" in ds else ds[list(ds.data_vars)[0]]
    ila = int(np.abs(la - clat).argmin())
    ilo = int(np.abs((lo % 360) - (clon % 360)).argmin())
    vals = []
    steps = ds["step"].values if "step" in ds.dims else [np.timedelta64(int(LEAD), "h")]
    for si, st in enumerate(steps):
        valid = INIT + dt.timedelta(hours=int(np.asarray(st).astype("timedelta64[h]").astype(int))) + dt.timedelta(hours=tz)
        if valid.strftime("%Y-%m-%d") == target and 10 <= valid.hour <= 23:
            v = var.isel(step=si) if "step" in var.dims else var
            arr = np.asarray(v.values)
            vals.append(float(arr[ila, ilo]) if arr.ndim == 2 else float(arr.ravel()[ila * len(lo) + ilo]))
    return round((max(vals) - 273.15) * 9 / 5 + 32, 1) if vals else None


def emit(rec):
    recs = []
    if os.path.exists(SINK):
        try:
            recs = json.load(open(SINK))
        except Exception:
            recs = []
    recs.append(rec)
    tmp = SINK + ".tmp"
    json.dump(recs, open(tmp, "w"))
    os.replace(tmp, SINK)  # atomic (Gemini: no partial-write data suicide)
    print("EMIT", rec["model"], rec["status"], rec.get("readings", rec.get("error", "")), flush=True)


def run_model(name, cli_model):
    """Run an ai-models-gfs model on live GFS; GenCast yields N members, GraphCast 1."""
    import xarray as xr
    out = f"/workspace/{name}_{{step}}.grib"
    cmd = ["ai-models-gfs", "--input", "gfs", "--date", INIT_D, "--time", TIME,
           "--lead-time", LEAD, "--path", out, cli_model]
    try:
        subprocess.run(cmd, check=True, timeout=2400)
        files = sorted(glob.glob(f"/workspace/{name}_*.grib"))
        if not files:
            emit({"model": name, "status": "FAIL", "error": "no grib output"})
            return
        # GenCast writes per-member ('number' dim); GraphCast single field.
        for f in files:
            ds = xr.open_dataset(f, engine="cfgrib", backend_kwargs={"filter_by_keys": {"shortName": "2t"}})
            members = ds["number"].values if "number" in ds.dims else [0]
            for m in members:
                dsm = ds.sel(number=m) if "number" in ds.dims else ds
                reads = {c: city_high_f(dsm, *v, TARGET) for c, v in CITIES.items()}
                tag = f"{name}" if len(members) == 1 else f"{name}#{int(m)}"
                emit({"model": tag, "status": "GREEN", "init": INIT.isoformat(),
                      "target": TARGET, "unit": "F", "readings": reads})
    except Exception as e:
        emit({"model": name, "status": "FAIL", "error": f"{type(e).__name__}: {e}"[:200]})


if __name__ == "__main__":
    assert TARGET, "VALK_TARGET required (no manipulation-bug: label only real emits)"
    print(f">>> valk_jax · init {INIT} · target {TARGET} · sink {SINK}", flush=True)
    run_model("GenCast", "gencast")     # ~50 probabilistic members → the KDE's backbone
    run_model("GraphCast", "graphcast")  # deterministic SOTA → 1 member
    print(">>> valk_jax done", flush=True)
