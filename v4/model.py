from __future__ import annotations

import argparse
import glob
import os
import re
import warnings
from datetime import date, datetime, timedelta
from itertools import product
from typing import Dict, List, Optional

import pandas as pd
from sklearn.preprocessing import LabelEncoder
from statsmodels.tsa.statespace.sarimax import SARIMAX

from info import GENERATION_MAPPINGS, KPOP_GROUPS, SOLOISTS

warnings.filterwarnings('ignore')

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


def get_solo_releases_for_group(group: str, all_releases: Dict[str, pd.DataFrame]) -> pd.DataFrame:
	solo_releases = []
	
	# Find all soloists that belong to this group
	for soloist, soloist_group in SOLOISTS.items():
		if soloist_group == group:
			soloist_sanitized = sanitize(soloist)
			if soloist_sanitized in all_releases:
				solo_df = all_releases[soloist_sanitized].copy()
				solo_df['soloist'] = soloist
				solo_releases.append(solo_df)
	
	if solo_releases:
		combined_solos = pd.concat(solo_releases, ignore_index=True)
		combined_solos = combined_solos.sort_values('release_date').reset_index(drop=True)
		return combined_solos
	else:
		return pd.DataFrame()


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


def extract_features_from_group(df: pd.DataFrame, group: str, cutoff: date, all_releases: Dict[str, pd.DataFrame]) -> List[Dict]:
	features = []
	generation = GENERATION_MAPPINGS.get(group, 0)
	cutoff_dt = pd.Timestamp(cutoff)
	df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
	if len(df_sorted) < 2:
		return features
	
	# Get solo releases for this group
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
			# do a bunch of annoying math (thanks pandas)
			six_months_ago = current_date - pd.DateOffset(months=6)
			one_year_ago = current_date - pd.DateOffset(months=12)
			two_years_ago = current_date - pd.DateOffset(months=24)
			thirty_days_ago = current_date - pd.DateOffset(days=30)
			recent_solos_6m = len(solo_releases[
				(solo_releases["release_date"] >= six_months_ago) & 
				(solo_releases["release_date"] < current_date)
			])
			recent_solos_1y = len(solo_releases[
				(solo_releases["release_date"] >= one_year_ago) & 
				(solo_releases["release_date"] < current_date)
			])
			recent_solos_2y = len(solo_releases[
				(solo_releases["release_date"] >= two_years_ago) & 
				(solo_releases["release_date"] < current_date)
			])
			
			previous_solos = solo_releases[solo_releases["release_date"] < current_date]
			days_since_last_solo = (current_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
			total_solos_before = len(previous_solos)
			years_since_debut = (current_date - df_sorted.iloc[0]["release_date"]).days / 365.25
			solo_frequency = total_solos_before / max(years_since_debut, 0.1)
			recent_solo_30d = len(solo_releases[
				(solo_releases["release_date"] >= thirty_days_ago) & 
				(solo_releases["release_date"] < current_date)
			])
		
		feature_dict = {
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
			# solo / subunit releases
			"recent_solos_6m": recent_solos_6m,
			"recent_solos_1y": recent_solos_1y,
			"recent_solos_2y": recent_solos_2y,
			"recent_solo_30d": recent_solo_30d,
			"days_since_last_solo": days_since_last_solo,
			"solo_frequency": solo_frequency,
			"target_days": target_days
		}
		features.append(feature_dict)
	
	return features


def prepare_training_data(data_by_group: Dict[str, pd.DataFrame], cutoff: date) -> pd.DataFrame:
	all_features = []
	for group, df in data_by_group.items():
		features = extract_features_from_group(df, group, cutoff, data_by_group)
		all_features.extend(features)
	if not all_features:
		return pd.DataFrame()
	df_features = pd.DataFrame(all_features)
	
	# categorical variables
	le_group = LabelEncoder()
	le_type = LabelEncoder()
	df_features["group_encoded"] = le_group.fit_transform(df_features["group"])
	df_features["type_encoded"] = le_type.fit_transform(df_features["release_type"])
	
	return df_features


def prepare_time_series_data(data_by_group: Dict[str, pd.DataFrame], cutoff: date) -> Dict[str, Dict]:
	time_series_data = {}
	
	for group, df in data_by_group.items():
		# skip groups with insufficient data
		if len(df) < 3:
			continue
			
		# get solo releases for this group
		solo_releases = get_solo_releases_for_group(group, data_by_group)
		cutoff_dt = pd.Timestamp(cutoff)
		df_sorted = df[df["release_date"] <= cutoff_dt].sort_values("release_date")
		if len(df_sorted) < 3:
			continue
		
		# Calculate intervals between releases
		intervals = df_sorted["release_date"].diff().dt.days.dropna()
		if len(intervals) < 2:
			continue
		ts_data = {
			'y': intervals.values,  # days between releases
			'dates': df_sorted["release_date"].iloc[1:].values,
			'group': group,
			'df_original': df_sorted
		}
		
		# exogenous vars (wow the X in SARIMAX)
		exog_vars = []
		for i, (date, _) in enumerate(zip(df_sorted["release_date"].iloc[1:], intervals)):
			exog_row = {}
			exog_row['release_number'] = i + 2  # +2 because we start from the second release
			exog_row['days_since_debut'] = (date - df_sorted.iloc[0]["release_date"]).days
			exog_row['month'] = date.month
			exog_row['quarter'] = (date.month - 1) // 3 + 1
			exog_row['generation'] = GENERATION_MAPPINGS.get(group, 0)
			
			recent_solos_6m = 0
			recent_solos_1y = 0
			recent_solos_2y = 0
			recent_solo_30d = 0
			days_since_last_solo = 9999
			solo_frequency = 0
			
			if not solo_releases.empty and 'release_date' in solo_releases.columns:
				six_months_ago = date - pd.DateOffset(months=6)
				one_year_ago = date - pd.DateOffset(months=12)
				two_years_ago = date - pd.DateOffset(months=24)
				thirty_days_ago = date - pd.DateOffset(days=30)
				
				recent_solos_6m = len(solo_releases[
					(solo_releases["release_date"] >= six_months_ago) & 
					(solo_releases["release_date"] < date)
				])
				recent_solos_1y = len(solo_releases[
					(solo_releases["release_date"] >= one_year_ago) & 
					(solo_releases["release_date"] < date)
				])
				recent_solos_2y = len(solo_releases[
					(solo_releases["release_date"] >= two_years_ago) & 
					(solo_releases["release_date"] < date)
				])
				recent_solo_30d = len(solo_releases[
					(solo_releases["release_date"] >= thirty_days_ago) & 
					(solo_releases["release_date"] < date)
				])
				
				previous_solos = solo_releases[solo_releases["release_date"] < date]
				days_since_last_solo = (date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
				total_solos_before = len(previous_solos)
				years_since_debut = (date - df_sorted.iloc[0]["release_date"]).days / 365.25
				solo_frequency = total_solos_before / max(years_since_debut, 0.1)
			
			exog_row.update({
				'recent_solos_6m': recent_solos_6m,
				'recent_solos_1y': recent_solos_1y,
				'recent_solos_2y': recent_solos_2y,
				'recent_solo_30d': recent_solo_30d,
				'days_since_last_solo': days_since_last_solo,
				'solo_frequency': solo_frequency
			})
			
			exog_vars.append(exog_row)
		
		ts_data['exog'] = pd.DataFrame(exog_vars)
		time_series_data[group] = ts_data
	
	return time_series_data


def train_sarimax_models(time_series_data: Dict[str, Dict]) -> Dict[str, object]:
	models = {}
	
	for group, ts_data in time_series_data.items():
		try:
			y = ts_data['y']
			exog = ts_data['exog']
			exog_cols = [
				'recent_solos_6m', 'recent_solos_1y', 'recent_solos_2y',
				'recent_solo_30d', 'days_since_last_solo', 'solo_frequency',
				'release_number', 'days_since_debut', 'month', 'quarter', 'generation'
			]
			
			available_cols = [col for col in exog_cols if col in exog.columns]
			exog_subset = exog[available_cols]
			
			# order guessing :fire:
			orders_to_try = [(1,0,0), (0,0,1), (1,0,1), (2,0,0), (0,0,2), (1,0,2), (2,0,1)]
			# use common ARIMA parameters ^
			best_aic = float('inf')
			best_model = None
			
			for order in orders_to_try:
				try:
					# the model will eventually use seasonality (likely quarters or years), for now running with no seasonality parameter
					# in essence this is just ARIMAX
					model = SARIMAX(
						endog=y,
						exog=exog_subset,
						order=order,
						seasonal_order=(0, 0, 0, 0),
						enforce_stationarity=False,
						enforce_invertibility=False
					)
					fitted_model = model.fit(disp=False)
					if fitted_model.aic < best_aic:
						best_aic = fitted_model.aic
						best_model = fitted_model
				except Exception as e:
					continue
			
			if best_model is not None:
				models[group] = best_model
				print(f"Trained SARIMAX model for {group} with order {best_model.model.order}")
			else:
				print(f"Failed to train SARIMAX model for {group}")
				
		except Exception as e:
			print(f"Error training model for {group}: {e}")
			continue
	
	return models


def predict_next_release_sarimax(
	df_group: pd.DataFrame,
	model: object,
	group: str,
	cutoff: date,
	min_prediction_date: date,
	all_releases: Dict[str, pd.DataFrame]
) -> Optional[date]:
	
	cutoff_dt = pd.Timestamp(cutoff)
	min_prediction_dt = pd.Timestamp(min_prediction_date)
	df_cut = df_group[df_group["release_date"] <= cutoff_dt]
	if df_cut.empty:
		return None
	last_release = df_cut.iloc[-1]
	last_date = last_release["release_date"]
	
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
		
		recent_solos_6m = len(solo_releases[
			(solo_releases["release_date"] >= six_months_ago) & 
			(solo_releases["release_date"] <= last_date)
		])
		recent_solos_1y = len(solo_releases[
			(solo_releases["release_date"] >= one_year_ago) & 
			(solo_releases["release_date"] <= last_date)
		])
		recent_solos_2y = len(solo_releases[
			(solo_releases["release_date"] >= two_years_ago) & 
			(solo_releases["release_date"] <= last_date)
		])
		recent_solo_30d = len(solo_releases[
			(solo_releases["release_date"] >= thirty_days_ago) & 
			(solo_releases["release_date"] <= last_date)
		])
		
		previous_solos = solo_releases[solo_releases["release_date"] <= last_date]
		days_since_last_solo = (last_date - previous_solos.iloc[-1]["release_date"]).days if not previous_solos.empty else 9999
		total_solos_before = len(previous_solos)
		years_since_debut = (last_date - df_cut.iloc[0]["release_date"]).days / 365.25
		solo_frequency = total_solos_before / max(years_since_debut, 0.1)
	
	# prepare exogenous
	# wow this is an annoying word to spell
	exog_pred = pd.DataFrame([{
		'recent_solos_6m': recent_solos_6m,
		'recent_solos_1y': recent_solos_1y,
		'recent_solos_2y': recent_solos_2y,
		'recent_solo_30d': recent_solo_30d,
		'days_since_last_solo': days_since_last_solo,
		'solo_frequency': solo_frequency,
		'release_number': len(df_cut) + 1,
		'days_since_debut': (last_date - df_cut.iloc[0]["release_date"]).days,
		'month': last_date.month,
		'quarter': (last_date.month - 1) // 3 + 1,
		'generation': GENERATION_MAPPINGS.get(group, 0)
	}])
	
	try:
		forecast = model.forecast(steps=1, exog=exog_pred)
		predicted_days = max(1, int(round(forecast[0]))) # pos
		
		predicted_date = last_date + timedelta(days=predicted_days)
		while predicted_date < min_prediction_dt:
			predicted_date += timedelta(days=predicted_days)
		
		return predicted_date
		
	except Exception as e:
		# fallback (in case something happens ig)
		if len(df_cut) > 1:
			avg_interval = df_cut["release_date"].diff().dt.days.mean()
			predicted_date = last_date + timedelta(days=int(avg_interval))
			while predicted_date < min_prediction_dt:
				predicted_date += timedelta(days=int(avg_interval))
			return predicted_date
		else:
			return min_prediction_dt


def predict_all(
	albums_dir: str = "albums",
	cutoff: date = DEFAULT_CUTOFF,
	min_prediction_date: date = DEFAULT_MIN_PREDICTION_DATE,
) -> pd.DataFrame:
	
	data_by_group = load_all_releases(albums_dir)
	time_series_data = prepare_time_series_data(data_by_group, cutoff)
	
	if not time_series_data:
		print("Warning: No time series data available. Using fallback predictions.")
		exit(1)
	
	models = train_sarimax_models(time_series_data)
	if not models:
		print("Warning: No models trained successfully. Using fallback predictions.")
		exit(1)
	cutoff_dt = pd.Timestamp(cutoff)
	
	# do prediction stuff
	records = []
	for group in list_all_groups():
		df_group = data_by_group.get(sanitize(group))
		
		if df_group is None or sanitize(group) not in models:
			predicted_date = min_prediction_date
			last_date = None
			actual_next_date = None
			error_pct = None
		else:
			model = models[sanitize(group)]
			predicted_date = predict_next_release_sarimax(
				df_group=df_group,
				model=model,
				group=group,
				cutoff=cutoff,
				min_prediction_date=min_prediction_date,
				all_releases=data_by_group
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
					error_days = abs(predicted_interval - actual_interval) # absolute error (in days)
				else:
					error_pct = None
					error_days = None
			else:
				error_pct = None
				error_days = None
		
		records.append({
			"group": group,
			"last_release_date": last_date.strftime("%Y-%m-%d") if last_date is not None else None,
			"predicted_next_release_date": predicted_date.strftime("%Y-%m-%d") if predicted_date is not None else None,
			"actual_next_release_date": actual_next_date.strftime("%Y-%m-%d") if actual_next_date is not None else None,
			"error_pct": round(error_pct, 3) if error_pct is not None else None,
			"error_days": error_days,
		})
	
	result = pd.DataFrame.from_records(records)
	result = result.sort_values(by=["predicted_next_release_date", "group"]).reset_index(drop=True)
	return result


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Predict next K-pop release dates using SARIMAX")
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
	
	print(f"Training SARIMAX models on data up to {cutoff}...")
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
			
			# overall stats math
			overall_mape = valid["abs_pct_err"].mean()
			overall_mae = (valid["predicted_interval_days"] - valid["actual_interval_days"]).abs().mean()
			
			os.system('cls' if os.name == 'nt' else 'clear')
			print(f"Overall MAPE: {overall_mape:.2f}%")
			print(f"Overall MAE: {overall_mae:.1f} days")
			print("-" * 20)
			valid["generation"] = valid["group"].map(GENERATION_MAPPINGS)
			generations_found = False
			for gen in sorted(valid["generation"].unique()):
				if gen == 0:
					continue
				gen_data = valid[valid["generation"] == gen]
				if gen_data.empty:
					continue
				generations_found = True
				
				gen_mape = gen_data["abs_pct_err"].mean()
				gen_mae = (gen_data["predicted_interval_days"] - gen_data["actual_interval_days"]).abs().mean()
				gen_errors = (gen_data["predicted_interval_days"] - gen_data["actual_interval_days"]).abs()
				label = f"{gen}rd Gen" if gen == 3 else f"{gen}th Gen"
				print(f"{label}")
				print(f"MAPE: {gen_mape:.2f}%")
				print(f"Lowest Error: {gen_errors.min():.1f} days")
				print(f"MAE: {gen_mae:.1f} days")
				print(f"Most Error: {gen_errors.max():.1f} days")
				print(f"Stdev of Error: {gen_errors.std():.1f} days")
				print("-" * 20)
			
			if not generations_found:
				print("No generation data available for detailed statistics.")
	
	if args.out:
		out_cols = [
			"group",
			"last_release_date",
			"predicted_next_release_date",
			"actual_next_release_date",
			"error_pct",
			"error_days",
		]
		predictions[out_cols].to_csv(args.out, index=False)
	
	print(f"SARIMAX model run complete. Data up until and including {cutoff} was used; predictions written to {args.out}")


if __name__ == "__main__":
	main()

