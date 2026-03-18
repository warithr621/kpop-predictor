from __future__ import annotations

import glob
import hashlib
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

from info import GENERATION_MAPPINGS, KPOP_GROUPS, SOLOISTS, GROUP_COMPANIES


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

        day_of_year = int(current_date.dayofyear)
        day_sin = float(np.sin(2 * np.pi * day_of_year / 366.0))
        day_cos = float(np.cos(2 * np.pi * day_of_year / 366.0))

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
            "min_interval_so_far": float(min_interval_so_far),
            "max_interval_so_far": float(max_interval_so_far),
            "ema_interval_so_far": float(ema_interval),
            "avg_last_3_intervals": float(avg_last_3_intervals),
            "median_last_3_intervals": float(median_last_3_intervals),
            "last_interval_2": float(last_interval_2),
            "last_interval_3": float(last_interval_3),
            "std_last_5_intervals": float(std_last_5_intervals),
            "releases_this_year": len(
                previous_releases[previous_releases["release_date"].dt.year == current_date.year]
            ),
            "releases_last_year": len(
                previous_releases[previous_releases["release_date"].dt.year == current_date.year - 1]
            ),
            "month": int(current_date.month),
            "quarter": int((current_date.month - 1) // 3 + 1),
            "day_sin": day_sin,
            "day_cos": day_cos,
            "recent_solos_6m": int(recent_solos_6m),
            "recent_solos_1y": int(recent_solos_1y),
            "recent_solos_2y": int(recent_solos_2y),
            "recent_solo_30d": int(recent_solo_30d),
            "days_since_last_solo": float(days_since_last_solo),
            "solo_frequency": float(solo_frequency),
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
        df_features["company"].fillna("Unknown").apply(lambda v: stable_hash_int(str(v), 100))
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
        "min_interval_so_far", "max_interval_so_far",
        "ema_interval_so_far", "avg_last_3_intervals", "median_last_3_intervals",
        "last_interval_2", "last_interval_3", "std_last_5_intervals",
        "releases_this_year", "releases_last_year",
        "month", "quarter", "day_sin", "day_cos",
        "recent_solos_6m", "recent_solos_1y", "recent_solos_2y",
        "recent_solo_30d", "days_since_last_solo", "solo_frequency"
    ]
    X = df_train[feature_cols]
    Y = df_train["target_days_log"]

    models: Dict[float, lgb.LGBMRegressor] = {}
    for q in quantiles:
        params = {
            "objective": "quantile",
            "alpha": q,
            "metric": "mae",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "random_state": 42,
            "n_estimators": 300,
        }
        model = lgb.LGBMRegressor(**params)
        model.fit(X, Y)
        models[q] = model

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

    day_of_year = int(last_date.dayofyear)
    day_sin = float(np.sin(2 * np.pi * day_of_year / 366.0))
    day_cos = float(np.cos(2 * np.pi * day_of_year / 366.0))

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
        "min_interval_so_far",
        "max_interval_so_far",
        "ema_interval_so_far",
        "avg_last_3_intervals",
        "median_last_3_intervals",
        "last_interval_2",
        "last_interval_3",
        "std_last_5_intervals",
        "releases_this_year",
        "releases_last_year",
        "month",
        "quarter",
        "day_sin",
        "day_cos",
        "recent_solos_6m",
        "recent_solos_1y",
        "recent_solos_2y",
        "recent_solo_30d",
        "days_since_last_solo",
        "solo_frequency",
    ]

    feature_dict = {
        "group_encoded": stable_hash_int(str(group_key), 1000),
        "generation": generation,
        "type_encoded": stable_hash_int(str(last_release["type"]), 10),
        "company_encoded": stable_hash_int(str(company if company is not None else "Unknown"), 100),
        "release_number": int(len(df_cut) - 1),
        "days_since_debut": (last_date - df_cut.iloc[0]["release_date"]).days,
        "days_since_previous": float(days_since_previous),
        "avg_interval_so_far": float(avg_interval_so_far),
        "median_interval_so_far": float(median_interval_so_far),
        "std_interval_so_far": float(std_interval_so_far),
        "min_interval_so_far": float(min_interval_so_far),
        "max_interval_so_far": float(max_interval_so_far),
        "ema_interval_so_far": float(ema_interval),
        "avg_last_3_intervals": float(avg_last_3_intervals),
        "median_last_3_intervals": float(median_last_3_intervals),
        "last_interval_2": float(last_interval_2),
        "last_interval_3": float(last_interval_3),
        "std_last_5_intervals": float(std_last_5_intervals),
        "releases_this_year": float(releases_this_year),
        "releases_last_year": float(releases_last_year),
        "month": int(last_date.month),
        "quarter": int((last_date.month - 1) // 3 + 1),
        "day_sin": float(day_sin),
        "day_cos": float(day_cos),
        "recent_solos_6m": float(recent_solos_6m),
        "recent_solos_1y": float(recent_solos_1y),
        "recent_solos_2y": float(recent_solos_2y),
        "recent_solo_30d": float(recent_solo_30d),
        "days_since_last_solo": float(days_since_last_solo),
        "solo_frequency": float(solo_frequency),
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

    def shift_date(date_value: date, step_days: int) -> date:
        while date_value < min_prediction_dt:
            date_value = date_value + timedelta(days=step_days)
        return date_value

    pred_log_10 = float(models[q10].predict(X_pred)[0])
    pred_log_50 = float(models[q50].predict(X_pred)[0])
    pred_log_90 = float(models[q90].predict(X_pred)[0])

    pred_days_10 = pred_days_from_log(pred_log_10, "floor")
    pred_days_50 = pred_days_from_log(pred_log_50, "round")
    pred_days_90 = pred_days_from_log(pred_log_90, "ceil")

    # Enforce ordering on the implied intervals.
    pred_days_10 = min(pred_days_10, pred_days_50)
    pred_days_90 = max(pred_days_90, pred_days_50)

    pred_date_10 = shift_date(last_date + timedelta(days=pred_days_10), pred_days_10)
    pred_date_50 = shift_date(last_date + timedelta(days=pred_days_50), pred_days_50)
    pred_date_90 = shift_date(last_date + timedelta(days=pred_days_90), pred_days_90)

    # Enforce ordering on the dates as well.
    pred_date_low = min(pred_date_10, pred_date_50)
    pred_date_high = max(pred_date_90, pred_date_50)

    return {
        "pred_date_low": pred_date_low,
        "pred_date_med": pred_date_50,
        "pred_date_high": pred_date_high,
        "pred_days_low": pred_days_10,
        "pred_days_med": pred_days_50,
        "pred_days_high": pred_days_90,
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


