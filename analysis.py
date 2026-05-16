"""
Evaluation suite for the K-pop release predictor.

Sections:
  1. Walk-forward CV — trains at 5 historical cutoffs, predicts each group's
     next release, aggregates across all (cutoff, group) pairs. Primary metric
     for detecting overfitting during development.
  2. Leave-last-out — trains on full data, withholds each group's most recent
     release. Matches the numbers reported in the project readme.

Prints within-window accuracy at ±6/8/12/18/24 weeks for both sections.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

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
    train_lightgbm_quantile_models,
    predict_next_release_lightgbm_interval,
    get_current_cutoff_dates,
)
from info import KPOP_GROUPS, GENERATION_MAPPINGS


EVAL_CUTOFFS = [
    date(2023, 1, 1), date(2023, 7, 1),
    date(2024, 1, 1), date(2024, 7, 1),
    date(2025, 1, 1),
]

SHORTLIST = [
    "Stray Kids", "i-dle", "ATEEZ", "ITZY", "TXT",
    "TREASURE", "STAYC", "aespa", "ENHYPEN", "IVE",
    "NMIXX", "LE SSERAFIM", "KISS OF LIFE", "RIIZE",
    "BABYMONSTER", "MEOVV", "ILLIT", "Hearts2Hearts",
]

SHORTLIST_4TH = [g for g in SHORTLIST if GENERATION_MAPPINGS.get(g) == 4]
SHORTLIST_5TH = [g for g in SHORTLIST if GENERATION_MAPPINGS.get(g) == 5]

WEEK_THRESHOLDS = [6, 8, 12, 18, 24]

ALL_GROUPS = [g for gen in KPOP_GROUPS.values() for g in gen]


def to_date(x):
    if hasattr(x, "date"):
        return x.date()
    return x


def walk_forward_cv():
    """Train at each eval cutoff and predict each group's next release."""
    print("=" * 60)
    print("  WALK-FORWARD CROSS-VALIDATION")
    print("=" * 60)
    print(f"  Cutoffs: {[str(c) for c in EVAL_CUTOFFS]}\n")

    data_by_group = load_all_releases(ALBUMS_DIR)

    all_results = []
    for cutoff in EVAL_CUTOFFS:
        df_train = prepare_training_data(data_by_group, cutoff)
        if df_train.empty:
            continue
        models = train_lightgbm_quantile_models(df_train)

        for group in ALL_GROUPS:
            group_key = sanitize(group)
            df_group = data_by_group.get(group_key)
            if df_group is None or df_group.empty:
                continue

            # Need ≥2 releases before cutoff and ≥1 release after cutoff
            cutoff_ts = pd.Timestamp(cutoff)
            before = df_group[df_group["release_date"] <= cutoff_ts]
            after = df_group[df_group["release_date"] > cutoff_ts]
            if len(before) < 2 or len(after) == 0:
                continue

            actual_date = after.iloc[0]["release_date"]
            if hasattr(actual_date, "date"):
                actual_date = actual_date.date()

            pred = predict_next_release_lightgbm_interval(
                df_group=df_group,
                models=models,
                group_key=group_key,
                cutoff=cutoff,
                min_prediction_date=cutoff + timedelta(days=1),
                all_releases=data_by_group,
            )
            if pred is None:
                continue

            pred_med = to_date(pred["pred_date_med"])
            error_days = abs((pred_med - actual_date).days)
            signed_days = (pred_med - actual_date).days

            all_results.append({
                "cutoff": cutoff,
                "group": group,
                "actual": actual_date,
                "pred_med": pred_med,
                "error_days": error_days,
                "signed_days": signed_days,
            })

    df = pd.DataFrame(all_results)
    if df.empty:
        print("  No results — check cutoffs and data.\n")
        return df

    errs = df["error_days"].values
    signed = df["signed_days"].values
    print(f"  Total (cutoff, group) pairs evaluated: {len(df)}")
    print(f"  Median absolute error : {np.median(errs):.1f} days")
    print(f"  Mean absolute error   : {np.mean(errs):.1f} days")
    print(f"  Bias (median signed)  : {np.median(signed):+.1f} days")
    print()
    for w in WEEK_THRESHOLDS:
        acc = 100.0 * np.mean(errs <= w * 7)
        print(f"  Within ±{w:2d} weeks       : {acc:.1f}%")
    print()
    return df


