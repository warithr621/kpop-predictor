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

**Both at once** (from repo root, via `concurrently`; uses `~/venv/bin/uvicorn`):
```bash
npm run dev
```

**Data collection** (requires MusicBrainz credentials in `.env`):
```bash
source ~/venv/bin/activate && python data_collection.py        # only scrapes groups with no CSV yet
source ~/venv/bin/activate && python data_collection.py --all  # re-scrapes and OVERWRITES every CSV
```
A full `--all` run takes a while (MusicBrainz rate limit, one extra request per release group).

**Updating existing data — only append new releases.** `--all` rewrites each CSV wholesale, which can pull in historical rows that were previously excluded on purpose (OSTs, repackages, re-dated entries). After a re-scrape, keep every committed row exactly as-is and only add scraped rows dated *after* that group's latest committed release; review anything older by hand. Compare against the committed CSVs (`git show HEAD:albums/<file>.csv`) and check `git diff --stat albums` shows insertions only. Parse dates with an explicit format when comparing (see the date note below).

**Backtest / model evaluation** (~45s; retrains once per monthly cutoff):
```bash
source ~/venv/bin/activate && python analysis.py
```

> Always activate `~/venv` before running Python — the system Python is externally managed.

## Architecture

Full-stack K-pop release prediction app: a Python/FastAPI ML backend + Next.js frontend.

### Data layer
- `albums/` — one CSV per artist/group (`title, type, release_date`, optional `secondary_types, track_count, label`), scraped from MusicBrainz via `data_collection.py`. Entries with excluded `secondary_types` are silently dropped at load time (`_BASE_EXCLUDED_SECONDARY = {"compilation", "live", "remix", "demo", "soundtrack"}`). Pre-debut Mixtape/Street releases are also filtered (see below). The CSVs are treated as raw archives; filtering is always applied at load time, not at scrape time. Dates are parsed strictly as `YYYY-MM-DD`; partial dates (`2012`, `2016-05`) are dropped.
- `artist_ids.json` — cached MusicBrainz artist IDs to avoid re-scraping.
- `info.py` — single source of truth for all static metadata:
  - `KPOP_GROUPS` — groups by generation (3rd/4th/5th)
  - `SOLOISTS` — soloist → parent group mapping
  - `GENERATION_MAPPINGS`, `GROUP_COMPANIES`
  - `MILITARY_SERVICE` — per-member enlistment/discharge dates (used as a live feature)
  - `AWARD_SHOWS` — major K-pop award ceremony dates (MAMA, MMA, GDA, etc.), used to compute `days_to_awards` and `award_run_up` features

### Backend (`backend/`)
- `model.py` — all ML logic: feature engineering, Weibull AFT training, prediction, and caching utilities.
  - Uses `lifelines.WeibullAFTFitter` (`train_weibull_aft_model`) on raw `target_days` — the AFT model applies the log-linear transform internally; do **not** pass log-transformed values. `penalizer=0.01` for L2 regularization. Zero-day intervals are clipped to 1 before fitting.
  - Quantile predictions via `model.predict_percentile(X, p=..., conditional_after=[elapsed])`, returned by `predict_next_release_weibull_interval`. Predictions are conditioned on the days already elapsed since the last release (lifelines returns *remaining* time, so `elapsed` is added back). The raw p25–p75 window is used with no spread shrinking.
  - Shared inference helpers: `_extract_inference_features` (builds feature row from last release snapshot) and `_apply_cycles_and_sort` (advances overdue predictions by whole cycles anchored on p50, then sorts low/med/high). With conditional prediction the model's dates always land after the cutoff, so the cycle-advance is effectively a safety net there; it still matters for the naive baselines in `analysis.py`.
  - Feature helpers `_compute_interval_stats`, `_compute_solo_features`, `_compute_seasonality` are shared by training and inference — edit the helpers, not the callers, to change feature logic
  - `FEATURE_COLS` is the single source of truth for the 30-column feature list; it is used by all training and inference paths
  - Cache key prefix: `model_v17_weibull_`
  - Key constants: `EMA_ALPHA = 0.3`, `COMEBACK_MONTHS = {1,2,3,7,8,9}`, `AWARD_RUNUP_DAYS = 75`
