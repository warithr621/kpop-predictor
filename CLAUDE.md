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
- `albums/` — one CSV per artist/group (`title, type, release_date`, optional `secondary_types, track_count, label`), scraped from MusicBrainz via `data_collection.py`. Entries with excluded `secondary_types` are silently dropped at load time (`_BASE_EXCLUDED_SECONDARY = {"compilation", "live", "remix", "demo", "soundtrack"}`). Pre-debut Mixtape/Street releases are also filtered (see below). The CSVs are treated as raw archives; filtering is always applied at load time, not at scrape time.
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
  - Feature helpers `_compute_interval_stats`, `_compute_solo_features`, `_compute_seasonality` are shared by both `extract_features_from_group` and `predict_next_release_lightgbm_interval` — edit the helpers, not the callers, to change feature logic
  - `FEATURE_COLS` is the single source of truth for the 33-column feature list; it is used by both training and inference
  - Overdue groups (p50 raw date < today) are advanced forward by a shared cycle count anchored on p50 to prevent quantile collapse
  - Final date ordering is enforced by sorting all three (date, days) pairs together — do not revert to piecemeal min/max
  - Cache key prefix: `model_v12_quantiles_`
  - Key constants: `EMA_ALPHA = 0.3`, `COMEBACK_MONTHS = {1,2,3,7,8,9}`, `AWARD_RUNUP_DAYS = 75`
- `app.py` — FastAPI app: `/api/groups`, `/api/releases`, `/api/predict`, `/api/status`. Trained models are pickled to `backend/cache/` keyed by a data signature + cutoff date; cache auto-invalidates when CSVs change. **Bump the cache key version** (`model_vN_quantiles_`) whenever feature columns or quantiles change.
- `analysis.py` (root) — offline backtest (leave-last-out): withholds each group's most recent release and reports MAE/coverage/within-N-weeks. Run this to sanity-check any model change. `INCLUDE_3RD_GEN` controls which 3rd-gen groups are evaluated (currently only TWICE).

### Frontend (`frontend/src/`)
- Next.js (Pages Router) + Tailwind CSS
- **Pages**
  - `pages/index.jsx` — group picker with typing-animation header; uses `<GenerationSection>` for each gen column
  - `pages/group.jsx` — release timeline + predict button + `<PredictionCard>`; all color logic delegated to `lib/themeUtils.js`
- **Components**
  - `components/Timeline.jsx` — SVG release history; constants `SVG_WIDTH/HEIGHT/PAD` at top
  - `components/ReleaseModal.jsx` — release detail modal, extracted from Timeline
  - `components/PredictionCard.jsx` — p25/p50/p75 range bar card, extracted from group.jsx
  - `components/GenerationSection.jsx` — reusable gen column (badge + card list), extracted from index.jsx
  - `components/Typing.jsx` — animated typing header
- **Utilities**
  - `lib/api.js` — all fetch calls (`fetchGroups`, `fetchReleases`, `predictNextRelease`); `NEXT_PUBLIC_API_BASE` controls the backend URL (defaults to `http://localhost:8000`)
  - `lib/dateUtils.js` — `fmt`, `fmtShort`, `daysFromNow`, `parseISODate`, `toDate`; always use `fmtShort` with `year: 'numeric'` to avoid cross-year ambiguity
  - `lib/themeUtils.js` — `getAccentColor`, `getGlowColor`, `getGradientEnd`, `getBadgeClass`; single source of truth for generation-aware colors
- **Styles** — dark techno theme in `styles/globals.css` via CSS custom properties: `--accent-4th: #f0287a` (pink), `--accent-5th: #22d3ee` (cyan). CSS classes cover range bar (`.range-bar*`), modal (`.modal-*`), error banner (`.error-banner`), and page container (`.page-container`). Prefer CSS classes over inline styles for anything reused across components.