def run_leave_last_out():
    print("Loading all releases...")
    data_by_group = load_all_releases(ALBUMS_DIR)

    # Train a global model using today's cutoff (full data)
    current_cutoff, _ = get_current_cutoff_dates()
    print(f"Training global model with cutoff {current_cutoff}...")
    df_train = prepare_training_data(data_by_group, current_cutoff)
    models = train_lightgbm_quantile_models(df_train)
    print(f"Model trained on {len(df_train)} rows.\n")

    results = []
    for group in ALL_GROUPS:
        group_key = sanitize(group)
        df_group = data_by_group.get(group_key)
        if df_group is None or df_group.empty:
            continue

        last_date = pd.to_datetime(df_group["release_date"]).max().date()
        cutoff = last_date - timedelta(days=1)

        pred = predict_next_release_lightgbm_interval(
            df_group=df_group,
            models=models,
            group_key=group_key,
            cutoff=cutoff,
            min_prediction_date=cutoff + timedelta(days=1),
            all_releases=data_by_group,
        )
        if pred is None:
            continue

        pred_med = to_date(pred["pred_date_med"])
        pred_low = to_date(pred["pred_date_low"])
        pred_high = to_date(pred["pred_date_high"])
        error_days = abs((pred_med - last_date).days)
        signed_days = (pred_med - last_date).days
        in_interval = pred_low <= last_date <= pred_high

        results.append({
            "group": group,
            "actual": last_date,
            "pred_med": pred_med,
            "pred_low": pred_low,
            "pred_high": pred_high,
            "error_days": error_days,
            "signed_days": signed_days,
            "in_interval": in_interval,
        })

    df = pd.DataFrame(results)

    def window_acc(errors, weeks):
        return 100.0 * np.mean(errors <= weeks * 7)

    def print_stats(label, subset):
        errs = subset["error_days"].values
        signed = subset["signed_days"].values
        cov = 100.0 * subset["in_interval"].mean()
        print(f"\n{'='*60}")
        print(f"  {label}  (n={len(subset)})")
        print(f"{'='*60}")
        print(f"  Median absolute error : {np.median(errs):.1f} days")
        print(f"  Mean absolute error   : {np.mean(errs):.1f} days")
        print(f"  Bias (median signed)  : {np.median(signed):+.1f} days")
        print(f"  Interval coverage     : {cov:.1f}%")
        print()
        for w in WEEK_THRESHOLDS:
            print(f"  Within ±{w:2d} weeks       : {window_acc(errs, w):.1f}%")

    print_stats("ALL GROUPS", df)
    print()

    shortlist_df = df[df["group"].isin(SHORTLIST)].copy()
    print_stats("SHORTLIST (18 groups)", shortlist_df)

    def print_breakdown(label, subset_df):
        subset_sorted = subset_df.sort_values("error_days")
        print(f"\n{'='*60}")
        print(f"  {label} — per-group breakdown (sorted by error)")
        print(f"{'='*60}")
        print(f"  {'Group':<22} {'Actual':<12} {'Predicted':<12} {'Error':>8}  {'Direction'}")
        print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*8}  {'-'*9}")
        for _, row in subset_sorted.iterrows():
            direction = f"+{row['signed_days']}d" if row['signed_days'] >= 0 else f"{row['signed_days']}d"
            print(f"  {row['group']:<22} {str(row['actual']):<12} {str(row['pred_med']):<12} {row['error_days']:>6}d  {direction}")
        errs = subset_df["error_days"].values
        print(f"\n  Summary:")
        print(f"  {'Threshold':<15} {'Accuracy':>10}")
        print(f"  {'-'*15} {'-'*10}")
        for w in WEEK_THRESHOLDS:
            acc = window_acc(errs, w)
            print(f"  ±{w:2d} weeks        {acc:>9.1f}%")
        print(f"  Median error   {np.median(errs):>9.1f}d")

    df4 = df[df["group"].isin(SHORTLIST_4TH)].copy()
    df5 = df[df["group"].isin(SHORTLIST_5TH)].copy()
    print_breakdown("4th Gen", df4)
    print_breakdown("5th Gen", df5)

    return df


if __name__ == "__main__":
    walk_forward_cv()
    run_leave_last_out()
