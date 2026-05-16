from __future__ import annotations

import hashlib
import json
import os
import pickle
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Reuse mappings from root info.py
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from info import GENERATION_MAPPINGS, KPOP_GROUPS, GROUP_COMPANIES
from backend.model import (
    DEFAULT_CUTOFF,
    DEFAULT_MIN_PREDICTION_DATE,
    sanitize,
    load_group_releases,
    load_all_releases,
    prepare_training_data,
    train_lightgbm_quantile_models,
    predict_next_release_lightgbm_interval,
    compute_data_signature,
    load_group_error_stats,
    get_current_cutoff_dates,
)


ALBUMS_DIR = os.path.join(ROOT_DIR, "albums")
CACHE_DIR = os.path.join(ROOT_DIR, "backend", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class PredictRequest(BaseModel):
    group: str


app = FastAPI(title="K-pop Predictor API", version="0.1.0")

# In dev, allow all origins by default; override with env if needed
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def status():
    try:
        sig = compute_data_signature(ALBUMS_DIR)
        return {"status": "ok", "data_signature": sig}
    except Exception as exc:  # pragma: no cover
        return {"status": "degraded", "error": str(exc)}


@app.get("/api/groups")
def get_groups():
    groups: List[Dict[str, str]] = []
    for generation_label, group_names in KPOP_GROUPS.items():
        for name in group_names:
            company = GROUP_COMPANIES.get(name)
            groups.append({
                "name": name,
                "generation": generation_label,
                "company": company,
            })
    return {"groups": groups}


@app.get("/api/releases")
def get_releases(group: str = Query(..., description="Exact group name as shown in /api/groups")):
    try:
        csv_key = sanitize(group)
        csv_path = os.path.join(ALBUMS_DIR, f"{csv_key}.csv")
        if not os.path.exists(csv_path):
            raise HTTPException(status_code=404, detail=f"No CSV found for group '{group}'")
        df = load_group_releases(csv_path)
        records = [
            {
                "title": row["title"],
                "type": row["type"],
                "date": pd.to_datetime(row["release_date"]).date().isoformat(),
            }
            for _, row in df.iterrows()
        ]
        return {"group": group, "releases": records}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _load_or_train_model(cutoff_date: date = DEFAULT_CUTOFF):
    """Train the model using all data up to cutoff_date or load from cache.

    Returns (models, data_by_group, signature)
    """
    signature = compute_data_signature(ALBUMS_DIR)
    # Include cutoff date in cache key to avoid stale cache when using current date
    cutoff_str = cutoff_date.isoformat()
    # Bump this when the feature schema / training objective changes.
    cache_key = f"model_v8_quantiles_{signature}_{cutoff_str}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            payload = pickle.load(f)
        return payload["models"], payload["data_by_group"], signature

    data_by_group = load_all_releases(ALBUMS_DIR)
    df_train = prepare_training_data(data_by_group, cutoff_date)
    if df_train.empty:
        raise HTTPException(status_code=500, detail="No training data available")
    models = train_lightgbm_quantile_models(df_train)
    with open(cache_path, "wb") as f:
        pickle.dump({"models": models, "data_by_group": data_by_group}, f)
    return models, data_by_group, signature


@app.post("/api/predict")
def predict(req: PredictRequest):
    start_ts = datetime.utcnow()
    try:
        # Use current date as cutoff instead of hardcoded DEFAULT_CUTOFF
        current_cutoff, current_min_prediction = get_current_cutoff_dates()
        
        models, data_by_group, signature = _load_or_train_model(current_cutoff)

        group = req.group
        group_key = sanitize(group)
        df_group = data_by_group.get(group_key)
        if df_group is None or df_group.empty:
            raise HTTPException(status_code=404, detail=f"No data for group '{group}'")

        pred = predict_next_release_lightgbm_interval(
            df_group=df_group,
            models=models,
            group_key=group_key,
            cutoff=current_cutoff,
            min_prediction_date=current_min_prediction,
            all_releases=data_by_group,
        )

        if pred is None:
            raise HTTPException(status_code=422, detail="Unable to produce a prediction for this group")

        # uncertainty from historical errors if available
        err = load_group_error_stats(group)
        uncertainty_days: Optional[float] = None
        notes_parts: List[str] = []
        if err is not None:
            uncertainty_days = err.get("mae_days")
            notes_parts.append("uncertainty approximated by past MAE")
        if uncertainty_days is None:
            try:
                uncertainty_days = (pred["pred_days_high"] - pred["pred_days_low"]) / 2.0
                notes_parts.append("uncertainty derived from predicted interval")
            except Exception:
                pass
        runtime_sec = (datetime.utcnow() - start_ts).total_seconds()
        notes_parts.append(f"runtime: {runtime_sec:.1f}s")
        notes_parts.append(f"trained on data through {current_cutoff.isoformat()}")

        return {
            "group": group,
            # Backwards compatible: keep `pred_date` as the median.
            "pred_date": pred["pred_date_med"].isoformat(),
            "pred_date_low": pred["pred_date_low"].isoformat(),
            "pred_date_med": pred["pred_date_med"].isoformat(),
            "pred_date_high": pred["pred_date_high"].isoformat(),
            "pred_days_low": pred["pred_days_low"],
            "pred_days_med": pred["pred_days_med"],
            "pred_days_high": pred["pred_days_high"],
            "uncertainty_days": uncertainty_days,
            "notes": ", ".join(notes_parts),
            "metrics": err or {},
            "data_signature": signature,
            "cutoff_date": current_cutoff.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/")
def root():
    return {"message": "K-pop Predictor API. See /api/status"}