- `app.py` — FastAPI app: `/api/groups`, `/api/releases`, `/api/predict`, `/api/status`. Trained model is pickled to `backend/cache/` (gitignored) keyed by a data signature + cutoff date; cache auto-invalidates when CSVs change or the day rolls over. Old pickles accumulate there and are safe to delete. **Bump the cache key version** (`model_vN_weibull_`) whenever feature columns change.
  - `load_group_error_stats` reads per-group MAE from `versions/*/predictions.csv`; that directory doesn't currently exist, so `/api/predict` always falls back to half the predicted p25–p75 width for `uncertainty_days`.
- `analysis.py` (root) — rolling-origin backtest: for each monthly cutoff T, trains only on data known at T, predicts each 4th/5th gen group's next release exactly as the app does, and scores against the first actual release after T. Compares the model against naive baselines (median of recent gaps). `compare()` accepts arbitrary predictor factories for experiments. Any modeling change should beat the current numbers here before shipping.

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
- **Date parsing**: `load_group_releases` uses `format="%Y-%m-%d"`. Never call `pd.to_datetime` on release dates without an explicit format — pandas infers the format from the first row, so a year-only first date (`2012`) silently turns every later full date into NaT (this previously wiped out most of I.M's and Jay_B's history).
- **Future-dated releases**: MusicBrainz sometimes lists announced releases with future dates. Training and inference filter to `release_date <= cutoff`, so they're ignored by the model, but `/api/releases` still returns them.
- **Feature parity**: `FEATURE_COLS` in `model.py` is the authoritative 30-column list used by both training and inference. Adding or removing a feature requires updating `FEATURE_COLS`, the relevant feature helper, and bumping the cache key.

## Features (30 total)

One training row per observed release, predicting the interval to the *next* release. Target is raw `target_days` (clipped to 1; the Weibull AFT model applies the log-linear transform internally). All feature computation is in `_compute_interval_stats`, `_compute_solo_features`, and `_compute_seasonality` in `model.py`.

**Identity** (1)
- `generation` — 3 / 4 / 5 (from `GENERATION_MAPPINGS`)

Hashed group/type/company IDs were removed: as raw numbers in a linear model they imposed a meaningless ordering and added no backtest accuracy. Don't reintroduce hashed IDs as numeric features.

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

**Release type change** (1)
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

**Market** (1)
- `is_japanese_release` — 1 if the release's label matches `JAPANESE_LABELS` in `model.py`

## Model performance (rolling backtest, data through 2026-11-17)

From `python analysis.py` — 23 monthly cutoffs (Jul 2024 – May 2026), 4th/5th gen groups, 634 scored predictions:

| | median err | mean err | bias | p25–p75 coverage | ±6 wk | ±12 wk |
|---|---|---|---|---|---|---|
| Weibull AFT (current) | 34 d | 52 d | −8 d | 54% | 61% | 84% |
| Naive: median of all past gaps | 38 d | 59 d | −22 d | 61% | 53% | 77% |

Findings from the Nov 2026 overhaul (useful before trying further changes):
- The old leave-last-out backtest trained on the releases it scored and floored predictions at the actual date, so its numbers (~21 d median, 100% within 12 wk) were inflated. Before the fixes the model was no better than the naive baseline.
- Conditioning on elapsed time (`conditional_after`) was the main win: mean error 61→52 d, bias −33→−8 d.
- Fitted Weibull shape ρ ≈ 1.0 — close to memoryless, which is why conditioning on elapsed time matters so much.
- Tried and rejected: adding right-censored rows for each group's open gap (fixed bias but worsened median error), stronger L2 (`penalizer=0.1`, no change).
- A 9-feature model (EMA/median/last-3 intervals, days_since_previous, acceleration, CV, generation, military, releases_last_year) scores about the same as the full 30 — most engineered features add little measurable signal.
- Any short gap counts as a release (pre-release single + EP a week apart = 7-day interval). Redefining the target as "comebacks" (merging nearby releases) is untested and likely the biggest remaining lever.

## Environment variables
- `.env` (root) — `USERNAME`, `PASSWORD`, `EMAIL` for MusicBrainz auth (data collection only)
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE` for backend URL
- `FRONTEND_ORIGIN` (backend env) — CORS origin restriction; defaults to `*` in dev
