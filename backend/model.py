from __future__ import annotations

import glob
import hashlib
import math
import os
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from lifelines import WeibullAFTFitter

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from info import AWARD_SHOWS, GENERATION_MAPPINGS, GROUP_COMPANIES, KPOP_GROUPS, MILITARY_SERVICE, SOLOISTS


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_CUTOFF = date(2024, 12, 31)
DEFAULT_MIN_PREDICTION_DATE = date(2025, 1, 1)
DEFAULT_INTERVAL_DAYS = 120

EMA_ALPHA = 0.3
COMEBACK_MONTHS = {1, 2, 3, 7, 8, 9}
AWARD_RUNUP_DAYS = 75

_BASE_EXCLUDED_SECONDARY = {"compilation", "live", "remix", "demo", "soundtrack"}


# ── Core utilities ─────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    import re
    name = name.strip()
    name = re.sub(r"[\/\\\:\*\?\"<>\|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name


# ── Sanitized lookup tables ────────────────────────────────────────────────────
# CSV filenames use sanitize() so all runtime lookups must go through these.

SANITIZED_GENERATION_MAPPINGS  = {sanitize(k): v for k, v in GENERATION_MAPPINGS.items()}
SANITIZED_GROUP_COMPANIES      = {sanitize(k): v for k, v in GROUP_COMPANIES.items()}
SANITIZED_SOLOISTS             = {sanitize(s): sanitize(p) for s, p in SOLOISTS.items()}
SOLOIST_ORIGINAL_BY_SANITIZED  = {sanitize(s): s for s in SOLOISTS}
SANITIZED_MILITARY_SERVICE     = {sanitize(k): v for k, v in MILITARY_SERVICE.items()}


# ── Core utilities ─────────────────────────────────────────────────────────────

def get_current_cutoff_dates() -> tuple[date, date]:
    today = date.today()
    return today, today + timedelta(days=1)


def stable_hash_int(value: str, modulo: int) -> int:
    """Deterministic SHA-256-based hash for categorical encoding."""
    if modulo <= 0:
        raise ValueError("modulo must be positive")
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(h[:16], 16) % modulo


def list_all_groups() -> List[str]:
    return [group for groups in KPOP_GROUPS.values() for group in groups]


def get_group_from_csv_path(csv_path: str) -> str:
    return os.path.splitext(os.path.basename(csv_path))[0]


# ── Data loading ───────────────────────────────────────────────────────────────

def _get_secondary_parts(val: str) -> set:
    return {p.strip().lower() for p in str(val).split("|") if p.strip()}


def load_group_releases(csv_path: str, excluded_secondary: set | None = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = {"title", "type", "release_date"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns {missing} in {csv_path}")

    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df.dropna(subset=["release_date"]).sort_values("release_date").reset_index(drop=True)

    for col, default in [("secondary_types", ""), ("track_count", 0), ("label", "")]:
        if col not in df.columns:
            df[col] = default
    df["track_count"] = pd.to_numeric(df["track_count"], errors="coerce").fillna(0).astype(int)

    excluded = excluded_secondary if excluded_secondary is not None else _BASE_EXCLUDED_SECONDARY
    df = df[~df["secondary_types"].apply(
        lambda v: bool(_get_secondary_parts(v) & excluded)
    )].reset_index(drop=True)
    return df


def load_all_releases(
    albums_dir: str,
    extra_excluded_secondary: set | None = None,
    exclude_predebut_mixtape: bool = False,
) -> Dict[str, pd.DataFrame]:
    excluded = _BASE_EXCLUDED_SECONDARY | (extra_excluded_secondary or set())

    group_to_df: Dict[str, pd.DataFrame] = {}
    for csv_path in sorted(glob.glob(os.path.join(albums_dir, "*.csv"))):
        group = get_group_from_csv_path(csv_path)
        try:
            df = load_group_releases(csv_path, excluded_secondary=excluded)
        except Exception:
            continue
        if not df.empty:
            group_to_df[group] = df

    if not exclude_predebut_mixtape:
        return group_to_df

    return _filter_predebut_mixtapes(group_to_df)


def _filter_predebut_mixtapes(group_to_df: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Drop Mixtape/Street releases that predate each group's first official release."""
    _UNOFFICIAL = {"mixtape/street", "spokenword"}

    # Earliest non-unofficial release per group
    debut_dates: Dict[str, pd.Timestamp] = {}
    for group, df in group_to_df.items():
        official = df[~df["secondary_types"].apply(lambda v: bool(_get_secondary_parts(v) & _UNOFFICIAL))]
        if not official.empty:
            debut_dates[group] = official["release_date"].min()

    # Soloists with no official releases fall back to their parent group's debut
    for group in group_to_df:
        if group not in debut_dates:
            parent = SANITIZED_SOLOISTS.get(group)
            if parent and parent in debut_dates:
                debut_dates[group] = debut_dates[parent]

    filtered: Dict[str, pd.DataFrame] = {}
    for group, df in group_to_df.items():
        debut = debut_dates.get(group)
        if debut is None:
            filtered[group] = df
            continue
        is_mixtape = df["secondary_types"].apply(lambda v: "mixtape/street" in _get_secondary_parts(v))
        df = df[~(is_mixtape & (df["release_date"] < debut))].reset_index(drop=True)
        if not df.empty:
            filtered[group] = df
    return filtered


# ── Domain lookups ─────────────────────────────────────────────────────────────

def members_in_military_at(group_key: str, as_of: pd.Timestamp) -> int:
    count = 0
    for _member, enlist_str, discharge_str in SANITIZED_MILITARY_SERVICE.get(group_key, []):
        enlist = pd.Timestamp(enlist_str)
        discharge = pd.Timestamp(discharge_str) if discharge_str else pd.Timestamp("2099-12-31")
        if enlist <= as_of <= discharge:
            count += 1
    return count


def days_to_next_award_show(as_of: pd.Timestamp) -> int:
    year = as_of.year
    candidates = []
    for _, month, day in AWARD_SHOWS:
        for y in (year, year + 1):
            try:
                dt = pd.Timestamp(y, month, day)
            except ValueError:
                continue
            if dt > as_of:
                candidates.append((dt - as_of).days)
    return min(candidates) if candidates else 365


def get_solo_releases_for_group(group_key: str, all_releases: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """All solo releases whose parent group matches group_key (sanitized)."""
    frames: List[pd.DataFrame] = []
    for soloist_key, parent_key in SANITIZED_SOLOISTS.items():
        if parent_key != group_key or soloist_key not in all_releases:
            continue
        solo_df = all_releases[soloist_key].copy()
        solo_df["soloist"] = SOLOIST_ORIGINAL_BY_SANITIZED.get(soloist_key, soloist_key)
        frames.append(solo_df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("release_date").reset_index(drop=True)


# ── Feature helpers ────────────────────────────────────────────────────────────

def _compute_interval_stats(
    intervals_before: pd.Series,
    intervals_including: pd.Series,
) -> dict:
    """Interval statistics used as model features."""
    n_before = len(intervals_before)
    n_incl = len(intervals_including)

    avg    = float(intervals_before.mean())   if n_before > 0 else float(DEFAULT_INTERVAL_DAYS)
    median = float(intervals_before.median()) if n_before > 0 else float(DEFAULT_INTERVAL_DAYS)
    std    = float(intervals_before.std())    if n_before > 1 else 0.0
    cv     = std / avg if avg > 0 else 0.0

    avg_last_3    = float(intervals_including.iloc[-3:].mean())   if n_incl > 0 else float(DEFAULT_INTERVAL_DAYS)
    median_last_3 = float(intervals_including.iloc[-3:].median()) if n_incl > 0 else float(DEFAULT_INTERVAL_DAYS)
    std_last_5    = float(intervals_including.iloc[-5:].std())    if n_incl >= 3 else 0.0

    ema: Optional[float] = None
    for v in intervals_including.tolist():
        ema = float(v) if ema is None else EMA_ALPHA * float(v) + (1 - EMA_ALPHA) * ema
    if ema is None:
        ema = float(DEFAULT_INTERVAL_DAYS)

    trend = 0.0
    trend_vals = intervals_including.iloc[-5:].values
    if len(trend_vals) >= 3:
        slope = float(np.polyfit(range(len(trend_vals)), trend_vals, 1)[0])
        trend = slope / max(avg, 1.0)

    return {
        "avg_interval_so_far":    avg,
        "median_interval_so_far": median,
        "std_interval_so_far":    std,
        "interval_cv":            cv,
        "ema_interval_so_far":    ema,
        "avg_last_3_intervals":   avg_last_3,
        "median_last_3_intervals": median_last_3,
        "std_last_5_intervals":   std_last_5,
        "release_acceleration":   avg_last_3 / max(avg, 1.0),
        "interval_trend_5":       trend,
    }


def _compute_solo_features(
    solo_releases: pd.DataFrame,
    as_of: pd.Timestamp,
    debut_date: pd.Timestamp,
) -> dict:
    """Solo activity features relative to as_of date."""
    null_result = {
        "recent_solos_6m": 0,
        "recent_solo_30d": 0,
        "days_since_last_solo": 9999.0,
        "solo_frequency": 0.0,
    }
    if solo_releases.empty or "release_date" not in solo_releases.columns:
        return null_result

    six_months_ago  = as_of - pd.DateOffset(months=6)
    thirty_days_ago = as_of - pd.DateOffset(days=30)
    before = solo_releases[solo_releases["release_date"] < as_of]

    recent_6m  = len(solo_releases[(solo_releases["release_date"] >= six_months_ago)  & (solo_releases["release_date"] < as_of)])
    recent_30d = len(solo_releases[(solo_releases["release_date"] >= thirty_days_ago) & (solo_releases["release_date"] < as_of)])
    days_since = float((as_of - before.iloc[-1]["release_date"]).days) if not before.empty else 9999.0
    years_since_debut = (as_of - debut_date).days / 365.25
    frequency = len(before) / max(years_since_debut, 0.1)

    return {
        "recent_solos_6m":      recent_6m,
        "recent_solo_30d":      recent_30d,
        "days_since_last_solo": days_since,
        "solo_frequency":       float(frequency),
    }


def _compute_seasonality(release_date: pd.Timestamp) -> dict:
    """Cyclical and categorical seasonality features."""
    day_of_year = int(release_date.dayofyear)
    return {
        "day_sin":        float(np.sin(2 * np.pi * day_of_year / 366.0)),
        "day_cos":        float(np.cos(2 * np.pi * day_of_year / 366.0)),
        "comeback_season": int(release_date.month in COMEBACK_MONTHS),
    }


def _get_effective_company(label_str, group_company: Optional[str]) -> str:
    label = str(label_str).strip()
    if label and label not in ("", "nan"):
        return label
    return group_company if group_company is not None else "Unknown"


# ── Training pipeline ──────────────────────────────────────────────────────────

FEATURE_COLS = [
    "group_encoded", "generation", "type_encoded", "company_encoded",
    "release_number", "days_since_debut", "days_since_previous",
    "avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
    "interval_cv", "ema_interval_so_far",
    "avg_last_3_intervals", "median_last_3_intervals", "std_last_5_intervals",
    "releases_this_year", "releases_last_year",
    "day_sin", "day_cos", "comeback_season",
    "days_since_previous_norm", "release_acceleration",
    "members_in_military",
    "recent_solos_6m", "recent_solo_30d", "days_since_last_solo", "solo_frequency",
    "interval_trend_5", "last_type_encoded", "type_changed",
    "track_count_log",
    "days_to_awards", "award_run_up",
]


def extract_features_from_group(
    df: pd.DataFrame,
    group_key: str,
    cutoff: date,
    all_releases: Dict[str, pd.DataFrame],
) -> List[Dict]:
    """One training row per observed release, predicting the gap to the next one."""
    parent_group_key = SANITIZED_SOLOISTS.get(group_key, group_key)
    generation = SANITIZED_GENERATION_MAPPINGS.get(parent_group_key, 0)
    company = SANITIZED_GROUP_COMPANIES.get(parent_group_key)
    solo_releases = get_solo_releases_for_group(parent_group_key, all_releases)

    cutoff_dt = pd.Timestamp(cutoff)
    df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
    if len(df_sorted) < 2:
        return []

    debut_date = df_sorted.iloc[0]["release_date"]
    features: List[Dict] = []

    for i in range(1, len(df_sorted) - 1):
        current = df_sorted.iloc[i]
        prev_releases = df_sorted.iloc[:i]
        current_date = current["release_date"]
        target_days = (df_sorted.iloc[i + 1]["release_date"] - current_date).days

        intervals_before    = prev_releases["release_date"].diff().dt.days.dropna()
        intervals_including = df_sorted.iloc[:i + 1]["release_date"].diff().dt.days.dropna()
        days_since_previous = (current_date - prev_releases.iloc[-1]["release_date"]).days

        stats  = _compute_interval_stats(intervals_before, intervals_including)
        solos  = _compute_solo_features(solo_releases, current_date, debut_date)
        season = _compute_seasonality(current_date)

        effective_company = _get_effective_company(
            current.get("label", "") if "label" in current.index else "",
            company,
        )
        days_to_awards = days_to_next_award_show(current_date)

        features.append({
            "group":          group_key,
            "generation":     generation,
            "company":        company,
            "release_type":   current["type"],
            "release_number": i,
            "as_of_date":     pd.Timestamp(current_date),
            "days_since_debut":        (current_date - debut_date).days,
            "days_since_previous":     float(days_since_previous),
            "days_since_previous_norm": float(days_since_previous) / max(stats["avg_interval_so_far"], 1.0),
            **stats,
            **solos,
            **season,
            "releases_this_year":  len(prev_releases[prev_releases["release_date"].dt.year == current_date.year]),
            "releases_last_year":  len(prev_releases[prev_releases["release_date"].dt.year == current_date.year - 1]),
            "members_in_military": members_in_military_at(parent_group_key, current_date),
            "last_type_encoded":   stable_hash_int(str(prev_releases.iloc[-1]["type"]), 10),
            "type_changed":        int(str(current["type"]) != str(prev_releases.iloc[-1]["type"])),
            "track_count_log":     float(np.log1p(int(current.get("track_count", 0)))),
            "release_label":       effective_company,
            "days_to_awards":      days_to_awards,
            "award_run_up":        int(days_to_awards <= AWARD_RUNUP_DAYS),
            "target_days":         float(target_days),
        })

    return features


def prepare_training_data(data_by_group: Dict[str, pd.DataFrame], cutoff: date) -> pd.DataFrame:
    all_features: List[Dict] = []
    for group, df in data_by_group.items():
        all_features.extend(extract_features_from_group(df, group, cutoff, data_by_group))
    if not all_features:
        return pd.DataFrame()
    df_features = pd.DataFrame(all_features)
    df_features["group_encoded"]   = df_features["group"].apply(lambda v: stable_hash_int(str(v), 1000))
    df_features["type_encoded"]    = df_features["release_type"].apply(lambda v: stable_hash_int(str(v), 10))
    df_features["company_encoded"] = df_features["release_label"].fillna("Unknown").apply(lambda v: stable_hash_int(str(v), 100))
    df_features["target_days_log"] = np.log1p(df_features["target_days"])
    return df_features



def train_weibull_aft_model(df_train: pd.DataFrame) -> WeibullAFTFitter:
    """Train a Weibull AFT model on raw inter-release intervals (not log-transformed).

    Weibull requires strictly positive durations; intervals of 0 are clipped to 1 day.
    """
    df_pos = df_train.copy()
    df_pos["target_days"] = df_pos["target_days"].clip(lower=1.0)
    fitter = WeibullAFTFitter(penalizer=0.01)
    fitter.fit(df_pos[FEATURE_COLS + ["target_days"]], duration_col="target_days")
    return fitter


# ── Prediction ─────────────────────────────────────────────────────────────────

def _extract_inference_features(
    df_group: pd.DataFrame,
    group_key: str,
    cutoff: date,
    all_releases: Dict[str, pd.DataFrame],
) -> Optional[tuple]:
    """Shared feature extraction for all inference functions. Returns (X_pred, last_date) or None."""
    cutoff_dt = pd.Timestamp(cutoff)
    df_cut = df_group[df_group["release_date"] <= cutoff_dt].sort_values("release_date").reset_index(drop=True)
    if len(df_cut) < 2:
        return None

    last_release    = df_cut.iloc[-1]
    last_date       = last_release["release_date"]
    prev_releases   = df_cut.iloc[:-1]
    debut_date      = df_cut.iloc[0]["release_date"]

    parent_group_key = SANITIZED_SOLOISTS.get(group_key, group_key)
    generation       = SANITIZED_GENERATION_MAPPINGS.get(parent_group_key, 0)
    company          = SANITIZED_GROUP_COMPANIES.get(parent_group_key)
    solo_releases    = get_solo_releases_for_group(parent_group_key, all_releases)

    intervals_before    = prev_releases["release_date"].diff().dt.days.dropna()
    intervals_including = df_cut["release_date"].diff().dt.days.dropna()
    days_since_previous = (last_date - prev_releases.iloc[-1]["release_date"]).days

    stats  = _compute_interval_stats(intervals_before, intervals_including)
    solos  = _compute_solo_features(solo_releases, last_date, debut_date)
    season = _compute_seasonality(last_date)

    effective_company = _get_effective_company(
        last_release.get("label", "") if "label" in last_release.index else "",
        company,
    )
    second_last    = df_cut.iloc[-2]
    days_to_awards = days_to_next_award_show(last_date)

    feature_dict = {
        "group_encoded":    stable_hash_int(str(group_key), 1000),
        "generation":       generation,
        "type_encoded":     stable_hash_int(str(last_release["type"]), 10),
        "company_encoded":  stable_hash_int(effective_company, 100),
        "release_number":   int(len(df_cut) - 1),
        "days_since_debut": (last_date - debut_date).days,
        "days_since_previous":      float(days_since_previous),
        "days_since_previous_norm": float(days_since_previous) / max(stats["avg_interval_so_far"], 1.0),
        **stats,
        **solos,
        **season,
        "releases_this_year":  len(prev_releases[prev_releases["release_date"].dt.year == last_date.year]),
        "releases_last_year":  len(prev_releases[prev_releases["release_date"].dt.year == last_date.year - 1]),
        "members_in_military": members_in_military_at(parent_group_key, last_date),
        "last_type_encoded":   stable_hash_int(str(second_last["type"]), 10),
        "type_changed":        int(str(last_release["type"]) != str(second_last["type"])),
        "track_count_log":     float(np.log1p(int(last_release.get("track_count", 0)))),
        "days_to_awards":      days_to_awards,
        "award_run_up":        int(days_to_awards <= AWARD_RUNUP_DAYS),
    }

    X_pred = pd.DataFrame([feature_dict], columns=FEATURE_COLS)
    return X_pred, last_date


def _apply_cycles_and_sort(
    last_date,
    pred_days_25: int,
    pred_days_50: int,
    pred_days_75: int,
    min_prediction_date: date,
) -> Dict[str, object]:
    """Advance overdue predictions by whole cycles and enforce low/med/high ordering."""
    pred_date_25 = last_date + timedelta(days=pred_days_25)
    pred_date_50 = last_date + timedelta(days=pred_days_50)
    pred_date_75 = last_date + timedelta(days=pred_days_75)

    min_pred_dt = pd.Timestamp(min_prediction_date)
    cycles = math.ceil((min_pred_dt - pred_date_50).days / pred_days_50) if pred_date_50 < min_pred_dt else 0
    pred_date_25 = max(pred_date_25 + timedelta(days=cycles * pred_days_25), min_pred_dt)
    pred_date_50 = pred_date_50 + timedelta(days=cycles * pred_days_50)
    pred_date_75 = pred_date_75 + timedelta(days=cycles * pred_days_75)

    pairs = sorted(
        [(pred_date_25, pred_days_25), (pred_date_50, pred_days_50), (pred_date_75, pred_days_75)],
        key=lambda x: x[0],
    )
    (pred_date_low, pred_days_low), (pred_date_med, pred_days_med), (pred_date_high, pred_days_high) = pairs

    return {
        "pred_date_low":  pred_date_low,
        "pred_date_med":  pred_date_med,
        "pred_date_high": pred_date_high,
        "pred_days_low":  pred_days_low,
        "pred_days_med":  pred_days_med,
        "pred_days_high": pred_days_high,
    }



def predict_next_release_weibull_interval(
    df_group: pd.DataFrame,
    model: WeibullAFTFitter,
    group_key: str,
    cutoff: date,
    min_prediction_date: date,
    all_releases: Dict[str, pd.DataFrame],
) -> Optional[Dict[str, object]]:
    """Predict the next release window using Weibull AFT survival analysis (p25/p50/p75)."""
    result = _extract_inference_features(df_group, group_key, cutoff, all_releases)
    if result is None:
        return None
    X_pred, last_date = result

    def safe_days(p: float, round_mode: str) -> int:
        raw = max(1.0, float(model.predict_percentile(X_pred, p=p).iloc[0]))
        if round_mode == "floor": return max(1, int(np.floor(raw)))
        if round_mode == "ceil":  return max(1, int(np.ceil(raw)))
        return max(1, int(np.round(raw)))

    pred_days_25 = safe_days(0.25, "floor")
    pred_days_50 = safe_days(0.50, "round")
    pred_days_75 = safe_days(0.75, "ceil")

    # Enforce ordering before cycle-advance
    pred_days_25 = min(pred_days_25, pred_days_50)
    pred_days_75 = max(pred_days_75, pred_days_50)

    return _apply_cycles_and_sort(last_date, pred_days_25, pred_days_50, pred_days_75, min_prediction_date)


# ── Cache utilities ────────────────────────────────────────────────────────────

def compute_data_signature(albums_dir: str) -> str:
    """SHA-256 hash of CSV filenames + mtimes, used to key the model cache."""
    hasher = hashlib.sha256()
    for csv_path in sorted(glob.glob(os.path.join(albums_dir, "*.csv"))):
        try:
            st = os.stat(csv_path)
        except FileNotFoundError:
            continue
        hasher.update(os.path.basename(csv_path).encode())
        hasher.update(str(int(st.st_mtime)).encode())
        hasher.update(str(int(st.st_size)).encode())
    return hasher.hexdigest()[:16]


def load_group_error_stats(group_name: str) -> Optional[Dict[str, float]]:
    """Load historical MAE/MAPE from versions/*/predictions.csv if available."""
    versions_dir = os.path.join(ROOT_DIR, "versions")
    if not os.path.exists(versions_dir):
        return None
    version_dirs = [
        os.path.join(versions_dir, d)
        for d in os.listdir(versions_dir)
        if os.path.isdir(os.path.join(versions_dir, d))
    ]
    maes: List[float] = []
    mapes: List[float] = []
    for vdir in version_dirs:
        csv_path = os.path.join(vdir, "predictions.csv")
        if not os.path.exists(csv_path):
            continue
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "group" not in df.columns:
            continue
        sub = df[df["group"] == group_name]
        if sub.empty:
            continue
        if "error_days" in sub.columns:
            maes.extend(sub["error_days"].dropna().astype(float).tolist())
        if "error_pct" in sub.columns:
            mapes.extend(sub["error_pct"].dropna().astype(float).tolist())
    if not maes and not mapes:
        return None
    out: Dict[str, float] = {}
    if maes:
        out["mae_days"] = float(pd.Series(maes).mean())
    if mapes:
        out["mape_pct"] = float(pd.Series(mapes).mean())
    return out
