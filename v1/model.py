from __future__ import annotations

import argparse
import glob
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from info import GENERATION_MAPPINGS, KPOP_GROUPS

DEFAULT_CUTOFF = date(2024, 12, 31)
DEFAULT_MIN_PREDICTION_DATE = date(2025, 1, 1)


def sanitize(name: str) -> str:
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

	df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce").dt.date
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


def compute_intervals_days(release_dates: List[date]) -> List[int]:
	intervals: List[int] = []
	for earlier, later in zip(release_dates, release_dates[1:]):
		delta = (later - earlier).days
		if delta > 0:
			intervals.append(delta)
	return intervals


def mean_or_none(values: List[int]) -> Optional[float]:
	if not values:
		return None
	return float(sum(values) / len(values))


def map_group_to_generation(group: str) -> Optional[str]:
	return GENERATION_MAPPINGS.get(group)


@dataclass
class CadenceStats:
	group_mean_days: Optional[float]
	generation_mean_days: Optional[float]
	global_mean_days: float

	def pick_interval_days(self) -> int:
		for source in (self.group_mean_days, self.generation_mean_days, self.global_mean_days):
			if source is not None and source > 0:
				return int(round(source))
		return 120


def build_cadence_statistics(
	data_by_group: Dict[str, pd.DataFrame],
	cutoff: date,
) -> Tuple[Dict[str, CadenceStats], Dict[str, float], float]:
	group_to_intervals: Dict[str, List[int]] = {}
	all_intervals: List[int] = []

	gen_to_intervals: Dict[str, List[int]] = {}

	# map sanitized key -> original group name for correct generation lookup
	sanitized_to_original: Dict[str, str] = {sanitize(g): g for g in list_all_groups()}

	for group_key, df in data_by_group.items():
		df_cut = df[df["release_date"] <= cutoff]
		dates = df_cut["release_date"].tolist()
		intervals = compute_intervals_days(dates)
		group_to_intervals[group_key] = intervals
		all_intervals.extend(intervals)

		original_group = sanitized_to_original.get(group_key, group_key)
		gen = map_group_to_generation(original_group)
		if gen is not None:
			gen_to_intervals.setdefault(gen, []).extend(intervals)

	global_mean = mean_or_none(all_intervals) or 120.0
	gen_to_mean: Dict[str, float] = {gen: (mean_or_none(iv) or global_mean) for gen, iv in gen_to_intervals.items()}

	group_to_stats: Dict[str, CadenceStats] = {}
	for group_key, intervals in group_to_intervals.items():
		group_mean = mean_or_none(intervals)
		original_group = sanitized_to_original.get(group_key, group_key)
		gen = map_group_to_generation(original_group)
		gen_mean = gen_to_mean.get(gen) if gen is not None else None
		group_to_stats[group_key] = CadenceStats(
			group_mean_days=group_mean,
			generation_mean_days=gen_mean,
			global_mean_days=global_mean,
		)

	return group_to_stats, gen_to_mean, global_mean


def step_forward_by_interval(start_date: date, interval_days: int, min_date: date) -> date:
	if interval_days <= 0:
		interval_days = 120
	candidate = start_date
	while candidate < min_date:
		candidate = candidate + timedelta(days=interval_days)
	return candidate


def predict_next_release_for_group(
	df_group: pd.DataFrame,
	cadence: CadenceStats,
	cutoff: date,
	min_prediction_date: date,
) -> Optional[date]:
	df_cut = df_group[df_group["release_date"] <= cutoff]
	if df_cut.empty:
		return None
	last_date: date = df_cut["release_date"].max()
	interval_days = cadence.pick_interval_days()
	return step_forward_by_interval(last_date, interval_days, min_prediction_date)


