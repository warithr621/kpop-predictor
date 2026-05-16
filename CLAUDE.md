# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Backend (FastAPI)**
```bash
source ~/venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload   # run from repo root
```

**Frontend (Next.js)**
```bash
cd frontend
npm install
npm run dev    # runs on port 3000
```

**Data collection** (requires MusicBrainz credentials in `.env`):
```bash
source ~/venv/bin/activate && python data_collection.py
```

**Backtest / model evaluation**:
```bash
source ~/venv/bin/activate && python analysis.py
```

> Always activate `~/venv` before running Python — the system Python is externally managed.

## Architecture

Full-stack K-pop release prediction app: a Python/FastAPI ML backend + Next.js frontend.

### Data layer
- `albums/` — one CSV per artist/group (`title, type, release_date`, optional `secondary_types, track_count, label`), scraped from MusicBrainz via `data_collection.py`. Compilations, live albums, remixes, and demos are filtered at load time.
- `artist_ids.json` — cached MusicBrainz artist IDs to avoid re-scraping.
- `info.py` — single source of truth for all static metadata:
  - `KPOP_GROUPS` — groups by generation (3rd/4th/5th)
  - `SOLOISTS` — soloist → parent group mapping
  - `GENERATION_MAPPINGS`, `GROUP_COMPANIES`
  - `MILITARY_SERVICE` — per-member enlistment/discharge dates (used as a live feature)
  - `AWARD_SHOWS` — major K-pop award ceremony dates (MAMA, MMA, GDA, etc.), used to compute `days_to_awards` and `award_run_up` features

### Backend (`backend/`)
- `model.py` — all ML logic: feature engineering, LightGBM quantile regression (**p25/p50/p75**), prediction, and caching utilities.
  - Trains on log-transformed inter-release intervals (`target_days_log = log1p(days)`)
  - Uses `stable_hash_int` (SHA-256-based) for deterministic categorical encoding — never use sklearn `LabelEncoder` here
  - `extract_features_from_group` / `predict_next_release_lightgbm_interval` must stay in sync: both must compute the same feature set in the same way
  - Overdue groups (p50 raw date < today) are advanced forward by a shared cycle count anchored on p50 to prevent quantile collapse
  - Final date ordering is enforced by sorting all three (date, days) pairs together — do not revert to piecemeal min/max
  - Cache key prefix: `model_v10_quantiles_`
- `app.py` — FastAPI app: `/api/groups`, `/api/releases`, `/api/predict`, `/api/status`. Trained models are pickled to `backend/cache/` keyed by a data signature + cutoff date; cache auto-invalidates when CSVs change. **Bump the cache key version** (`model_vN_quantiles_`) whenever feature columns or quantiles change.
- `analysis.py` (root) — offline backtest (leave-last-out): withholds each group's most recent release and reports MAE/coverage/within-N-weeks. Run this to sanity-check any model change.

### Frontend (`frontend/`)
- Next.js (Pages Router) + Tailwind CSS
- `src/lib/api.js` — all fetch calls; `NEXT_PUBLIC_API_BASE` controls the backend URL (defaults to `http://localhost:8000`)
- `src/pages/index.jsx` — group picker, split into 4th/5th gen columns with typing-animation header
- `src/pages/group.jsx` — release timeline + `PredictionCard`. The range bar shows p25 (Optimistic) / p50 (Most Likely) / p75 (Late estimate); always use `fmtShort` with `year: 'numeric'` to avoid cross-year date ambiguity.
- `src/components/Timeline.jsx`, `Typing.jsx` — timeline renderer and animated header
- Dark techno theme in `src/styles/globals.css` via CSS custom properties: `--accent-4th: #f0287a` (pink), `--accent-5th: #22d3ee` (cyan). Generation-aware accent colors apply to cards, badges, predict button glow, and range bar.

### Key design details
- **Soloists inherit parent group features**: `get_solo_releases_for_group` pulls member solo releases as activity signals (e.g. solo drops before a group comeback). Soloist predictions also benefit from parent group history.
- **Cutoff date**: training always uses data up to today (`get_current_cutoff_dates()`). The hardcoded `DEFAULT_CUTOFF = 2024-12-31` is only a fallback — never use it for production predictions.
- **Group name sanitization**: CSV filenames use `sanitize()` (spaces/special chars → `_`). `info.py` keys use original display names. Both `model.py` and `app.py` call `sanitize()` consistently when looking up CSVs.
- **Feature parity**: the 32 feature columns in `train_lightgbm_quantile_models` must exactly match those built in `predict_next_release_lightgbm_interval`. Mismatches cause silent wrong predictions, not errors.

## Environment variables
- `.env` (root) — `USERNAME`, `PASSWORD`, `EMAIL` for MusicBrainz auth (data collection only)
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE` for backend URL
- `FRONTEND_ORIGIN` (backend env) — CORS origin restriction; defaults to `*` in dev
