"""
Leave-last-out evaluation for the K-pop release predictor.

For each group, withholds the most recent release from the model (cutoff = last_release_date - 1 day),
generates a prediction, then compares pred_date_med to the actual release date.

Prints:
  - Overall stats across all groups
  - Per-group breakdown for 18 shortlisted groups
  - Within-window accuracy at ±6/8/12/18/24 weeks for both sets
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

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
from info import KPOP_GROUPS


SHORTLIST = [
    "Stray Kids", "i-dle", "ATEEZ", "ITZY", "TXT",
    "TREASURE", "STAYC", "aespa", "ENHYPEN", "IVE",
    "NMIXX", "LE SSERAFIM", "KISS OF LIFE", "RIIZE",
    "BABYMONSTER", "MEOVV", "ILLIT", "Hearts2Hearts",
]

WEEK_THRESHOLDS = [6, 8, 12, 18, 24]

ALL_GROUPS = [g for gen in KPOP_GROUPS.values() for g in gen]


def to_date(x):
    if hasattr(x, "date"):
        return x.date()
    return x


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

    # Per-group breakdown for shortlist
    print(f"\n{'='*60}")
    print("  Per-group breakdown (shortlist, sorted by error)")
    print(f"{'='*60}")
    shortlist_sorted = shortlist_df.sort_values("error_days")
    print(f"  {'Group':<22} {'Actual':<12} {'Predicted':<12} {'Error':>8}  {'Direction'}")
    print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*8}  {'-'*9}")
    for _, row in shortlist_sorted.iterrows():
        direction = f"+{row['signed_days']}d" if row['signed_days'] >= 0 else f"{row['signed_days']}d"
        print(f"  {row['group']:<22} {str(row['actual']):<12} {str(row['pred_med']):<12} {row['error_days']:>6}d  {direction}")

    # Window accuracy table for shortlist
    print(f"\n  Average stats across shortlist:")
    print(f"  {'Threshold':<15} {'Accuracy':>10}")
    print(f"  {'-'*15} {'-'*10}")
    for w in WEEK_THRESHOLDS:
        acc = window_acc(shortlist_df["error_days"].values, w)
        print(f"  ±{w:2d} weeks        {acc:>9.1f}%")
    print(f"  Median error   {np.median(shortlist_df['error_days'].values):>9.1f}d")

    return df


if __name__ == "__main__":
    run_leave_last_out()