### Key design details
- **Soloists inherit parent group features**: `get_solo_releases_for_group` pulls member solo releases as activity signals (e.g. solo drops before a group comeback). Soloist predictions also benefit from parent group history.
- **Pre-debut Mixtape/Street filtering**: `load_all_releases(exclude_predebut_mixtape=True)` drops Mixtape/Street releases that predate a group's first official release. Both `app.py` and `analysis.py` use this flag — keep them in sync.
- **Cutoff date**: training always uses data up to today (`get_current_cutoff_dates()`). The hardcoded `DEFAULT_CUTOFF = 2024-12-31` is only a fallback — never use it for production predictions.
- **Group name sanitization**: CSV filenames use `sanitize()` (spaces/special chars → `_`). `info.py` keys use original display names. Both `model.py` and `app.py` call `sanitize()` consistently when looking up CSVs.
- **Feature parity**: `FEATURE_COLS` in `model.py` is the authoritative 33-column list used by both training and inference. Adding or removing a feature requires updating `FEATURE_COLS`, the relevant feature helper, and bumping the cache key.

## Features (33 total)

One training row per observed release, predicting the interval to the *next* release. Target is `log1p(days)` (log-transformed to reduce skew from outlier gaps). All feature computation is in `_compute_interval_stats`, `_compute_solo_features`, and `_compute_seasonality` in `model.py`.

**Identity / categorical** (4)
- `group_encoded` — SHA-256 hash of group name mod 1000
- `generation` — 3 / 4 / 5 (from `GENERATION_MAPPINGS`)
- `type_encoded` — SHA-256 hash of release type (album/EP/single…) mod 10
- `company_encoded` — SHA-256 hash of label/company mod 100; prefers per-release label over group default

**Release position** (2)
- `release_number` — 0-indexed ordinal of this release in the group's history
- `days_since_debut` — days from first release to current release date

**Recent gap** (1)
- `days_since_previous` — days between this release and the one before it

**Historical interval statistics** (6)
- `avg_interval_so_far`, `median_interval_so_far`, `std_interval_so_far` — mean/median/std of all prior inter-release gaps
- `interval_cv` — coefficient of variation (`std / avg`); measures release regularity
- `ema_interval_so_far` — exponential moving average of intervals (α = `EMA_ALPHA`); weights recent gaps more
- `days_since_previous_norm` — `days_since_previous / avg_interval_so_far`

**Rolling / recent interval features** (4)
- `avg_last_3_intervals`, `median_last_3_intervals` — mean/median of the 3 most recent gaps
- `std_last_5_intervals` — std of the 5 most recent gaps
- `release_acceleration` — `avg_last_3 / avg_so_far`; < 1 means releasing faster lately

**Trend** (1)
- `interval_trend_5` — linear slope of the last 5 gaps, normalized by `avg_interval_so_far`; positive = slowing down

**Seasonality** (3)
- `day_sin`, `day_cos` — sine/cosine encoding of day-of-year (captures annual release cycles)
- `comeback_season` — 1 if month ∈ `COMEBACK_MONTHS` (Jan, Feb, Mar, Jul, Aug, Sep)

**Activity counts** (2)
- `releases_this_year` — releases by this group in the same calendar year as the current release
- `releases_last_year` — releases in the prior calendar year

**Release type change** (2)
- `last_type_encoded` — type of the *previous* release (hash mod 10)
- `type_changed` — 1 if release type differs from the previous one

**Track count** (1)
- `track_count_log` — `log1p(track_count)` of the current release; larger releases may signal longer recovery gaps

**Military service** (1)
- `members_in_military` — count of members actively serving on the current release date (South Korean mandatory service; sourced from `MILITARY_SERVICE` in `info.py`)

**Solo activity** (4)
- `recent_solos_6m` — solo releases from parent group members in the 6 months before this release
- `recent_solo_30d` — same, last 30 days only
- `days_since_last_solo` — days since any parent group member's most recent solo drop
- `solo_frequency` — total solo releases before this date ÷ years since debut

**Award show proximity** (2)
- `days_to_awards` — days until the next major K-pop award ceremony (MAMA / MMA / GDA / SMA / Gaon)
- `award_run_up` — 1 if `days_to_awards ≤ AWARD_RUNUP_DAYS` (groups release earlier to be fresh in voters' minds)

## Environment variables
- `.env` (root) — `USERNAME`, `PASSWORD`, `EMAIL` for MusicBrainz auth (data collection only)
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE` for backend URL
- `FRONTEND_ORIGIN` (backend env) — CORS origin restriction; defaults to `*` in dev