def predict_all(
	albums_dir: str,
	cutoff: date = DEFAULT_CUTOFF,
	min_prediction_date: date = DEFAULT_MIN_PREDICTION_DATE,
) -> pd.DataFrame:
	data_by_group = load_all_releases(albums_dir)
	stats_by_group, gen_to_mean, global_mean = build_cadence_statistics(data_by_group, cutoff)

	records = []
	for group in list_all_groups():
		df_group = data_by_group.get(sanitize(group))
		cadence = stats_by_group.get(sanitize(group))

		if df_group is None or cadence is None:
			predicted_date = min_prediction_date
			last_date = None
			actual_next_date = None
			error_pct = None
		else:
			predicted_date = predict_next_release_for_group(
				df_group=df_group,
				cadence=cadence,
				cutoff=cutoff,
				min_prediction_date=min_prediction_date,
			)
			if predicted_date is None:
				continue
			df_cut = df_group[df_group["release_date"] <= cutoff]
			last_date = df_cut["release_date"].max() if not df_cut.empty else None
			if last_date is not None:
				df_future = df_group[df_group["release_date"] > last_date]
				actual_next_date = df_future["release_date"].min() if not df_future.empty else None
			else:
				actual_next_date = None

			# percent error based on day intervals from last_date
			if last_date is not None and actual_next_date is not None:
				predicted_interval = (predicted_date - last_date).days
				actual_interval = (actual_next_date - last_date).days
				if actual_interval > 0:
					error_pct = abs(predicted_interval - actual_interval) / actual_interval * 100.0
				else:
					error_pct = None
			else:
				error_pct = None

		records.append(
			{
				"group": group,
				"last_release_date": last_date,
				"predicted_next_release_date": predicted_date,
				"actual_next_release_date": actual_next_date,
				"error": error_pct,
			}
		)

	result = pd.DataFrame.from_records(records)
	result = result.sort_values(by=["predicted_next_release_date", "group"]).reset_index(drop=True)
	return result


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Predict next K-pop release dates using cadence model (mean intervals)")
	parser.add_argument(
		"--albums_dir",
		type=str,
		default="albums",
		help="Directory containing per-group CSVs (title,type,release_date)",
	)
	parser.add_argument(
		"--cutoff",
		type=str,
		default=DEFAULT_CUTOFF.isoformat(),
		help="Use only releases on or before this date for training (YYYY-MM-DD)",
	)
	parser.add_argument(
		"--out",
		type=str,
		default="predictions.csv",
		help="Optional path to write predictions CSV",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").date()
	min_date = max(DEFAULT_MIN_PREDICTION_DATE, cutoff + timedelta(days=1))
	predictions = predict_all(albums_dir=args.albums_dir, cutoff=cutoff, min_prediction_date=min_date)

	pred_with_actual = predictions.dropna(subset=["last_release_date", "actual_next_release_date"]).copy()
	if not pred_with_actual.empty:
		for col in ["last_release_date", "predicted_next_release_date", "actual_next_release_date"]:
			pred_with_actual[col] = pd.to_datetime(pred_with_actual[col])
		pred_with_actual["actual_interval_days"] = (
			pred_with_actual["actual_next_release_date"] - pred_with_actual["last_release_date"]
		).dt.days
		pred_with_actual["predicted_interval_days"] = (
			pred_with_actual["predicted_next_release_date"] - pred_with_actual["last_release_date"]
		).dt.days
		valid = pred_with_actual[pred_with_actual["actual_interval_days"] > 0]
		if not valid.empty:
			valid["abs_pct_err"] = (
				(valid["predicted_interval_days"] - valid["actual_interval_days"]).abs()
				/ valid["actual_interval_days"].abs()
			) * 100.0

			overall_mape = valid["abs_pct_err"].mean()
			print(f"Overall MAPE: {overall_mape:.2f}%")
			valid["generation"] = valid["group"].map(GENERATION_MAPPINGS)
			gen_mape = valid.groupby("generation")["abs_pct_err"].mean().sort_index()
			for gen, mape in gen_mape.items():
				label = gen if pd.notna(gen) else "Unknown"
				print(f"MAPE for {label}: {mape:.2f}%")

	if args.out:
		out_cols = [
			"group",
			"last_release_date",
			"predicted_next_release_date",
			"actual_next_release_date",
			"error",
		]
		predictions[out_cols].to_csv(args.out, index=False)
	print(f"Model run is complete. Data up until and including {cutoff} was used; predictions written to {args.out}")


if __name__ == "__main__":
	main()


