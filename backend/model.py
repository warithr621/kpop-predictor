from __future__ import annotations

import glob
import hashlib
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import lightgbm as lgb
import pandas as pd
from sklearn.preprocessing import LabelEncoder

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


def get_solo_releases_for_group(group: str, all_releases: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    solo_releases = []
    for soloist, soloist_group in SOLOISTS.items():
        if soloist_group == group:
            soloist_sanitized = sanitize(soloist)
            if soloist_sanitized in all_releases:
                solo_df = all_releases[soloist_sanitized].copy()
                solo_df['soloist'] = soloist
                solo_releases.append(solo_df)
    if solo_releases:
        combined = pd.concat(solo_releases, ignore_index=True)
        combined = combined.sort_values('release_date').reset_index(drop=True)
        return combined
    return pd.DataFrame()


def extract_features_from_group(df: pd.DataFrame, group: str, cutoff: date, all_releases: Dict[str, pd.DataFrame]) -> List[Dict]:
    features: List[Dict] = []
    generation = GENERATION_MAPPINGS.get(group, 0)
    company = GROUP_COMPANIES.get(group, None)
    if group in SOLOISTS:
        parent_group = SOLOISTS[group]
        company = GROUP_COMPANIES.get(parent_group, None)
    cutoff_dt = pd.Timestamp(cutoff)
    df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
    if len(df_sorted) < 2:
        return features
    solo_releases = get_solo_releases_for_group(group, all_releases)
    for i in range(1, len(df_sorted)):
        current_release = df_sorted.iloc[i]
        previous_releases = df_sorted.iloc[:i]
        if i < len(df_sorted) - 1:
            next_release = df_sorted.iloc[i + 1]
            target_days = (next_release["release_date"] - current_release["release_date"]).days
        else:
            continue
        current_date = current_release["release_date"]
        recent_solos_6m = 0
        recent_solos_1y = 0
        recent_solos_2y = 0
        recent_solo_30d = 0
        days_since_last_solo = 9999
        solo_frequency = 0
        if not solo_releases.empty and 'release_date' in solo_releases.columns:
            six_months_ago = current_date - pd.DateOffset(months=6)
            one_year_ago = current_date - pd.DateOffset(months=12)
            two_years_ago = current_date - pd.DateOffset(months=24)
            thirty_days_ago = current_date - pd.DateOffset(days=30)
            recent_solos_6m = len(solo_releases[(solo_releases["release_date"] >= six_months_ago) & (solo_releases["release_date"] < current_date)])
            recent_solos_1y = len(solo_releases[(solo_releases["release_date"] >= one_year_ago) & (solo_releases["release_date"] < current_date)])
            recent_solos_2y = len(solo_releases[(solo_releases["release_date"] >= two_years_ago) & (solo_releases["release_date"] < current_date)])
            previous_solos = solo_releases[solo_releases["release_date"] < current_date]
            days_since_last_solo = (current_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
            total_solos_before = len(previous_solos)
            years_since_debut = (current_date - df_sorted.iloc[0]["release_date"]).days / 365.25
            solo_frequency = total_solos_before / max(years_since_debut, 0.1)
            recent_solo_30d = len(solo_releases[(solo_releases["release_date"] >= thirty_days_ago) & (solo_releases["release_date"] < current_date)])
        feature_dict = {
            "group": group,
            "generation": generation,
            "company": company,
            "release_date": current_release["release_date"],
            "release_type": current_release["type"],
            "release_number": i,
            "days_since_debut": (current_release["release_date"] - df_sorted.iloc[0]["release_date"]).days,
            "days_since_previous": (current_release["release_date"] - previous_releases.iloc[-1]["release_date"]).days,
            "avg_interval_so_far": previous_releases["release_date"].diff().dt.days.mean() if len(previous_releases) > 1 else 0,
            "median_interval_so_far": previous_releases["release_date"].diff().dt.days.median() if len(previous_releases) > 1 else 0,
            "std_interval_so_far": previous_releases["release_date"].diff().dt.days.std() if len(previous_releases) > 2 else 0,
            "min_interval_so_far": previous_releases["release_date"].diff().dt.days.min() if len(previous_releases) > 1 else 0,
            "max_interval_so_far": previous_releases["release_date"].diff().dt.days.max() if len(previous_releases) > 1 else 0,
            "releases_this_year": len(previous_releases[previous_releases["release_date"].dt.year == current_release["release_date"].year]),
            "releases_last_year": len(previous_releases[previous_releases["release_date"].dt.year == current_release["release_date"].year - 1]),
            "month": current_release["release_date"].month,
            "quarter": (current_release["release_date"].month - 1) // 3 + 1,
            "recent_solos_6m": recent_solos_6m,
            "recent_solos_1y": recent_solos_1y,
            "recent_solos_2y": recent_solos_2y,
            "recent_solo_30d": recent_solo_30d,
            "days_since_last_solo": days_since_last_solo,
            "solo_frequency": solo_frequency,
            "target_days": target_days,
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
    le_group = LabelEncoder()
    le_type = LabelEncoder()
    le_company = LabelEncoder()
    df_features["group_encoded"] = le_group.fit_transform(df_features["group"])
    df_features["type_encoded"] = le_type.fit_transform(df_features["release_type"])
    df_features["company_encoded"] = le_company.fit_transform(df_features["company"].fillna("Unknown"))
    return df_features


def train_lightgbm_model(df_train: pd.DataFrame) -> lgb.LGBMRegressor:
    feature_cols = [
        "group_encoded", "generation", "type_encoded", "company_encoded",
        "release_number", "days_since_debut", "days_since_previous",
        "avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
        "min_interval_so_far", "max_interval_so_far",
        "releases_this_year", "releases_last_year",
        "month", "quarter",
        "recent_solos_6m", "recent_solos_1y", "recent_solos_2y",
        "recent_solo_30d", "days_since_last_solo", "solo_frequency"
    ]
    X = df_train[feature_cols]
    Y = df_train["target_days"]
    params = {
        'objective': 'regression',
        'metric': 'mae',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'random_state': 42
    }
    model = lgb.LGBMRegressor(**params)
    model.fit(X, Y)
    return model


def predict_next_release_lightgbm(
    df_group: pd.DataFrame,
    model: lgb.LGBMRegressor,
    group: str,
    cutoff: date,
    min_prediction_date: date,
    all_releases: Dict[str, pd.DataFrame]
) -> Optional[date]:
    if group in SOLOISTS:
        parent_group = SOLOISTS[group]
        company = GROUP_COMPANIES.get(parent_group, "Unknown")
    elif '_' in group and len(group.split('_')) > 1:
        parent_group = group.split('_')[0]
        company = GROUP_COMPANIES.get(parent_group, "Unknown")
    else:
        company = GROUP_COMPANIES.get(group, "Unknown")
    cutoff_dt = pd.Timestamp(cutoff)
    min_prediction_dt = pd.Timestamp(min_prediction_date)
    df_cut = df_group[df_group["release_date"] <= cutoff_dt]
    if df_cut.empty:
        return None
    last_release = df_cut.iloc[-1]
    last_date = last_release["release_date"]
    previous_releases = df_cut.iloc[:-1] if len(df_cut) > 1 else pd.DataFrame()
    generation = GENERATION_MAPPINGS.get(group, 0)
    solo_releases = get_solo_releases_for_group(group, all_releases)
    recent_solos_6m = 0
    recent_solos_1y = 0
    recent_solos_2y = 0
    recent_solo_30d = 0
    days_since_last_solo = 9999
    solo_frequency = 0
    if not solo_releases.empty and 'release_date' in solo_releases.columns:
        six_months_ago = last_date - pd.DateOffset(months=6)
        one_year_ago = last_date - pd.DateOffset(months=12)
        two_years_ago = last_date - pd.DateOffset(months=24)
        thirty_days_ago = last_date - pd.DateOffset(days=30)
        recent_solos_6m = len(solo_releases[(solo_releases["release_date"] >= six_months_ago) & (solo_releases["release_date"] <= last_date)])
        recent_solos_1y = len(solo_releases[(solo_releases["release_date"] >= one_year_ago) & (solo_releases["release_date"] <= last_date)])
        recent_solos_2y = len(solo_releases[(solo_releases["release_date"] >= two_years_ago) & (solo_releases["release_date"] <= last_date)])
        recent_solo_30d = len(solo_releases[(solo_releases["release_date"] >= thirty_days_ago) & (solo_releases["release_date"] <= last_date)])
        previous_solos = solo_releases[solo_releases["release_date"] <= last_date]
        days_since_last_solo = (last_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
        total_solos_before = len(previous_solos)
        years_since_debut = (last_date - df_cut.iloc[0]["release_date"]).days / 365.25
        solo_frequency = total_solos_before / max(years_since_debut, 0.1)
    feature_dict = {
        "group_encoded": hash(group) % 1000,
        "generation": generation,
        "type_encoded": hash(last_release["type"]) % 10,
        "company_encoded": hash(company) % 100,
        "release_number": len(df_cut),
        "days_since_debut": (last_date - df_cut.iloc[0]["release_date"]).days if len(df_cut) > 1 else 0,
        "days_since_previous": (last_date - previous_releases.iloc[-1]["release_date"]).days if len(previous_releases) > 0 else 0,
        "avg_interval_so_far": previous_releases["release_date"].diff().dt.days.mean() if len(previous_releases) > 1 else 120,
        "median_interval_so_far": previous_releases["release_date"].diff().dt.days.median() if len(previous_releases) > 1 else 120,
        "std_interval_so_far": previous_releases["release_date"].diff().dt.days.std() if len(previous_releases) > 2 else 0,
        "min_interval_so_far": previous_releases["release_date"].diff().dt.days.min() if len(previous_releases) > 1 else 120,
        "max_interval_so_far": previous_releases["release_date"].diff().dt.days.max() if len(previous_releases) > 1 else 120,
        "releases_this_year": len(previous_releases[previous_releases["release_date"].dt.year == last_date.year]) if len(previous_releases) > 0 else 0,
        "releases_last_year": len(previous_releases[previous_releases["release_date"].dt.year == last_date.year - 1]) if len(previous_releases) > 0 else 0,
        "month": last_date.month,
        "quarter": (last_date.month - 1) // 3 + 1,
        "recent_solos_6m": recent_solos_6m,
        "recent_solos_1y": recent_solos_1y,
        "recent_solos_2y": recent_solos_2y,
        "recent_solo_30d": recent_solo_30d,
        "days_since_last_solo": days_since_last_solo,
        "solo_frequency": solo_frequency,
    }
    feature_cols = [
        "group_encoded", "generation", "type_encoded", "company_encoded",
        "release_number", "days_since_debut", "days_since_previous",
        "avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
        "min_interval_so_far", "max_interval_so_far",
        "releases_this_year", "releases_last_year",
        "month", "quarter",
        "recent_solos_6m", "recent_solos_1y", "recent_solos_2y",
        "recent_solo_30d", "days_since_last_solo", "solo_frequency"
    ]
    X_pred = pd.DataFrame([feature_dict], columns=feature_cols)
    predicted_days = model.predict(X_pred)[0]
    predicted_days = max(1, int(round(predicted_days)))
    predicted_date = last_date + timedelta(days=predicted_days)
    while predicted_date < min_prediction_dt:
        predicted_date += timedelta(days=predicted_days)
    return predicted_date


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


