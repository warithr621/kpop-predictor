from __future__ import annotations

import argparse
import glob
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import lightgbm as lgb
import pandas as pd
from sklearn.preprocessing import LabelEncoder

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


def extract_features_from_group(df: pd.DataFrame, group: str, cutoff: date) -> List[Dict]:
	features = []
	generation = GENERATION_MAPPINGS.get(group, "Unknown")
	cutoff_dt = pd.Timestamp(cutoff)
	df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
	if len(df_sorted) < 2:
		return features
	for i in range(1, len(df_sorted)):
		current_release = df_sorted.iloc[i]
		previous_releases = df_sorted.iloc[:i]
		
		if i < len(df_sorted) - 1:
			next_release = df_sorted.iloc[i + 1]
			target_days = (next_release["release_date"] - current_release["release_date"]).days
		else:
			continue
		
		feature_dict = { # pain
			"group": group,
			"generation": generation,
			"release_date": current_release["release_date"],
			"release_type": current_release["type"],
			"release_number": i,  # nth release for this group
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
			"target_days": target_days
		}
		features.append(feature_dict)
	
	return features


def prepare_training_data(data_by_group: Dict[str, pd.DataFrame], cutoff: date) -> pd.DataFrame:
	all_features = []
	for group, df in data_by_group.items():
		features = extract_features_from_group(df, group, cutoff)
		all_features.extend(features)
	if not all_features:
		return pd.DataFrame()
	df_features = pd.DataFrame(all_features)
	
	# categorical variables
	le_group = LabelEncoder()
	le_generation = LabelEncoder()
	le_type = LabelEncoder()
	df_features["group_encoded"] = le_group.fit_transform(df_features["group"])
	df_features["generation_encoded"] = le_generation.fit_transform(df_features["generation"])
	df_features["type_encoded"] = le_type.fit_transform(df_features["release_type"])
	
	return df_features


def train_lightgbm_model(df_train: pd.DataFrame) -> lgb.LGBMRegressor:
	
	# fts for training
	feature_cols = [
		"group_encoded", "generation_encoded", "type_encoded",
		"release_number", "days_since_debut", "days_since_previous",
		"avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
		"min_interval_so_far", "max_interval_so_far",
		"releases_this_year", "releases_last_year",
		"month", "quarter"
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
	min_prediction_date: date
) -> Optional[date]:
	
	cutoff_dt = pd.Timestamp(cutoff)
	min_prediction_dt = pd.Timestamp(min_prediction_date)
	df_cut = df_group[df_group["release_date"] <= cutoff_dt]
	if df_cut.empty:
		return None
	
	last_release = df_cut.iloc[-1]
	last_date = last_release["release_date"]
	previous_releases = df_cut.iloc[:-1] if len(df_cut) > 1 else pd.DataFrame()
	generation = GENERATION_MAPPINGS.get(group, "Unknown")
	
	feature_dict = {
		"group_encoded": hash(group) % 1000,
		"generation_encoded": hash(generation) % 10,
		"type_encoded": hash(last_release["type"]) % 10,
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
		"quarter": (last_date.month - 1) // 3 + 1
	}
	
	# ft array
	feature_cols = [
		"group_encoded", "generation_encoded", "type_encoded",
		"release_number", "days_since_debut", "days_since_previous",
		"avg_interval_so_far", "median_interval_so_far", "std_interval_so_far",
		"min_interval_so_far", "max_interval_so_far",
		"releases_this_year", "releases_last_year",
		"month", "quarter"
	]
	
	X_pred = pd.DataFrame([feature_dict], columns=feature_cols)
	
	# Predict days until next release
	predicted_days = model.predict(X_pred)[0]
	predicted_days = max(1, int(round(predicted_days)))  # should be pos, but just in case
	predicted_date = last_date + timedelta(days=predicted_days)
	while predicted_date < min_prediction_dt:
		predicted_date += timedelta(days=predicted_days)
	return predicted_date


def predict_all(
	albums_dir: str = "albums",
	cutoff: date = DEFAULT_CUTOFF,
	min_prediction_date: date = DEFAULT_MIN_PREDICTION_DATE,
) -> pd.DataFrame:
	
	data_by_group = load_all_releases(albums_dir)
	df_train = prepare_training_data(data_by_group, cutoff)
	if df_train.empty:
		print("Warning: No training data available. Using fallback predictions.")
		exit(1)
	
	model = train_lightgbm_model(df_train)
	cutoff_dt = pd.Timestamp(cutoff)
	
	# do prediction stuff
	records = []
	for group in list_all_groups():
		df_group = data_by_group.get(sanitize(group))
		
		if df_group is None:
			predicted_date = min_prediction_date
			last_date = None
			actual_next_date = None
			error_pct = None
		else:
			predicted_date = predict_next_release_lightgbm(
				df_group=df_group,
				model=model,
				group=group,
				cutoff=cutoff,
				min_prediction_date=min_prediction_date
			)
			if predicted_date is None:
				continue

			df_cut = df_group[df_group["release_date"] <= cutoff_dt]
			last_date = df_cut["release_date"].max() if not df_cut.empty else None
			
			if last_date is not None:
				df_future = df_group[df_group["release_date"] > last_date]
				actual_next_date = df_future["release_date"].min() if not df_future.empty else None
			else:
				actual_next_date = None
			
			if last_date is not None and actual_next_date is not None:
				predicted_interval = (predicted_date - last_date).days
				actual_interval = (actual_next_date - last_date).days
				if actual_interval > 0:
					error_pct = abs(predicted_interval - actual_interval) / actual_interval * 100.0
				else:
					error_pct = None
			else:
				error_pct = None
		
		records.append({
			"group": group,
			"last_release_date": last_date.strftime("%Y-%m-%d") if last_date is not None else None,
			"predicted_next_release_date": predicted_date.strftime("%Y-%m-%d") if predicted_date is not None else None,
			"actual_next_release_date": actual_next_date.strftime("%Y-%m-%d") if actual_next_date is not None else None,
			"error": round(error_pct, 3) if error_pct is not None else None,
		})
	
	result = pd.DataFrame.from_records(records)
	result = result.sort_values(by=["predicted_next_release_date", "group"]).reset_index(drop=True)
	return result


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Predict next K-pop release dates using LightGBM")
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
	
	print(f"Training LightGBM model on data up to {cutoff}...")
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
	
	print(f"LightGBM model run complete. Data up until and including {cutoff} was used; predictions written to {args.out}")


if __name__ == "__main__":
	main()


