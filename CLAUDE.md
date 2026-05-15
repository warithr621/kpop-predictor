# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Backend (FastAPI)**
```bash
pip install -r requirements.txt
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend (Next.js)**
```bash
cd frontend
npm install
npm run dev    # runs on port 3000
```

**Data collection** (requires MusicBrainz credentials in `.env`):
```bash
python data_collection.py
```

**Backtest / model evaluation**:
```bash
python analysis.py
```

## Architecture

This is a full-stack K-pop release prediction app with three layers:

### Data layer
- `albums/` — one CSV per artist/group with columns `title, type, release_date` (and optional `secondary_types, track_count, label`), scraped from MusicBrainz via `data_collection.py`. Compilations, live albums, remixes, and demos are filtered out at load time.
- `artist_ids.json` — cached MusicBrainz artist IDs to avoid re-scraping
- `info.py` — single source of truth for group metadata: `KPOP_GROUPS` (organized by generation), `SOLOISTS` (soloist → parent group), `GENERATION_MAPPINGS`, `GROUP_COMPANIES`
- `requirements.txt` — Python backend dependencies

### Backend (`backend/`)
- `model.py` — all ML logic: feature engineering, LightGBM quantile regression (p10/p50/p90), and prediction. The model trains on log-transformed inter-release intervals and uses `stable_hash_int` (SHA-256-based) for deterministic categorical encoding instead of sklearn `LabelEncoder` (avoids encode/decode mismatch across runs). Cache key prefix is `model_v4_quantiles_`.
- `app.py` — FastAPI app exposing `/api/groups`, `/api/releases`, `/api/predict`, `/api/status`. Trained models are pickled to `backend/cache/` keyed by a data signature + cutoff date. The cache is invalidated automatically when CSV files change.
- `backend/__init__.py` — empty, makes `backend` a package so `from backend.model import ...` works when running from the repo root.
- `analysis.py` (root) — offline backtest script: trains on pre-2024 data, evaluates on 2024+ releases, prints MAE/MAPE/coverage/within-N-weeks stats broken down by release type and group.

### Frontend (`frontend/`)
- Next.js (Pages Router) + Tailwind CSS
- `src/lib/api.js` — all fetch calls to the backend; `NEXT_PUBLIC_API_BASE` env var controls the backend URL (defaults to `http://localhost:8000`)
- Page flow: `/` (landing) → `/gen` (pick generation) → `/groups` (pick group) → `/group` (show releases + prediction)

### Key design details
- **Soloists inherit parent group features**: when predicting for a group, `get_solo_releases_for_group` pulls in all member solo releases as additional features, letting the model detect activity signals (e.g. members releasing solos before a group comeback).
- **Cutoff date**: training always uses data up to today (`get_current_cutoff_dates()`), not the hardcoded `DEFAULT_CUTOFF = 2024-12-31`. Cache keys include the cutoff date to prevent stale predictions.
- **Group name sanitization**: CSV filenames use `sanitize()` (spaces → `_`, special chars → `_`). `info.py` keys use the original display names. Both `model.py` and `app.py` call `sanitize()` consistently when looking up CSVs.
- **`versions/`**: optional directory of historical prediction CSVs (`predictions.csv` with columns `group, error_days, error_pct`) used by `load_group_error_stats` to report per-group MAE in the API response.

## Environment variables
- `.env` (root) — `USERNAME`, `PASSWORD`, `EMAIL` for MusicBrainz auth (data collection only)
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE` for backend URL
- `FRONTEND_ORIGIN` (backend env) — CORS origin restriction; defaults to `*` in dev
