"""Wind forecast vs actuals API (Elexon FUELHH + WINDFOR), Jan 2026."""
import os, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import pickle
import numpy as np, pandas as pd, requests
from flask import Flask, jsonify, request, send_from_directory

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
START, END = dt.date(2026, 1, 1), dt.date(2026, 1, 31)
MAX_HORIZON_H = 48
app = Flask(__name__, static_folder=os.environ.get("STATIC_DIR", "static"), static_url_path="")
_cache = {}

def _fetch(ds, params):
    r = requests.get(f"{BASE}/{ds}/stream", params={**params, "format": "json"}, timeout=90)
    r.raise_for_status()
    return r.json()

def _chunks(start, end, days):
    d = start
    while d <= end:
        yield d, min(d + dt.timedelta(days=days - 1), end)
        d += dt.timedelta(days=days)

def load():
    """Fetch once per instance, in parallel chunks, and cache."""
    if "data" in _cache:
        return _cache["data"]
    snap = os.path.join(os.path.dirname(__file__), "data.pkl")
    if os.path.exists(snap):
        with open(snap, "rb") as fh:
            _cache["data"] = pickle.load(fh)
        return _cache["data"]
    a_jobs = [("FUELHH", {"settlementDateFrom": s.isoformat(), "settlementDateTo": e.isoformat(), "fuelType": "WIND"})
              for s, e in _chunks(START, END, 7)]
    # forecasts for Jan targets are published up to 48h earlier -> start window 3 days early
    f_jobs = [("WINDFOR", {"publishDateTimeFrom": f"{s}T00:00:00Z", "publishDateTimeTo": f"{e}T23:59:59Z"})
              for s, e in _chunks(START - dt.timedelta(days=3), END, 1)]
    with ThreadPoolExecutor(8) as ex:
        a_rows = sum(ex.map(lambda j: _fetch(*j), a_jobs), [])
        f_rows = sum(ex.map(lambda j: _fetch(*j), f_jobs), [])
    a = pd.DataFrame(a_rows)
    a = a[a.fuelType == "WIND"].assign(start=lambda d: pd.to_datetime(d.startTime, utc=True))
    a = a.drop_duplicates("start").set_index("start")["generation"].rename("actual").astype(float)
    f = pd.DataFrame(f_rows).assign(start=lambda d: pd.to_datetime(d.startTime, utc=True),
                                    pub=lambda d: pd.to_datetime(d.publishTime, utc=True))
    f["forecast"] = f.generation.astype(float)
    f["horizon_h"] = (f.start - f.pub).dt.total_seconds() / 3600
    f = f[(f.horizon_h >= 0) & (f.horizon_h <= MAX_HORIZON_H) & (f.start.dt.date >= START) & (f.start.dt.date <= END)]
    _cache["data"] = (a, f[["start", "pub", "forecast", "horizon_h"]])
    return _cache["data"]

def decision_forecast(f, cutoff_hour):
    """Per target half-hour: latest forecast published before the day-ahead decision time
    = (target day - 1) at cutoff_hour (UTC == UK time in January)."""
    cut = f.start.dt.normalize() - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    g = f[f.pub <= cut].sort_values("pub").groupby("start").tail(1)
    return g.set_index("start")[["forecast", "pub", "horizon_h"]]

def metrics(err, actual):
    e = err.dropna()
    if e.empty:
        return {}
    return {"n": int(len(e)), "mae": e.abs().mean(), "rmse": float(np.sqrt((e ** 2).mean())),
            "bias": e.mean(), "p5": e.quantile(.05), "p95": e.quantile(.95),
            "wmape_pct": 100 * e.abs().sum() / actual.loc[e.index].sum()}

def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if np.isnan(o) else round(float(o), 2)
    if isinstance(o, np.integer): return int(o)
    return o

@app.get("/api/compare")
def compare():
    """Decision-time forecast vs actual. Params: start, end (YYYY-MM-DD), cutoff_hour (default 9)."""
    a, f = load()
    ch = int(request.args.get("cutoff_hour", 9))
    s = pd.Timestamp(request.args.get("start", START.isoformat()), tz="UTC")
    e = pd.Timestamp(request.args.get("end", END.isoformat()), tz="UTC") + pd.Timedelta(days=1)
    d = decision_forecast(f, ch).join(a, how="inner")
    d = d[(d.index >= s) & (d.index < e)].sort_index().copy()
    d["error"] = d.forecast - d.actual  # + = over-forecast (risk: under-buying)
    by_hour = d.groupby(d.index.hour).error.agg(mae=lambda x: x.abs().mean(), bias="mean").reset_index()
    by_hour.columns = ["hour", "mae", "bias"]
    pts = [{"t": t.isoformat(), "actual": r.actual, "forecast": r.forecast, "published": r.pub.isoformat(),
            "error": r.error} for t, r in d.iterrows()]
    return jsonify(_clean({"cutoff_hour": ch, "metrics": metrics(d.error, d.actual),
                           "by_hour": by_hour.to_dict("records"), "points": pts}))

@app.get("/api/horizon")
def horizon():
    """Error vs forecast horizon (all published forecasts, 4h buckets)."""
    a, f = load()
    d = f.join(a, on="start", how="inner").dropna().copy()
    d["error"] = d.forecast - d.actual
    d["bucket"] = (d.horizon_h // 4 * 4).astype(int)
    out = d.groupby("bucket").error.agg(mae=lambda x: x.abs().mean(), bias="mean", n="count").reset_index()
    return jsonify(_clean(out.to_dict("records")))

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
