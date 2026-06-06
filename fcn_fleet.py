#!/usr/bin/env python3
"""FCN FLEET runner (POD-SIDE) — attempt every pytorch/ONNX-family NVIDIA model in one pod.

For EACH model class in earth2studio.models.px:
  load weights  ->  single live GFS init  ->  roll forward to TARGET day
  ->  extract local-afternoon daily-high per city  ->  STREAM the result.

Streaming to a jsonl after every model means NOTHING is lost if one model errors
or the watchdog cuts the pod mid-fleet. Every failure records its exact error —
that error log is the forensics that fixes the stragglers next pass.

Dep family in THIS pod: pure-PyTorch (FCN/FCN3/SFNO via makani) + ONNX (Pangu/FuXi) + conv (DLWP).
Other families run their own pod: JAX (GraphCast/GenCast), anemoi (AIFS), aurora pkg (Aurora).
Recipe = validated fcn_one (cu124 torch, GFS IC, 6h steps, K->F, local-afternoon max).
"""
import os, json, gc, datetime as dt
import numpy as np

OUT    = os.environ.get("FCN_OUT", "/root/fcn_fleet.jsonl")
INIT   = dt.datetime.fromisoformat(os.environ.get("FCN_INIT", "2026-06-04T00:00:00"))
TARGET = os.environ.get("FCN_TARGET", "2026-06-05")
NSTEPS = int(os.environ.get("FCN_NSTEPS", "8"))

# the pytorch/ONNX family to attempt, in order of confidence (FCN proven first)
FLEET = os.environ.get("FCN_MODELS", "FCN,Pangu6,FuXi,Aurora").split(",")  # env-driven per dep-family pod

CITIES = {
    "miami": (25.7959, -80.2870, -4), "nyc": (40.6398, -73.7789, -4),
    "lax": (33.9425, -118.4081, -7), "denver": (39.8561, -104.6737, -6),
    "atlanta": (33.6407, -84.4277, -4), "chicago": (41.9742, -87.9073, -5),
    "dallas": (32.8471, -96.8518, -5), "houston": (29.9902, -95.3368, -5),
}

import torch
assert torch.cuda.is_available(), "NO CUDA — abort, do not burn budget on CPU"
print("CUDA:", torch.cuda.get_device_name(0), flush=True)
from earth2studio.io import ZarrBackend
import earth2studio.run as run
import earth2studio.models.px as px
import xarray as xr

# Data source is model-family aware. pytorch/ONNX models (FCN/Pangu/FuXi/Aurora)
# init fine from GFS. ECMWF AIFS/AIFSENS need their native IFS analysis: GFS does
# not supply AIFS's ERA5 channel set (cp06/tp06/insolation/sdor/slor/skt + the
# 50–1000 hPa q/t/u/v/w/z stack), which yields a coherent-but-cold-broken field
# (latitude-correct, ~73 K too cold ≈ jet-stream-level temps). Env-driven so each
# dependency-family pod selects the right IC without forking this runner.
_DATA_SRC = os.environ.get("FCN_DATA", "GFS").upper()
if _DATA_SRC == "IFS":
    from earth2studio.data import IFS
    DATA = IFS()
elif _DATA_SRC == "ARCO":
    from earth2studio.data import ARCO
    DATA = ARCO()
else:
    from earth2studio.data import GFS
    DATA = GFS()
print(f"DATA SOURCE: {_DATA_SRC}", flush=True)


def emit(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"EMIT {rec['model']:9} {rec['status']:6} "
          f"{rec.get('readings', rec.get('error', ''))}", flush=True)


def daily_high_f(ds, clat, clon, tz):
    """Local-afternoon daily-max °F for one city from a forecast zarr."""
    lat = ds["lat"].values
    lon = ds["lon"].values
    leads = ds["lead_time"].values
    ilat = int(np.abs(lat - clat).argmin())
    ilon = int(np.abs(lon - (clon % 360)).argmin())
    vals = []
    for li, ld in enumerate(leads):
        v = (np.datetime64(INIT) + ld).astype("datetime64[s]").astype(dt.datetime) + dt.timedelta(hours=tz)
        if v.strftime("%Y-%m-%d") == TARGET and 10 <= v.hour <= 23:
            vals.append(float(ds["t2m"].isel(time=0, lead_time=li).values[ilat, ilon]))
    return round((max(vals) - 273.15) * 9 / 5 + 32, 1) if vals else None


green = 0
for name in FLEET:
    Model = getattr(px, name, None)
    if Model is None:
        emit({"model": name, "status": "NOCLASS"})
        continue
    model = None
    try:
        print(f"\n=== {name} : loading ===", flush=True)
        model = Model.load_model(Model.load_default_package())
        zfn = f"/root/fleet_{name}.zarr"
        run.deterministic(
            time=[INIT], nsteps=NSTEPS, prognostic=model, data=DATA,
            io=ZarrBackend(file_name=zfn, backend_kwargs={"overwrite": True}),
            output_coords={"variable": np.array(["t2m"])},
        )
        ds = xr.open_zarr(zfn)
        _t2 = ds["t2m"].isel(time=0)
        print(f"  [{name}] t2m global K min/mean/max = "
              f"{float(_t2.min()):.1f}/{float(_t2.mean()):.1f}/{float(_t2.max()):.1f} "
              f"(sane surface ~ 230/288/320)", flush=True)
        reads = {c: daily_high_f(ds, *v) for c, v in CITIES.items()}
        emit({"model": name, "status": "GREEN", "init": INIT.isoformat(),
              "target": TARGET, "unit": "F", "readings": reads})
        green += 1
    except Exception as e:
        import traceback
        print(f"--- {name} FULL TRACEBACK (chained cause) ---", flush=True)
        traceback.print_exc()
        cause = e
        for _ in range(8):
            nxt = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
            if nxt is None:
                break
            cause = nxt
        emit({"model": name, "status": "FAIL",
              "error": f"{type(e).__name__}: {e}"[:200],
              "root_cause": f"{type(cause).__name__}: {cause}"[:200]})
    finally:
        # Gemini-hardened: free GPU even on failure so one model's OOM can't domino the rest.
        try:
            del model
        except Exception:
            pass
        torch.cuda.empty_cache()
        gc.collect()

print(f"\nFLEET DONE · {green}/{len(FLEET)} green · results in {OUT}", flush=True)
