from __future__ import annotations

import glob
import hashlib
import math
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

# Import from project root
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from info import GENERATION_MAPPINGS, KPOP_GROUPS, SOLOISTS, GROUP_COMPANIES, MILITARY_SERVICE, AWARD_SHOWS


DEFAULT_CUTOFF = date(2024, 12, 31)
DEFAULT_MIN_PREDICTION_DATE = date(2025, 1, 1)


def get_current_cutoff_dates():
    """Get current date as cutoff and next day as min prediction date."""
    today = date.today()
    return today, today + timedelta(days=1)


def sanitize(name: str) -> str:
    import re
    name = name.strip()
    name = re.sub(r"[\/\\\:\*\?\"<>\|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name


DEFAULT_INTERVAL_DAYS = 120


def stable_hash_int(value: str, modulo: int) -> int:
    """Deterministic hash for categorical values (consistent across runs)."""
    if modulo <= 0:
        raise ValueError("modulo must be positive")
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(h[:16], 16) % modulo


# Precompute sanitized lookup tables so that the model works consistently with
# CSV keys (which use `sanitize()` for filenames).
SANITIZED_GENERATION_MAPPINGS = {sanitize(k): v for k, v in GENERATION_MAPPINGS.items()}
SANITIZED_GROUP_COMPANIES = {sanitize(k): v for k, v in GROUP_COMPANIES.items()}
SANITIZED_SOLOISTS = {sanitize(soloist): sanitize(parent_group) for soloist, parent_group in SOLOISTS.items()}
SOLOIST_ORIGINAL_BY_SANITIZED = {sanitize(soloist): soloist for soloist in SOLOISTS.keys()}
SANITIZED_MILITARY_SERVICE = {sanitize(k): v for k, v in MILITARY_SERVICE.items()}


def list_all_groups() -> List[str]:
    return [group for groups in KPOP_GROUPS.values() for group in groups]


def get_group_from_csv_path(csv_path: str) -> str:
    base = os.path.basename(csv_path)
    name, _ = os.path.splitext(base)
    return name


def load_group_releases(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    expected_cols = {"title", "type", "release_date"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns {missing} in {csv_path}")
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df.dropna(subset=["release_date"]).copy()
    df = df.sort_values(by="release_date").reset_index(drop=True)

    for col, default in [("secondary_types", ""), ("track_count", 0), ("label", "")]:
        if col not in df.columns:
            df[col] = default
    df["track_count"] = pd.to_numeric(df["track_count"], errors="coerce").fillna(0).astype(int)

    _EXCLUDED_SECONDARY = {"compilation", "live", "remix", "demo"}

    def _has_excluded(val):
        parts = {p.strip().lower() for p in str(val).split("|") if p.strip()}
        return bool(parts & _EXCLUDED_SECONDARY)

    df = df[~df["secondary_types"].apply(_has_excluded)].reset_index(drop=True)
    return df


def load_all_releases(albums_dir: str) -> Dict[str, pd.DataFrame]:
    group_to_df: Dict[str, pd.DataFrame] = {}
    for csv_path in sorted(glob.glob(os.path.join(albums_dir, "*.csv"))):
        group = get_group_from_csv_path(csv_path)
        try:
            df = load_group_releases(csv_path)
        except Exception:
            continue
        if not df.empty:
            group_to_df[group] = df
    return group_to_df


def members_in_military_at(group_key: str, as_of: pd.Timestamp) -> int:
    """Count of members from group_key who were serving in the military on as_of date."""
    records = SANITIZED_MILITARY_SERVICE.get(group_key, [])
    count = 0
    for _member, enlist_str, discharge_str in records:
        enlist = pd.Timestamp(enlist_str)
        discharge = pd.Timestamp(discharge_str) if discharge_str else pd.Timestamp("2099-12-31")
        if enlist <= as_of <= discharge:
            count += 1
    return count


def days_to_next_award_show(as_of: pd.Timestamp) -> int:
    """Days from as_of until the next major K-pop award ceremony."""
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
    """
    Returns all solo releases whose parent group matches `group_key`.

    `group_key` is expected to already be sanitized (same as CSV filenames).
    """
    solo_releases: List[pd.DataFrame] = []
    for soloist_sanitized, soloist_parent_group_key in SANITIZED_SOLOISTS.items():
        if soloist_parent_group_key != group_key:
            continue
        if soloist_sanitized not in all_releases:
            continue
        solo_df = all_releases[soloist_sanitized].copy()
        solo_df["soloist"] = SOLOIST_ORIGINAL_BY_SANITIZED.get(soloist_sanitized, soloist_sanitized)
        solo_releases.append(solo_df)
    if not solo_releases:
        return pd.DataFrame()
    combined = pd.concat(solo_releases, ignore_index=True)
    combined = combined.sort_values("release_date").reset_index(drop=True)
    return combined


def extract_features_from_group(
    df: pd.DataFrame,
    group_key: str,
    cutoff: date,
    all_releases: Dict[str, pd.DataFrame],
) -> List[Dict]:
    """
    Builds one training row per observed release, predicting the next interval.

    `group_key` is expected to already be sanitized to match CSV filenames.
    """
    features: List[Dict] = []

    parent_group_key = SANITIZED_SOLOISTS.get(group_key, group_key)
    generation = SANITIZED_GENERATION_MAPPINGS.get(parent_group_key, 0)
    company = SANITIZED_GROUP_COMPANIES.get(parent_group_key, None)

    cutoff_dt = pd.Timestamp(cutoff)
    df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
    if len(df_sorted) < 2:
        return features

    solo_releases = get_solo_releases_for_group(parent_group_key, all_releases)

    for i in range(1, len(df_sorted)):
        current_release = df_sorted.iloc[i]
        previous_releases = df_sorted.iloc[:i]

        if i < len(df_sorted) - 1:
            next_release = df_sorted.iloc[i + 1]
            target_days = (next_release["release_date"] - current_release["release_date"]).days
        else:
            continue

        current_date = current_release["release_date"]

        intervals_before_current = previous_releases["release_date"].diff().dt.days.dropna()
        history_including_current = df_sorted.iloc[: i + 1]
        intervals_including_current = history_including_current["release_date"].diff().dt.days.dropna()

        days_since_previous = (current_date - previous_releases.iloc[-1]["release_date"]).days

        avg_interval_so_far = intervals_before_current.mean() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
        median_interval_so_far = (
            intervals_before_current.median() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
        )
        std_interval_so_far = intervals_before_current.std() if len(intervals_before_current) > 1 else 0
        min_interval_so_far = intervals_before_current.min() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
        max_interval_so_far = intervals_before_current.max() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS

        # Rolling interval features (last few observed intervals).
        last_interval_1 = days_since_previous
        last_interval_2 = float(intervals_including_current.iloc[-2]) if len(intervals_including_current) >= 2 else DEFAULT_INTERVAL_DAYS
        last_interval_3 = float(intervals_including_current.iloc[-3]) if len(intervals_including_current) >= 3 else DEFAULT_INTERVAL_DAYS
        avg_last_3_intervals = (
            float(intervals_including_current.iloc[-3:].mean()) if len(intervals_including_current) > 0 else DEFAULT_INTERVAL_DAYS
        )
        median_last_3_intervals = (
            float(intervals_including_current.iloc[-3:].median()) if len(intervals_including_current) > 0 else DEFAULT_INTERVAL_DAYS
        )
        std_last_5_intervals = (
            float(intervals_including_current.iloc[-5:].std()) if len(intervals_including_current) >= 3 else 0
        )

        ema_alpha = 0.3
        ema_interval = None
        for v in intervals_including_current.tolist():
            if ema_interval is None:
                ema_interval = float(v)
            else:
                ema_interval = float(ema_alpha * v + (1 - ema_alpha) * ema_interval)
        if ema_interval is None:
            ema_interval = float(DEFAULT_INTERVAL_DAYS)

        # Solo-related features (based on parent group).
        recent_solos_6m = 0
        recent_solos_1y = 0
        recent_solos_2y = 0
        recent_solo_30d = 0
        days_since_last_solo = 9999
        solo_frequency = 0
        if not solo_releases.empty and "release_date" in solo_releases.columns:
            six_months_ago = current_date - pd.DateOffset(months=6)
            one_year_ago = current_date - pd.DateOffset(months=12)
            two_years_ago = current_date - pd.DateOffset(months=24)
            thirty_days_ago = current_date - pd.DateOffset(days=30)
            recent_solos_6m = len(
                solo_releases[
                    (solo_releases["release_date"] >= six_months_ago)
                    & (solo_releases["release_date"] < current_date)
                ]
            )
            recent_solos_1y = len(
                solo_releases[
                    (solo_releases["release_date"] >= one_year_ago)
                    & (solo_releases["release_date"] < current_date)
                ]
            )
            recent_solos_2y = len(
                solo_releases[
                    (solo_releases["release_date"] >= two_years_ago)
                    & (solo_releases["release_date"] < current_date)
                ]
            )
            previous_solos = solo_releases[solo_releases["release_date"] < current_date]
            days_since_last_solo = (
                (current_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
            )
            total_solos_before = len(previous_solos)
            years_since_debut = (current_date - df_sorted.iloc[0]["release_date"]).days / 365.25
            solo_frequency = total_solos_before / max(years_since_debut, 0.1)
            recent_solo_30d = len(
                solo_releases[
                    (solo_releases["release_date"] >= thirty_days_ago)
                    & (solo_releases["release_date"] < current_date)
                ]
            )

        intervals_for_trend = intervals_including_current.iloc[-5:].values
        if len(intervals_for_trend) >= 3:
            slope = float(np.polyfit(range(len(intervals_for_trend)), intervals_for_trend, 1)[0])
            interval_trend_5 = slope / max(float(avg_interval_so_far), 1.0)
        else:
            interval_trend_5 = 0.0

        prev_release = previous_releases.iloc[-1]
        last_type_encoded = stable_hash_int(str(prev_release["type"]), 10)
        type_changed = int(str(current_release["type"]) != str(prev_release["type"]))

        track_count_val = int(current_release["track_count"]) if "track_count" in current_release.index else 0
        track_count_log = float(np.log1p(track_count_val))

        release_label = str(current_release["label"]).strip() if "label" in current_release.index and str(current_release["label"]).strip() not in ("", "nan") else None
        effective_company = release_label if release_label else (company if company is not None else "Unknown")

        day_of_year = int(current_date.dayofyear)
        day_sin = float(np.sin(2 * np.pi * day_of_year / 366.0))
        day_cos = float(np.cos(2 * np.pi * day_of_year / 366.0))

        days_to_awards = days_to_next_award_show(current_date)
        award_run_up = int(days_to_awards <= 75)

        feature_dict = {
            "group": group_key,
            "generation": generation,
            "company": company,
            "release_type": current_release["type"],
            "release_number": i,
            # The "as-of" date for this row's features (used for time-based evaluation splits).
            "as_of_date": pd.Timestamp(current_date),
            "days_since_debut": (current_date - df_sorted.iloc[0]["release_date"]).days,
            "days_since_previous": days_since_previous,
            "avg_interval_so_far": float(avg_interval_so_far),
            "median_interval_so_far": float(median_interval_so_far),
            "std_interval_so_far": float(std_interval_so_far),
            "interval_cv": float(std_interval_so_far / avg_interval_so_far) if avg_interval_so_far > 0 else 0.0,
            "ema_interval_so_far": float(ema_interval),
            "avg_last_3_intervals": float(avg_last_3_intervals),
            "median_last_3_intervals": float(median_last_3_intervals),
            "std_last_5_intervals": float(std_last_5_intervals),
            "releases_this_year": len(
                previous_releases[previous_releases["release_date"].dt.year == current_date.year]
            ),
            "releases_last_year": len(
                previous_releases[previous_releases["release_date"].dt.year == current_date.year - 1]
            ),
            "day_sin": day_sin,
            "day_cos": day_cos,
            "comeback_season": int(int(current_date.month) in {1, 2, 3, 7, 8, 9}),
            "days_since_previous_norm": float(days_since_previous) / max(float(avg_interval_so_far), 1.0),
            "release_acceleration": float(avg_last_3_intervals) / max(float(avg_interval_so_far), 1.0),
            "members_in_military": members_in_military_at(parent_group_key, current_date),
            "recent_solos_6m": int(recent_solos_6m),
            "recent_solo_30d": int(recent_solo_30d),
            "days_since_last_solo": float(days_since_last_solo),
            "solo_frequency": float(solo_frequency),
            "interval_trend_5": interval_trend_5,
            "last_type_encoded": last_type_encoded,
            "type_changed": type_changed,
            "track_count_log": track_count_log,
            "release_label": effective_company,
            "days_to_awards": days_to_awards,
            "award_run_up": award_run_up,
            "target_days": float(target_days),
        }
        features.append(feature_dict)

    return features


def prepare_training_data(data_by_group: Dict[str, pd.DataFrame], cutoff: date) -> pd.DataFrame:
    all_features: List[Dict] = []
    for group, df in data_by_group.items():
        features = extract_features_from_group(df, group, cutoff, data_by_group)
        all_features.extend(features)
    if not all_features:
        return pd.DataFrame()
    df_features = pd.DataFrame(all_features)
    # Stable categorical encodings so training and inference match.
    df_features["group_encoded"] = df_features["group"].apply(lambda v: stable_hash_int(str(v), 1000))
    df_features["type_encoded"] = df_features["release_type"].apply(lambda v: stable_hash_int(str(v), 10))
    df_features["company_encoded"] = (
        df_features["release_label"].fillna("Unknown").apply(lambda v: stable_hash_int(str(v), 100))
    )
    # Train on log-scale to reduce skew from very long/short intervals.
    df_features["target_days_log"] = np.log1p(df_features["target_days"])
    return df_features


def train_lightgbm_quantile_models(
    df_train: pd.DataFrame,
    quantiles: List[float] = [0.1, 0.5, 0.9],
) -> Dict[float, lgb.LGBMRegressor]:
    feature_cols = [
        "group_encoded", "generation", "type_encoded", "company_encoded",
        "release_number", "days_since_debut", "days_since_previous",
        "avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
        "interval_cv",
        "ema_interval_so_far", "avg_last_3_intervals", "median_last_3_intervals",
        "std_last_5_intervals",
        "releases_this_year", "releases_last_year",
        "day_sin", "day_cos",
        "comeback_season", "days_since_previous_norm", "release_acceleration",
        "members_in_military",
        "recent_solos_6m",
        "recent_solo_30d", "days_since_last_solo", "solo_frequency",
        "interval_trend_5", "last_type_encoded", "type_changed",
        "track_count_log",
        "days_to_awards", "award_run_up",
    ]
    X = df_train[feature_cols]
    Y = df_train["target_days_log"]

    # Temporal split for early stopping: latest 15% of the date range → val set.
    dates = pd.to_datetime(df_train["as_of_date"])
    date_min, date_max = dates.min(), dates.max()
    val_threshold = date_min + (date_max - date_min) * 0.85
    val_mask = dates >= val_threshold
    X_tr, Y_tr = X[~val_mask], Y[~val_mask]
    X_val, Y_val = X[val_mask], Y[val_mask]

    params_base = {
        "objective": "quantile",
        "metric": "mae",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 10,
        "lambda_l1": 0.1,
        "lambda_l2": 0.1,
        "verbose": -1,
        "random_state": 42,
        "n_estimators": 500,
    }

    models: Dict[float, lgb.LGBMRegressor] = {}
    for q in quantiles:
        params = {**params_base, "alpha": q}
        # Phase 1: find best n_estimators via early stopping on val set.
        probe = lgb.LGBMRegressor(**params)
        probe.fit(
            X_tr, Y_tr,
            eval_set=[(X_val, Y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
        )
        best_n = probe.best_iteration_ or params["n_estimators"]
        # Phase 2: refit on full data with the found n_estimators.
        final = lgb.LGBMRegressor(**{**params, "n_estimators": best_n})
        final.fit(X, Y)
        models[q] = final

    return models


def predict_next_release_lightgbm_interval(
    df_group: pd.DataFrame,
    models: Dict[float, lgb.LGBMRegressor],
    group_key: str,
    cutoff: date,
    min_prediction_date: date,
    all_releases: Dict[str, pd.DataFrame],
) -> Optional[Dict[str, object]]:
    """
    Predicts the *next release date interval* using quantile regression.

    Returns a dict with low/median/high dates (and their implied day counts).
    """
    cutoff_dt = pd.Timestamp(cutoff)
    min_prediction_dt = pd.Timestamp(min_prediction_date)

    df_cut = df_group[df_group["release_date"] <= cutoff_dt].sort_values("release_date").reset_index(drop=True)
    if len(df_cut) < 2:
        return None

    last_release = df_cut.iloc[-1]
    last_date = last_release["release_date"]
    previous_releases = df_cut.iloc[:-1]

    parent_group_key = SANITIZED_SOLOISTS.get(group_key, group_key)
    generation = SANITIZED_GENERATION_MAPPINGS.get(parent_group_key, 0)
    company = SANITIZED_GROUP_COMPANIES.get(parent_group_key, None)

    solo_releases = get_solo_releases_for_group(parent_group_key, all_releases)

    recent_solos_6m = 0
    recent_solos_1y = 0
    recent_solos_2y = 0
    recent_solo_30d = 0
    days_since_last_solo = 9999
    solo_frequency = 0
    if not solo_releases.empty and "release_date" in solo_releases.columns:
        six_months_ago = last_date - pd.DateOffset(months=6)
        one_year_ago = last_date - pd.DateOffset(months=12)
        two_years_ago = last_date - pd.DateOffset(months=24)
        thirty_days_ago = last_date - pd.DateOffset(days=30)

        recent_solos_6m = len(
            solo_releases[
                (solo_releases["release_date"] >= six_months_ago) & (solo_releases["release_date"] < last_date)
            ]
        )
        recent_solos_1y = len(
            solo_releases[
                (solo_releases["release_date"] >= one_year_ago) & (solo_releases["release_date"] < last_date)
            ]
        )
        recent_solos_2y = len(
            solo_releases[
                (solo_releases["release_date"] >= two_years_ago) & (solo_releases["release_date"] < last_date)
            ]
        )
        recent_solo_30d = len(
            solo_releases[
                (solo_releases["release_date"] >= thirty_days_ago) & (solo_releases["release_date"] < last_date)
            ]
        )

        previous_solos = solo_releases[solo_releases["release_date"] < last_date]
        days_since_last_solo = (
            (last_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
        )
        total_solos_before = len(previous_solos)
        years_since_debut = (last_date - df_cut.iloc[0]["release_date"]).days / 365.25
        solo_frequency = total_solos_before / max(years_since_debut, 0.1)

    intervals_before_current = previous_releases["release_date"].diff().dt.days.dropna()
    intervals_including_current = df_cut["release_date"].diff().dt.days.dropna()

    days_since_previous = (last_date - previous_releases.iloc[-1]["release_date"]).days

    avg_interval_so_far = intervals_before_current.mean() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
    median_interval_so_far = (
        intervals_before_current.median() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
    )
    std_interval_so_far = intervals_before_current.std() if len(intervals_before_current) > 1 else 0
    min_interval_so_far = intervals_before_current.min() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS
    max_interval_so_far = intervals_before_current.max() if len(intervals_before_current) > 0 else DEFAULT_INTERVAL_DAYS

    avg_last_3_intervals = (
        float(intervals_including_current.iloc[-3:].mean()) if len(intervals_including_current) > 0 else DEFAULT_INTERVAL_DAYS
    )
    median_last_3_intervals = (
        float(intervals_including_current.iloc[-3:].median()) if len(intervals_including_current) > 0 else DEFAULT_INTERVAL_DAYS
    )
    std_last_5_intervals = (
        float(intervals_including_current.iloc[-5:].std()) if len(intervals_including_current) >= 3 else 0
    )
    last_interval_2 = float(intervals_including_current.iloc[-2]) if len(intervals_including_current) >= 2 else DEFAULT_INTERVAL_DAYS
    last_interval_3 = float(intervals_including_current.iloc[-3]) if len(intervals_including_current) >= 3 else DEFAULT_INTERVAL_DAYS

    ema_alpha = 0.3
    ema_interval = None
    for v in intervals_including_current.tolist():
        if ema_interval is None:
            ema_interval = float(v)
        else:
            ema_interval = float(ema_alpha * v + (1 - ema_alpha) * ema_interval)
    if ema_interval is None:
        ema_interval = float(DEFAULT_INTERVAL_DAYS)

    releases_this_year = len(previous_releases[previous_releases["release_date"].dt.year == last_date.year])
    releases_last_year = len(previous_releases[previous_releases["release_date"].dt.year == last_date.year - 1])

    intervals_for_trend = intervals_including_current.iloc[-5:].values
    if len(intervals_for_trend) >= 3:
        slope = float(np.polyfit(range(len(intervals_for_trend)), intervals_for_trend, 1)[0])
        interval_trend_5 = slope / max(float(avg_interval_so_far), 1.0)
    else:
        interval_trend_5 = 0.0

    second_last_release = df_cut.iloc[-2] if len(df_cut) >= 2 else last_release
    last_type_encoded = stable_hash_int(str(second_last_release["type"]), 10)
    type_changed = int(str(last_release["type"]) != str(second_last_release["type"]))

    track_count_val = int(last_release["track_count"]) if "track_count" in last_release.index else 0
    track_count_log = float(np.log1p(track_count_val))

    release_label = str(last_release["label"]).strip() if "label" in last_release.index and str(last_release["label"]).strip() not in ("", "nan") else None
    effective_company = release_label if release_label else (company if company is not None else "Unknown")

    day_of_year = int(last_date.dayofyear)
    day_sin = float(np.sin(2 * np.pi * day_of_year / 366.0))
    day_cos = float(np.cos(2 * np.pi * day_of_year / 366.0))

    days_to_awards = days_to_next_award_show(last_date)
    award_run_up = int(days_to_awards <= 75)

    feature_cols = [
        "group_encoded",
        "generation",
        "type_encoded",
        "company_encoded",
        "release_number",
        "days_since_debut",
        "days_since_previous",
        "avg_interval_so_far",
        "median_interval_so_far",
        "std_interval_so_far",
        "interval_cv",
        "ema_interval_so_far",
        "avg_last_3_intervals",
        "median_last_3_intervals",
        "std_last_5_intervals",
        "releases_this_year",
        "releases_last_year",
        "day_sin",
        "day_cos",
        "comeback_season",
        "days_since_previous_norm",
        "release_acceleration",
        "members_in_military",
        "recent_solos_6m",
        "recent_solo_30d",
        "days_since_last_solo",
        "solo_frequency",
        "interval_trend_5",
        "last_type_encoded",
        "type_changed",
        "track_count_log",
        "days_to_awards",
        "award_run_up",
    ]

    interval_cv = float(std_interval_so_far / avg_interval_so_far) if avg_interval_so_far > 0 else 0.0

    feature_dict = {
        "group_encoded": stable_hash_int(str(group_key), 1000),
        "generation": generation,
        "type_encoded": stable_hash_int(str(last_release["type"]), 10),
        "company_encoded": stable_hash_int(effective_company, 100),
        "release_number": int(len(df_cut) - 1),
        "days_since_debut": (last_date - df_cut.iloc[0]["release_date"]).days,
        "days_since_previous": float(days_since_previous),
        "avg_interval_so_far": float(avg_interval_so_far),
        "median_interval_so_far": float(median_interval_so_far),
        "std_interval_so_far": float(std_interval_so_far),
        "interval_cv": interval_cv,
        "ema_interval_so_far": float(ema_interval),
        "avg_last_3_intervals": float(avg_last_3_intervals),
        "median_last_3_intervals": float(median_last_3_intervals),
        "std_last_5_intervals": float(std_last_5_intervals),
        "releases_this_year": float(releases_this_year),
        "releases_last_year": float(releases_last_year),
        "day_sin": float(day_sin),
        "day_cos": float(day_cos),
        "comeback_season": int(int(last_date.month) in {1, 2, 3, 7, 8, 9}),
        "days_since_previous_norm": float(days_since_previous) / max(float(avg_interval_so_far), 1.0),
        "release_acceleration": float(avg_last_3_intervals) / max(float(avg_interval_so_far), 1.0),
        "members_in_military": members_in_military_at(parent_group_key, last_date),
        "recent_solos_6m": float(recent_solos_6m),
        "recent_solo_30d": float(recent_solo_30d),
        "days_since_last_solo": float(days_since_last_solo),
        "solo_frequency": float(solo_frequency),
        "interval_trend_5": interval_trend_5,
        "last_type_encoded": last_type_encoded,
        "type_changed": type_changed,
        "track_count_log": track_count_log,
        "days_to_awards": days_to_awards,
        "award_run_up": award_run_up,
    }

    X_pred = pd.DataFrame([feature_dict], columns=feature_cols)

    def pred_days_from_log(pred_log: float, round_mode: str) -> int:
        pred_days_float = float(np.expm1(pred_log))
        pred_days_float = max(0.0, pred_days_float)
        if round_mode == "floor":
            return max(1, int(np.floor(pred_days_float)))
        if round_mode == "ceil":
            return max(1, int(np.ceil(pred_days_float)))
        return max(1, int(np.round(pred_days_float)))

    quantiles = sorted(models.keys())
    q10 = 0.1 if 0.1 in models else quantiles[0]
    q50 = 0.5 if 0.5 in models else min(quantiles, key=lambda x: abs(x - 0.5))
    q90 = 0.9 if 0.9 in models else quantiles[-1]

    pred_log_10 = float(models[q10].predict(X_pred)[0])
    pred_log_50 = float(models[q50].predict(X_pred)[0])
    pred_log_90 = float(models[q90].predict(X_pred)[0])

    pred_days_10 = pred_days_from_log(pred_log_10, "floor")
    pred_days_50 = pred_days_from_log(pred_log_50, "round")
    pred_days_90 = pred_days_from_log(pred_log_90, "ceil")

    # Enforce ordering on the implied intervals.
    pred_days_10 = min(pred_days_10, pred_days_50)
    pred_days_90 = max(pred_days_90, pred_days_50)

    pred_date_10_raw = last_date + timedelta(days=pred_days_10)
    pred_date_50_raw = last_date + timedelta(days=pred_days_50)
    pred_date_90_raw = last_date + timedelta(days=pred_days_90)

    # Advance all three quantiles by the same number of p50-cycles so they clear
    # min_prediction_dt. Using a shared cycle count (anchored on p50) prevents the
    # independent-loop approach from landing two quantiles on the same date.
    if pred_date_50_raw < min_prediction_dt:
        cycles = math.ceil((min_prediction_dt - pred_date_50_raw).days / pred_days_50)
    else:
        cycles = 0

    pred_date_10 = pred_date_10_raw + timedelta(days=cycles * pred_days_10)
    pred_date_50 = pred_date_50_raw + timedelta(days=cycles * pred_days_50)
    pred_date_90 = pred_date_90_raw + timedelta(days=cycles * pred_days_90)

    # p10 may still be before min_prediction_dt when pred_days_10 << pred_days_50; clamp it.
    pred_date_10 = max(pred_date_10, min_prediction_dt)

    # Single authoritative sort: keep (date, days) pairs together so both fields are
    # consistent regardless of quantile model inversion, cycling edge cases, or the
    # min_prediction_dt clamp shifting p10's date independently of its day count.
    pairs = sorted(
        [
            (pred_date_10, pred_days_10),
            (pred_date_50, pred_days_50),
            (pred_date_90, pred_days_90),
        ],
        key=lambda x: x[0],
    )
    pred_date_low,  pred_days_low  = pairs[0]
    pred_date_med,  pred_days_med  = pairs[1]
    pred_date_high, pred_days_high = pairs[2]

    return {
        "pred_date_low": pred_date_low,
        "pred_date_med": pred_date_med,
        "pred_date_high": pred_date_high,
        "pred_days_low": pred_days_low,
        "pred_days_med": pred_days_med,
        "pred_days_high": pred_days_high,
    }


def compute_data_signature(albums_dir: str) -> str:
    """Create a signature based on CSV filenames and mtimes to key the cache."""
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
    """Load simple historical error stats from versions/*/predictions.csv if available.

    Returns a dict like {mae_days: float, mape_pct: float} aggregated across versions.
    """
    version_dirs = [
        os.path.join(ROOT_DIR, "versions", d)
        for d in os.listdir(os.path.join(ROOT_DIR, "versions"))
        if os.path.isdir(os.path.join(ROOT_DIR, "versions", d))
    ] if os.path.exists(os.path.join(ROOT_DIR, "versions")) else []
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
        if 'group' not in df.columns:
            continue
        sub = df[df['group'] == group_name]
        if sub.empty:
            continue
        if 'error_days' in sub.columns and sub['error_days'].notna().any():
            maes.extend(sub['error_days'].dropna().astype(float).tolist())
        if 'error_pct' in sub.columns and sub['error_pct'].notna().any():
            mapes.extend(sub['error_pct'].dropna().astype(float).tolist())
    if not maes and not mapes:
        return None
    out: Dict[str, float] = {}
    if maes:
        out["mae_days"] = float(pd.Series(maes).mean())
    if mapes:
        out["mape_pct"] = float(pd.Series(mapes).mean())
    return out


