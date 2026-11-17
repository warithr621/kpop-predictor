"""
Rolling-origin backtest for the K-pop release predictor.

For each monthly cutoff T:
  1. Train on data known as of T only (training rows whose target release is <= T).
  2. For every 4th/5th gen group, predict the next release exactly as the app does
     in production (cutoff=T, min_prediction_date=T+1).
  3. Score against the first actual release after T.

Groups with no release between T and today are right-censored and excluded from
error metrics (counted separately). Cutoffs stop 6 months before today so most
groups have had time to release.

The model is compared against naive baselines that use no ML at all; if it can't
beat them, the features aren't adding signal.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

ALBUMS_DIR = os.path.join(ROOT_DIR, "albums")

from backend.model import (
    sanitize,
    load_all_releases,
    prepare_training_data,
    train_weibull_aft_model,
    predict_next_release_weibull_interval,
    _apply_cycles_and_sort,
)
from info import KPOP_GROUPS, GENERATION_MAPPINGS

EVAL_GROUPS = [g for gen in KPOP_GROUPS.values() for g in gen if GENERATION_MAPPINGS.get(g) in {4, 5}]
WEEK_THRESHOLDS = [2, 4, 6, 8, 12]
MIN_HORIZON_DAYS = 183

# A predictor factory takes (data_by_group, T) and returns predict(group_key) -> pred dict or None.
PredictorFactory = Callable[[Dict[str, pd.DataFrame], date], Callable[[str], Optional[dict]]]


def monthly_cutoffs(start: date, end: date) -> list[date]:
    return [d.date() for d in pd.date_range(start, end, freq="MS")]


def weibull_factory(data_by_group, T):
    model = train_weibull_aft_model(prepare_training_data(data_by_group, T))

    def predict(group_key):
        return predict_next_release_weibull_interval(
            df_group=data_by_group[group_key], model=model, group_key=group_key,
            cutoff=T, min_prediction_date=T + timedelta(days=1), all_releases=data_by_group,
        )
    return predict


def naive_factory(window: Optional[int]) -> PredictorFactory:
    """Last release + median of the last `window` gaps (all gaps if None); p25/p75 of those gaps as the range."""
    def factory(data_by_group, T):
        def predict(group_key):
            dates = data_by_group[group_key]["release_date"]
            dates = dates[dates <= pd.Timestamp(T)].sort_values()
            if len(dates) < 2:
                return None
            gaps = dates.diff().dt.days.dropna().clip(lower=1)
            if window:
                gaps = gaps.iloc[-window:]
            p25, p50, p75 = (max(1, int(round(np.percentile(gaps, q)))) for q in (25, 50, 75))
            return _apply_cycles_and_sort(dates.iloc[-1], p25, p50, p75, T + timedelta(days=1))
        return predict
    return factory


def run_backtest(factory: PredictorFactory, data_by_group, cutoffs, today: date) -> pd.DataFrame:
    rows = []
    for T in cutoffs:
        predict = factory(data_by_group, T)
        for group in EVAL_GROUPS:
            key = sanitize(group)
            df = data_by_group.get(key)
            if df is None:
                continue
            future = df["release_date"][(df["release_date"] > pd.Timestamp(T)) & (df["release_date"] <= pd.Timestamp(today))]
            pred = predict(key)
            if pred is None:
                continue
            actual = future.min().date() if not future.empty else None
            rows.append({
                "cutoff": T, "group": group, "actual": actual,
                "low": pred["pred_date_low"].date(), "med": pred["pred_date_med"].date(),
                "high": pred["pred_date_high"].date(),
            })
    out = pd.DataFrame(rows)
    obs = out["actual"].notna()
    out.loc[obs, "signed"] = [(m - a).days for m, a in zip(out.loc[obs, "med"], out.loc[obs, "actual"])]
    out["abs_err"] = out["signed"].abs()
    out["covered"] = obs & (out["actual"] >= out["low"]) & (out["actual"] <= out["high"])
    out["width"] = [(h - l).days for h, l in zip(out["high"], out["low"])]
    return out


def summarize(res: pd.DataFrame) -> dict:
    obs = res[res["actual"].notna()]
    s = {
        "n": len(obs),
        "censored": int(res["actual"].isna().sum()),
        "median_err": float(obs["abs_err"].median()),
        "mean_err": float(obs["abs_err"].mean()),
        "bias": float(obs["signed"].median()),
        "coverage": 100.0 * obs["covered"].mean(),
        "width": float(obs["width"].median()),
    }
    for w in WEEK_THRESHOLDS:
        s[f"±{w}w"] = 100.0 * (obs["abs_err"] <= w * 7).mean()
    return s


def compare(factories: Dict[str, PredictorFactory], data_by_group=None, cutoffs=None, today=None) -> pd.DataFrame:
    today = today or date.today()
    data_by_group = data_by_group or load_all_releases(ALBUMS_DIR, exclude_predebut_mixtape=True)
    cutoffs = cutoffs or monthly_cutoffs(date(2024, 7, 1), today - timedelta(days=MIN_HORIZON_DAYS))
    table = {name: summarize(run_backtest(f, data_by_group, cutoffs, today)) for name, f in factories.items()}
    return pd.DataFrame(table).T


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    table = compare({
        "weibull_aft": weibull_factory,
        "naive_last3": naive_factory(3),
        "naive_last6": naive_factory(6),
        "naive_all":   naive_factory(None),
    })
    print("Rolling-origin backtest (monthly cutoffs, 4th/5th gen groups)")
    print("errors in days; coverage/±Nw in %; width = median low→high span in days\n")
    print(table.round(1).to_string())
