"""
Evaluation suite for the K-pop release predictor.

Trains on full data, withholds each group's most recent release. Matches the numbers reported in the project readme.

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
    train_weibull_aft_model,
    predict_next_release_weibull_interval,
    get_current_cutoff_dates,
)
from info import KPOP_GROUPS, GENERATION_MAPPINGS


SHORTLIST = [
    "aespa", "ATEEZ", "BABYMONSTER", "ENHYPEN", "Hearts2Hearts",
    "i-dle", "ILLIT", "ITZY", "IVE", "KISS OF LIFE",
    "LE SSERAFIM", "MEOVV", "NMIXX", "RIIZE", "STAYC",
    "Stray Kids", "TREASURE", "TXT",
]

SHORTLIST_4TH = [g for g in SHORTLIST if GENERATION_MAPPINGS.get(g) == 4]
SHORTLIST_5TH = [g for g in SHORTLIST if GENERATION_MAPPINGS.get(g) == 5]

WEEK_THRESHOLDS = [6, 8, 12, 18, 24]

ALL_GROUPS = [g for gen in KPOP_GROUPS.values() for g in gen]


def to_date(x):
    if hasattr(x, "date"):
        return x.date()
    return x


def run_leave_last_out():
    print("Loading all releases...")
    data_by_group = load_all_releases(ALBUMS_DIR, exclude_predebut_mixtape=True)

    # Train a global model using today's cutoff (full data)
    current_cutoff, _ = get_current_cutoff_dates()
    print(f"Training model with cutoff {current_cutoff}...")
    df_train = prepare_training_data(data_by_group, current_cutoff)
    model = train_weibull_aft_model(df_train)
    print(f"Weibull AFT trained on {len(df_train)} rows.\n")

    results = []
    for group in ALL_GROUPS:
        if GENERATION_MAPPINGS.get(group) == 3:
            continue
        group_key = sanitize(group)
        df_group = data_by_group.get(group_key)
        if df_group is None or df_group.empty:
            continue

        last_date = pd.to_datetime(df_group["release_date"]).max().date()
        cutoff = last_date - timedelta(days=1)

        pred = predict_next_release_weibull_interval(
            df_group=df_group,
            model=model,
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

        results.append({
            "group": group,
            "actual": last_date,
            "pred_med": pred_med,
            "pred_low": pred_low,
            "pred_high": pred_high,
            "error_days": error_days,
            "signed_days": signed_days
        })

    df = pd.DataFrame(results)

    def window_acc(errors, weeks):
        return 100.0 * np.mean(errors <= weeks * 7)

    def interval_coverage(subset):
        in_interval = (subset["actual"] >= subset["pred_low"]) & (subset["actual"] <= subset["pred_high"])
        return 100.0 * in_interval.mean()

    def print_stats(label, subset):
        errs = subset["error_days"].values
        signed = subset["signed_days"].values
        coverage = interval_coverage(subset)
        print(f"\n{'='*60}")
        print(f"  {label}  (n={len(subset)})")
        print(f"{'='*60}")
        print(f"  Median absolute error : {np.median(errs):.1f} days")
        print(f"  Mean absolute error   : {np.mean(errs):.1f} days")
        print(f"  Bias (median signed)  : {np.median(signed):+.1f} days")
        print(f"  Interval coverage     : {coverage:.1f}%  (target ~50%)")
        print()
        for w in WEEK_THRESHOLDS:
            print(f"  Within ±{w:2d} weeks       : {window_acc(errs, w):.1f}%")

    df_4th_5th = df[df["group"].apply(lambda g: GENERATION_MAPPINGS.get(g) in {4, 5})].copy()
    print_stats("ALL GROUPS", df_4th_5th)
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

    # Calibration summary
    df["pred_days_med"] = df.apply(lambda r: (r["pred_med"] - r["actual"]).days + r["error_days"]
                                    if r["signed_days"] >= 0
                                    else r["error_days"] - (r["actual"] - r["pred_med"]).days, axis=1)
    df["half_spread"] = df.apply(
        lambda r: ((r["pred_high"] - r["pred_low"]).days / 2.0), axis=1
    )
    df["dist_to_med"] = df["error_days"].astype(float)
    valid = df[df["half_spread"] > 0]
    ratios = valid["dist_to_med"] / valid["half_spread"]
    multiplier = float(np.median(ratios))

    print(f"\n{'='*60}")
    print(f"  CALIBRATION — p25/p75 interval coverage")
    print(f"{'='*60}")
    print(f"  All 4th+5th gen : {interval_coverage(df_4th_5th):.1f}%  (target ~50%)")
    print(f"  Shortlist       : {interval_coverage(shortlist_df):.1f}%")
    print(f"  4th Gen only    : {interval_coverage(df4):.1f}%")
    print(f"  5th Gen only    : {interval_coverage(df5):.1f}%")
    print(f"\n  Spread multiplier to hit ~50% coverage: ~{multiplier:.2f}x")
    print(f"  (multiplier = median(|actual−med| / half_spread) across all groups)")
    print(f"{'='*60}")

    return df


if __name__ == "__main__":
    run_leave_last_out()
