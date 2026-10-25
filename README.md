# Wind forecast reliability (UK day-ahead, Jan 2026)
Compares Elexon WINDFOR forecasts with FUELHH wind actuals and quantifies forecast error for day-ahead buying.

**Live app:** <ADD VERCEL URL>

## Structure
- `backend/app.py` – Flask API: fetch + cache Elexon data, decision-time forecast selection, metrics (`/api/compare`, `/api/horizon`)
- `frontend/` – React (Vite + Recharts) dashboard
- `api/index.py`, `vercel.json` – Vercel entry/config
- `Dockerfile` – multi-stage (builds React, serves via gunicorn)

## Run
`docker build -t wind . && docker run -p 8000:8000 wind` then open http://localhost:8000
Dev: `pip install -r backend/requirements.txt && python backend/app.py`; `cd frontend && npm i && npm run dev`

## Method
- "Forecast available at decision time": for target half-hour T on day D, the latest forecast with publishTime <= (D-1 at cutoff hour, default 09:00 UK; UTC = UK in January). Cutoff is adjustable.
- Error = forecast - actual (MW). Metrics: MAE, RMSE, bias, wMAPE, 5th/95th percentile band, error by hour of day and by forecast horizon (0-48h).
- Scope: national wind only, Elexon only, target times 1-31 Jan 2026.

## AI usage
Built with assistance from Claude (Anthropic) for code generation; reviewed by the author.
