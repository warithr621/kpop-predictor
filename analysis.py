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
    train_lightgbm_quantile_models,
    train_weibull_aft_model,
    predict_next_release_lightgbm_interval,
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

# Only 3rd-gen group still on a regular release cadence
INCLUDE_3RD_GEN = {"TWICE"}

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
    print(f"Training models with cutoff {current_cutoff}...")
    df_train = prepare_training_data(data_by_group, current_cutoff)
    lgbm_models = train_lightgbm_quantile_models(df_train)
    print(f"LightGBM trained on {len(df_train)} rows.")
    weibull_model = train_weibull_aft_model(df_train)
    print("Weibull AFT trained.\n")

    lgbm_results = []
    weibull_results = []

    for group in ALL_GROUPS:
        if GENERATION_MAPPINGS.get(group) == 3 and group not in INCLUDE_3RD_GEN:
            continue
        group_key = sanitize(group)
        df_group = data_by_group.get(group_key)
        if df_group is None or df_group.empty:
            continue

        last_date = pd.to_datetime(df_group["release_date"]).max().date()
        cutoff = last_date - timedelta(days=1)
        min_pred = cutoff + timedelta(days=1)

        lgbm_pred = predict_next_release_lightgbm_interval(
            df_group=df_group,
            models=lgbm_models,
            group_key=group_key,
            cutoff=cutoff,
            min_prediction_date=min_pred,
            all_releases=data_by_group,
        )
        weibull_pred = predict_next_release_weibull_interval(
            df_group=df_group,
            model=weibull_model,
            group_key=group_key,
            cutoff=cutoff,
            min_prediction_date=min_pred,
            all_releases=data_by_group,
        )

        def make_row(group, last_date, pred):
            if pred is None:
                return None
            pred_med = to_date(pred["pred_date_med"])
            pred_low = to_date(pred["pred_date_low"])
            pred_high = to_date(pred["pred_date_high"])
            return {
                "group": group,
                "actual": last_date,
                "pred_med": pred_med,
                "pred_low": pred_low,
                "pred_high": pred_high,
                "error_days": abs((pred_med - last_date).days),
                "signed_days": (pred_med - last_date).days,
            }

        row_lgbm = make_row(group, last_date, lgbm_pred)
        row_weibull = make_row(group, last_date, weibull_pred)
        if row_lgbm:
            lgbm_results.append(row_lgbm)
        if row_weibull:
            weibull_results.append(row_weibull)

    df = pd.DataFrame(lgbm_results)
    df_weibull = pd.DataFrame(weibull_results)

    def window_acc(errors, weeks):
        return 100.0 * np.mean(errors <= weeks * 7)

    def print_stats(label, subset):
        errs = subset["error_days"].values
        signed = subset["signed_days"].values
        print(f"\n{'='*60}")
        print(f"  {label}  (n={len(subset)})")
        print(f"{'='*60}")
        print(f"  Median absolute error : {np.median(errs):.1f} days")
        print(f"  Mean absolute error   : {np.mean(errs):.1f} days")
        print(f"  Bias (median signed)  : {np.median(signed):+.1f} days")
        print()
        for w in WEEK_THRESHOLDS:
            print(f"  Within ±{w:2d} weeks       : {window_acc(errs, w):.1f}%")

    df_4th_5th = df[df["group"].apply(lambda g: GENERATION_MAPPINGS.get(g) in {4, 5})].copy()
    print_stats("LightGBM — ALL GROUPS", df_4th_5th)
    print()

    shortlist_df = df[df["group"].isin(SHORTLIST)].copy()
    print_stats("LightGBM — SHORTLIST (18 groups)", shortlist_df)

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
    print_breakdown("LightGBM — 4th Gen", df4)
    print_breakdown("LightGBM — 5th Gen", df5)

    # ── Weibull AFT section ────────────────────────────────────────────────────
    df_w_4th_5th = df_weibull[df_weibull["group"].apply(lambda g: GENERATION_MAPPINGS.get(g) in {4, 5})].copy()
    print_stats("Weibull AFT — ALL GROUPS", df_w_4th_5th)
    print()

    shortlist_w_df = df_weibull[df_weibull["group"].isin(SHORTLIST)].copy()
    print_stats("Weibull AFT — SHORTLIST (18 groups)", shortlist_w_df)

    df4w = df_weibull[df_weibull["group"].isin(SHORTLIST_4TH)].copy()
    df5w = df_weibull[df_weibull["group"].isin(SHORTLIST_5TH)].copy()
    print_breakdown("Weibull AFT — 4th Gen", df4w)
    print_breakdown("Weibull AFT — 5th Gen", df5w)

    # ── Side-by-side comparison ───────────────────────────────────────────────
    print(f"\n{'='*62}")
    print(f"  MODEL COMPARISON — Leave-Last-Out Backtest (All 4th+5th Gen)")
    print(f"{'='*62}")
    print(f"  {'Metric':<30} {'LightGBM':>12} {'Weibull AFT':>12}")
    print(f"  {'-'*30} {'-'*12} {'-'*12}")

    def cmp_row(label, lgbm_val, w_val, fmt="{:.1f}"):
        print(f"  {label:<30} {fmt.format(lgbm_val):>12} {fmt.format(w_val):>12}")

    l_errs = df_4th_5th["error_days"].values
    w_errs = df_w_4th_5th["error_days"].values
    l_signed = df_4th_5th["signed_days"].values
    w_signed = df_w_4th_5th["signed_days"].values

    cmp_row("MAE (days)", np.mean(l_errs), np.mean(w_errs))
    cmp_row("Median AE (days)", np.median(l_errs), np.median(w_errs))
    cmp_row("Bias / median signed (days)", np.median(l_signed), np.median(w_signed), fmt="{:+.1f}")
    for w in WEEK_THRESHOLDS:
        cmp_row(f"Within ±{w:2d} weeks (%)", window_acc(l_errs, w), window_acc(w_errs, w))

    print(f"{'='*62}")
    print(f"\n  Per-group errors (sorted by LightGBM error):")
    all_groups_in_results = sorted(
        set(df_4th_5th["group"]) | set(df_w_4th_5th["group"])
    )
    lgbm_map = {r["group"]: r["error_days"] for _, r in df_4th_5th.iterrows()}
    w_map    = {r["group"]: r["error_days"] for _, r in df_w_4th_5th.iterrows()}
    for g in sorted(all_groups_in_results, key=lambda g: lgbm_map.get(g, 9999)):
        l_e = lgbm_map.get(g)
        w_e = w_map.get(g)
        l_s = f"{l_e:>5}d" if l_e is not None else "   n/a"
        w_s = f"{w_e:>5}d" if w_e is not None else "   n/a"
        winner = "<-- lgbm" if (l_e is not None and w_e is not None and l_e < w_e) else ("<-- weibull" if (l_e is not None and w_e is not None and w_e < l_e) else "")
        print(f"    {g:<22}  lgbm={l_s}  weibull={w_s}  {winner}")

    return df, df_weibull


if __name__ == "__main__":
    run_leave_last_out()
