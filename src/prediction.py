"""
Random Forest classifier for predicting roadworthiness inspection outcomes.

The model predicts whether a regular inspection (KORRALINE) is passed on the
first attempt. The training flow mirrors the grading notebook:

- read yearly inspection CSVs from the local cache when available;
- clean the target and age fields;
- use a temporal split when multiple years are present;
- exclude target-derived pass-rate and station-strictness features.

Usage:
    python src/prediction.py --years 2023 2024 2025
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MPLCONFIG_DIR = PROJECT_ROOT / ".matplotlib"
MPLCONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR))

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    from src.data_cache import source_for_year
except ModuleNotFoundError:
    from data_cache import source_for_year


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"

DEFAULT_YEARS = [2023, 2024, 2025]

REQUIRED_COLUMNS = [
    "TEHNOYLEVAATUSPUNKT",
    "PUNKTI_KOOD",
    "YV_KUUPAEV",
    "YLEVAATUSLIIK",
    "YLEVAATUSOTSUS",
    "SOIDUK_ID",
    "ESMANE_REG_AASTA",
    "MARK",
    "MUDEL",
    "KATEGOORIA",
    "KERETYYP",
]

NUMERIC_FEATURES = [
    "VANUS",
    "VANUS_RUUT",
    "ON_VANA",
    "KUU_SIN",
    "KUU_COS",
    "MARK_SAGEDUS",
    "MUDEL_SAGEDUS",
    "EELMISED_YV",
]

HISTORICAL_RATE_SPECS = [
    ("HIST_MARK_FAIL_RATE", ("MARK",)),
    ("HIST_MUDEL_FAIL_RATE", ("MARK", "MUDEL")),
    ("HIST_KATEGOORIA_FAIL_RATE", ("KATEGOORIA",)),
    ("HIST_KERETYYP_FAIL_RATE", ("KERETYYP",)),
    ("HIST_PUNKT_FAIL_RATE", ("PUNKTI_KOOD",)),
    ("HIST_PUNKT_KATEGOORIA_FAIL_RATE", ("PUNKTI_KOOD", "KATEGOORIA")),
]
HISTORICAL_RATE_FEATURES = [name for name, _cols in HISTORICAL_RATE_SPECS]
MODEL_NUMERIC_FEATURES = NUMERIC_FEATURES + HISTORICAL_RATE_FEATURES
CATEGORICAL_FEATURES = ["MARK", "KATEGOORIA", "KERETYYP", "PUNKTI_KOOD"]
RATE_SOURCE_FEATURES = ["MARK", "MUDEL", "KATEGOORIA", "KERETYYP", "PUNKTI_KOOD"]
FEATURE_COLS = NUMERIC_FEATURES + RATE_SOURCE_FEATURES

LEAKAGE_PRONE_FEATURES = [
    "MARK_LABIMISE_MAAR",
    "MUDEL_LABIMISE_MAAR",
    "PUNKTI_RANGUS",
]

TARGET_COL = "LABIS_ESIMESEL"
TEXT_COLUMNS = [
    "TEHNOYLEVAATUSPUNKT",
    "PUNKTI_KOOD",
    "YV_KUUPAEV",
    "YLEVAATUSLIIK",
    "YLEVAATUSOTSUS",
    "MARK",
    "MUDEL",
    "KATEGOORIA",
    "KERETYYP",
]


class HistoricalRateEncoder(BaseEstimator, TransformerMixin):
    """
    Add smoothed historical fail-rate features learned only from training data.

    The target is 1 for first-time pass and 0 for repeat inspection. This
    transformer therefore encodes fail risk as 1 - target. It is fitted inside
    the sklearn Pipeline, so test-year rows never influence the mappings.
    """

    def __init__(
        self,
        rate_specs: list[tuple[str, tuple[str, ...]]] | None = None,
        smoothing: float = 100.0,
        missing_token: str = "__MISSING__",
    ):
        self.rate_specs = rate_specs
        self.smoothing = smoothing
        self.missing_token = missing_token

    def fit(self, X, y):
        X_df = self._as_frame(X)
        self.feature_names_in_ = np.asarray(X_df.columns, dtype=object)
        self.rate_specs_ = self.rate_specs or HISTORICAL_RATE_SPECS

        fail_target = 1 - pd.Series(y, index=X_df.index).astype(float)
        self.global_fail_rate_ = float(fail_target.mean()) if len(fail_target) else 0.0
        self.rate_maps_ = {}

        for output_col, source_cols in self.rate_specs_:
            keys = self._make_keys(X_df, source_cols)
            stats = (
                pd.DataFrame({"key": keys, "fail": fail_target})
                .groupby("key", dropna=False)["fail"]
                .agg(["sum", "count"])
            )
            smoothed = (
                stats["sum"] + self.smoothing * self.global_fail_rate_
            ) / (stats["count"] + self.smoothing)
            self.rate_maps_[output_col] = smoothed.astype(float).to_dict()

        return self

    def transform(self, X):
        X_df = self._as_frame(X).copy()
        for output_col, source_cols in self.rate_specs_:
            keys = self._make_keys(X_df, source_cols)
            X_df[output_col] = (
                keys.map(self.rate_maps_.get(output_col, {}))
                .fillna(self.global_fail_rate_)
                .astype(float)
            )
        return X_df

    def _as_frame(self, X) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            return X
        columns = getattr(self, "feature_names_in_", None)
        return pd.DataFrame(X, columns=columns)

    def _make_keys(self, X_df: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
        existing = [column for column in columns if column in X_df.columns]
        if not existing:
            return pd.Series(self.missing_token, index=X_df.index)
        parts = [
            X_df[column].astype("object").where(X_df[column].notna(), self.missing_token).astype(str)
            for column in existing
        ]
        key = parts[0]
        for part in parts[1:]:
            key = key + "||" + part
        return key


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if pd.isna(value):
        return None
    return value


def load_year(year: int, max_rows: int | None = None, prefer_cache: bool = True) -> pd.DataFrame:
    """Load one yearly source from cache or remote URL."""
    source = source_for_year(int(year), prefer_cache=prefer_cache)
    df = pd.read_csv(
        source,
        dtype=str,
        usecols=lambda column: column in REQUIRED_COLUMNS,
        nrows=max_rows,
        low_memory=False,
    )
    df["ALLIKA_AASTA"] = int(year)
    return df


def load_years(
    years: Iterable[int],
    max_rows_per_year: int | None = None,
    prefer_cache: bool = True,
) -> pd.DataFrame:
    """Load and concatenate selected yearly inspection files."""
    parts = []
    for year in sorted(int(y) for y in years):
        part = load_year(year, max_rows=max_rows_per_year, prefer_cache=prefer_cache)
        parts.append(part)
        print(f"{year}: {len(part):,} rows")
    df = pd.concat(parts, ignore_index=True)
    print(f"Loaded total: {len(df):,} rows")
    return df


def clean_inspections(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw inspection rows and create the binary target."""
    cleaned = df.copy()

    for column in TEXT_COLUMNS:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()

    cleaned["YV_AASTA"] = pd.to_numeric(
        cleaned["YV_KUUPAEV"].str[:4], errors="coerce"
    )
    cleaned["YV_KUU"] = pd.to_numeric(
        cleaned["YV_KUUPAEV"].str[5:7], errors="coerce"
    )
    cleaned["ESMANE_REG_AASTA"] = pd.to_numeric(
        cleaned["ESMANE_REG_AASTA"], errors="coerce"
    )
    cleaned["SOIDUK_ID"] = pd.to_numeric(cleaned["SOIDUK_ID"], errors="coerce")

    cleaned["VANUS"] = cleaned["YV_AASTA"] - cleaned["ESMANE_REG_AASTA"]
    cleaned.loc[(cleaned["VANUS"] < 0) | (cleaned["VANUS"] > 100), "VANUS"] = np.nan

    cleaned[TARGET_COL] = np.nan
    regular = cleaned["YLEVAATUSLIIK"] == "KORRALINE"
    cleaned.loc[regular & (cleaned["YLEVAATUSOTSUS"] == "KORRAS"), TARGET_COL] = 1
    cleaned.loc[regular & (cleaned["YLEVAATUSOTSUS"] == "KORDUVALE"), TARGET_COL] = 0

    critical = ["SOIDUK_ID", "MARK", "ESMANE_REG_AASTA", "VANUS"]
    cleaned["ANDMED_PUUDULIKUD"] = cleaned[critical].isna().any(axis=1).astype(int)

    return cleaned


def create_model_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Create the leakage-safe feature frame used by the classifier."""
    model_df = df.copy()
    if TARGET_COL not in model_df.columns:
        model_df = clean_inspections(model_df)

    model_df = model_df.dropna(subset=[TARGET_COL, "VANUS", "YV_KUU", "YV_AASTA"]).copy()
    model_df[TARGET_COL] = model_df[TARGET_COL].astype(int)

    model_df["VANUS_RUUT"] = model_df["VANUS"] ** 2
    model_df["ON_VANA"] = (model_df["VANUS"] > 10).astype(int)
    model_df["KUU_SIN"] = np.sin(2 * np.pi * model_df["YV_KUU"] / 12)
    model_df["KUU_COS"] = np.cos(2 * np.pi * model_df["YV_KUU"] / 12)
    model_df["MARK_SAGEDUS"] = model_df.groupby("MARK")["MARK"].transform("size")

    if "MUDEL" in model_df.columns:
        model_df["MUDEL_SAGEDUS"] = model_df.groupby(["MARK", "MUDEL"])["MUDEL"].transform("size")
    else:
        model_df["MUDEL_SAGEDUS"] = 0

    if "SOIDUK_ID" in model_df.columns:
        ordered = model_df.sort_values(["SOIDUK_ID", "YV_AASTA", "YV_KUU"])
        model_df["EELMISED_YV"] = ordered.groupby("SOIDUK_ID").cumcount().reindex(model_df.index)
    else:
        model_df["EELMISED_YV"] = 0

    for column in NUMERIC_FEATURES:
        model_df[column] = pd.to_numeric(model_df[column], errors="coerce").astype(float)

    for column in RATE_SOURCE_FEATURES:
        if column not in model_df.columns:
            model_df[column] = np.nan
        model_df[column] = model_df[column].astype("object").where(model_df[column].notna(), np.nan)

    return model_df


def _temporal_split(
    ml_df: pd.DataFrame,
    feature_cols: list[str],
    holdout_years: int = 1,
) -> tuple | None:
    """Split by year, holding out the latest year(s), when the data supports it."""
    if "YV_AASTA" not in ml_df.columns:
        return None

    years = sorted(int(y) for y in ml_df["YV_AASTA"].dropna().unique())
    if len(years) <= holdout_years:
        return None

    test_years = years[-holdout_years:]
    train_years = years[:-holdout_years]

    train_df = ml_df[ml_df["YV_AASTA"].isin(train_years)]
    test_df = ml_df[ml_df["YV_AASTA"].isin(test_years)]
    if train_df.empty or test_df.empty:
        return None
    if train_df[TARGET_COL].nunique() < 2 or test_df[TARGET_COL].nunique() < 2:
        return None

    split_info = {
        "type": "temporal",
        "train_years": train_years,
        "test_years": test_years,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
    }
    return (
        train_df[feature_cols],
        test_df[feature_cols],
        train_df[TARGET_COL],
        test_df[TARGET_COL],
        split_info,
    )


def _random_split(ml_df: pd.DataFrame, feature_cols: list[str]) -> tuple:
    X = ml_df[feature_cols]
    y = ml_df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    split_info = {
        "type": "stratified_random",
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }
    return X_train, X_test, y_train, y_test, split_info


def prepare_data(df: pd.DataFrame, holdout_years: int = 1) -> tuple:
    """
    Prepare train/test split for the classifier.

    Returns (X_train, X_test, y_train, y_test, feature_names, split_info).
    """
    ml_df = create_model_frame(df)
    ml_df = ml_df.dropna(subset=[TARGET_COL]).copy()

    split = _temporal_split(ml_df, FEATURE_COLS, holdout_years=holdout_years)
    if split is None:
        split = _random_split(ml_df, FEATURE_COLS)
    X_train, X_test, y_train, y_test, split_info = split

    print(f"Dataset: {len(ml_df):,} rows")
    print(f"Features: {len(FEATURE_COLS)}")
    print(f"Train set: {len(X_train):,} | Test set: {len(X_test):,}")
    print(f"Split: {split_info['type']}")
    print(f"Pass rate: {ml_df[TARGET_COL].mean() * 100:.1f}%")

    return X_train, X_test, y_train, y_test, FEATURE_COLS, split_info


def build_pipeline() -> Pipeline:
    """Build preprocessing + Random Forest pipeline."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), MODEL_NUMERIC_FEATURES),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    return Pipeline(
        steps=[
            ("historical_rates", HistoricalRateEncoder()),
            ("preprocess", preprocessor),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=40,
                    max_depth=12,
                    min_samples_leaf=10,
                    random_state=42,
                    n_jobs=1,
                    class_weight="balanced",
                ),
            ),
        ]
    )


def train_model(X_train, y_train) -> Pipeline:
    """Train Random Forest classifier."""
    print("\nTraining Random Forest...")
    model = build_pipeline()
    model.fit(X_train, y_train)
    print("Model trained")
    return model


def summarize_fail_thresholds(
    y_test,
    y_prob,
    target_recalls: tuple[float, ...] = (0.60, 0.70, 0.80, 0.90),
) -> list[dict]:
    """Summarize precision/recall tradeoffs for the fail-risk score."""
    y_true = np.asarray(y_test, dtype=int)
    if len(np.unique(y_true)) < 2:
        return []

    fail_true = 1 - y_true
    fail_score = 1 - np.asarray(y_prob, dtype=float)
    fail_precision, fail_recall, fail_thresholds = precision_recall_curve(
        fail_true, fail_score
    )
    if len(fail_thresholds) == 0:
        return []

    threshold_df = pd.DataFrame({
        "threshold": fail_thresholds,
        "fail_precision": fail_precision[:-1],
        "fail_recall": fail_recall[:-1],
    })
    threshold_df["fail_f1"] = (
        2 * threshold_df["fail_precision"] * threshold_df["fail_recall"]
        / (threshold_df["fail_precision"] + threshold_df["fail_recall"])
    ).fillna(0)

    sorted_scores = np.sort(fail_score)
    risk_counts = len(sorted_scores) - np.searchsorted(
        sorted_scores, fail_thresholds, side="left"
    )
    threshold_df["predicted_risk_share"] = risk_counts / len(sorted_scores)

    rows = []
    for target_recall in target_recalls:
        candidates = threshold_df[threshold_df["fail_recall"] >= target_recall]
        if candidates.empty:
            continue
        best = candidates.sort_values(
            ["fail_precision", "threshold"], ascending=False
        ).iloc[0]
        rows.append({
            "min_fail_recall": float(target_recall),
            "threshold": float(best["threshold"]),
            "fail_precision": float(best["fail_precision"]),
            "fail_recall": float(best["fail_recall"]),
            "fail_f1": float(best["fail_f1"]),
            "predicted_risk_share": float(best["predicted_risk_share"]),
        })
    return rows


def summarize_probability_quality(
    y_true,
    y_prob,
    n_bins: int = 10,
) -> dict:
    """Summarize probability calibration quality for the pass probability."""
    y_arr = np.asarray(y_true, dtype=int)
    prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    if len(y_arr) == 0:
        return {}

    rows = []
    bins = np.linspace(0, 1, n_bins + 1)
    bin_ids = np.clip(np.digitize(prob, bins, right=True) - 1, 0, n_bins - 1)
    for bin_id in range(n_bins):
        mask = bin_ids == bin_id
        if not mask.any():
            continue
        rows.append({
            "bin": int(bin_id),
            "lower": float(bins[bin_id]),
            "upper": float(bins[bin_id + 1]),
            "count": int(mask.sum()),
            "predicted_pass_rate": float(prob[mask].mean()),
            "actual_pass_rate": float(y_arr[mask].mean()),
            "absolute_error": float(abs(prob[mask].mean() - y_arr[mask].mean())),
        })

    ece = 0.0
    for row in rows:
        ece += row["count"] / len(y_arr) * row["absolute_error"]

    return {
        "brier_score": float(brier_score_loss(y_arr, prob)),
        "log_loss": float(log_loss(y_arr, prob, labels=[0, 1])),
        "expected_calibration_error": float(ece),
        "calibration_bins": rows,
    }


def temporal_calibration_analysis(df: pd.DataFrame) -> dict | None:
    """
    Fit a temporal calibration check without using the final test year.

    With 2023-2025 data this trains a temporary model on 2023, fits an
    isotonic probability calibrator on 2024 predictions, and evaluates both
    raw and calibrated probabilities on 2025.
    """
    model_df = create_model_frame(df).dropna(subset=[TARGET_COL]).copy()
    years = sorted(int(y) for y in model_df["YV_AASTA"].dropna().unique())
    if len(years) < 3:
        return None

    train_years = years[:-2]
    calibration_year = years[-2]
    test_year = years[-1]

    train_df = model_df[model_df["YV_AASTA"].isin(train_years)]
    calibration_df = model_df[model_df["YV_AASTA"] == calibration_year]
    test_df = model_df[model_df["YV_AASTA"] == test_year]
    if train_df.empty or calibration_df.empty or test_df.empty:
        return None
    if (
        train_df[TARGET_COL].nunique() < 2
        or calibration_df[TARGET_COL].nunique() < 2
        or test_df[TARGET_COL].nunique() < 2
    ):
        return None

    print(
        "\nTemporal calibration check: "
        f"train={train_years}, calibration={calibration_year}, test={test_year}"
    )
    calibration_model = build_pipeline()
    calibration_model.fit(train_df[FEATURE_COLS], train_df[TARGET_COL])

    calibration_prob = calibration_model.predict_proba(calibration_df[FEATURE_COLS])[:, 1]
    test_prob_raw = calibration_model.predict_proba(test_df[FEATURE_COLS])[:, 1]

    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(calibration_prob, calibration_df[TARGET_COL].astype(int))
    test_prob_isotonic = isotonic.transform(test_prob_raw)

    raw_quality = summarize_probability_quality(test_df[TARGET_COL], test_prob_raw)
    calibrated_quality = summarize_probability_quality(test_df[TARGET_COL], test_prob_isotonic)

    result = {
        "method": "isotonic",
        "train_years": train_years,
        "calibration_year": int(calibration_year),
        "test_year": int(test_year),
        "raw_probability_quality": raw_quality,
        "calibrated_probability_quality": calibrated_quality,
        "raw_roc_auc": float(roc_auc_score(test_df[TARGET_COL], test_prob_raw)),
        "calibrated_roc_auc": float(roc_auc_score(test_df[TARGET_COL], test_prob_isotonic)),
    }
    result["brier_improvement"] = (
        raw_quality["brier_score"] - calibrated_quality["brier_score"]
    )
    result["log_loss_improvement"] = (
        raw_quality["log_loss"] - calibrated_quality["log_loss"]
    )
    result["ece_improvement"] = (
        raw_quality["expected_calibration_error"]
        - calibrated_quality["expected_calibration_error"]
    )

    print("Calibration quality:")
    print(
        pd.DataFrame([
            {"variant": "raw", **{k: raw_quality[k] for k in [
                "brier_score", "log_loss", "expected_calibration_error"
            ]}},
            {"variant": "isotonic", **{k: calibrated_quality[k] for k in [
                "brier_score", "log_loss", "expected_calibration_error"
            ]}},
        ]).round(4).to_string(index=False)
    )
    return result


def _feature_importance(model: Pipeline) -> pd.DataFrame:
    rf = model.named_steps["model"]
    feature_names = model.named_steps["preprocess"].get_feature_names_out()
    return (
        pd.DataFrame({"feature": feature_names, "importance": rf.feature_importances_})
        .sort_values("importance", ascending=True)
    )


def evaluate_model(model: Pipeline, X_test, y_test, feature_names: list) -> dict:
    """Evaluate model performance and generate reports."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    baseline_pred = np.ones_like(y_test)

    metrics = {
        "baseline_always_pass_accuracy": float(accuracy_score(y_test, baseline_pred)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
    }
    metrics["probability_quality"] = summarize_probability_quality(y_test, y_prob)
    metrics["fail_threshold_summary"] = summarize_fail_thresholds(y_test, y_prob)
    metrics["classification_report"] = classification_report(
        y_test,
        y_pred,
        target_names=["Failed", "Passed"],
        zero_division=0,
        output_dict=True,
    )

    print("\n=== Model Performance ===")
    print(f"Baseline always-pass accuracy: {metrics['baseline_always_pass_accuracy']:.3f}")
    print(f"Accuracy:  {metrics['accuracy']:.3f}")
    print(f"Balanced accuracy: {metrics['balanced_accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1 Score:  {metrics['f1']:.3f}")
    print(f"ROC AUC:   {metrics['roc_auc']:.3f}")
    print(f"Brier:     {metrics['probability_quality']['brier_score']:.3f}")
    print(f"Log loss:  {metrics['probability_quality']['log_loss']:.3f}")

    print("\nClassification Report:")
    print(classification_report(
        y_test,
        y_pred,
        target_names=["Failed", "Passed"],
        zero_division=0,
    ))
    if metrics["fail_threshold_summary"]:
        print("\nFail-risk threshold summary:")
        print(pd.DataFrame(metrics["fail_threshold_summary"]).round(3).to_string(index=False))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    cm = confusion_matrix(y_test, y_pred)
    importance = _feature_importance(model)
    top_importance = importance.tail(20)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        ax=axes[0],
        xticklabels=["Failed", "Passed"],
        yticklabels=["Failed", "Passed"],
    )
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].set_title("Confusion Matrix")

    axes[1].barh(top_importance["feature"], top_importance["importance"])
    axes[1].set_xlabel("Importance")
    axes[1].set_title("Top 20 Feature Importances")

    plt.tight_layout()
    plot_path = PROCESSED_DIR / "model_evaluation.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nOK Evaluation plots saved: {plot_path}")

    fpr, tpr, _ = roc_curve(y_test, y_prob)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(fpr, tpr, label=f"ROC AUC = {metrics['roc_auc']:.3f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend()
    roc_path = PROCESSED_DIR / "roc_curve.png"
    plt.savefig(roc_path, dpi=150, bbox_inches="tight")
    plt.close()

    metrics["feature_importance"] = importance.sort_values(
        "importance", ascending=False
    ).head(50).to_dict("records")

    return metrics


def _lookup_count(series: pd.Series, default: int = 0) -> dict:
    counts = series.dropna().astype(str).value_counts()
    if counts.empty:
        return {}
    return {key: {"sagedus": int(value)} for key, value in counts.items()}


def build_lookups(df: pd.DataFrame) -> dict:
    """Build target-free lookup metadata for the Streamlit prediction form."""
    model_df = create_model_frame(df)

    mark_lookup = _lookup_count(model_df["MARK"])
    mudel_lookup: dict[str, dict] = {}
    if {"MARK", "MUDEL"}.issubset(model_df.columns):
        counts = (
            model_df.dropna(subset=["MARK", "MUDEL"])
            .astype({"MARK": str, "MUDEL": str})
            .groupby(["MARK", "MUDEL"])
            .size()
            .sort_values(ascending=False)
        )
        for (mark, mudel), count in counts.items():
            mudel_lookup.setdefault(mark, {})[mudel] = {"sagedus": int(count)}

    category_options = sorted(model_df["KATEGOORIA"].dropna().astype(str).unique())
    body_type_options = sorted(model_df["KERETYYP"].dropna().astype(str).unique())
    station_code_options = sorted(model_df["PUNKTI_KOOD"].dropna().astype(str).unique())

    return {
        "mark_lookup": mark_lookup,
        "mudel_lookup": mudel_lookup,
        "category_options": category_options,
        "body_type_options": body_type_options,
        "station_code_options": station_code_options,
        "default_mark_frequency": int(model_df["MARK_SAGEDUS"].median()),
        "default_model_frequency": int(model_df["MUDEL_SAGEDUS"].median()),
        "latest_training_year": int(model_df["YV_AASTA"].max()),
    }


def save_model(
    model: Pipeline,
    metrics: dict,
    feature_names: list,
    df: pd.DataFrame | None = None,
    split_info: dict | None = None,
):
    """Save trained model and metadata."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "random_forest.pkl"
    tmp_model_path = model_path.with_suffix(".pkl.tmp")
    with open(tmp_model_path, "wb") as f:
        pickle.dump(model, f)
    os.replace(tmp_model_path, model_path)

    meta = {
        "model_type": "RandomForestClassifier Pipeline with leakage-safe historical rates",
        "features": feature_names,
        "numeric_features": NUMERIC_FEATURES,
        "model_numeric_features": MODEL_NUMERIC_FEATURES,
        "historical_rate_features": HISTORICAL_RATE_FEATURES,
        "historical_rate_specs": [
            {"feature": name, "source_columns": list(columns)}
            for name, columns in HISTORICAL_RATE_SPECS
        ],
        "categorical_features": CATEGORICAL_FEATURES,
        "metrics": {k: v for k, v in metrics.items() if k != "feature_importance"},
        "feature_importance": metrics.get("feature_importance", []),
        "split": split_info or {},
        "excluded_features": LEAKAGE_PRONE_FEATURES,
        "training_note": (
            "Full-dataset target-derived pass-rate features and station strictness are excluded. "
            "Smoothed historical fail-rate features are fitted inside the pipeline from training data only. "
            "Use fail_threshold_summary for risk-screening thresholds."
        ),
    }

    if df is not None:
        meta.update(build_lookups(df))
        print(
            "  Lookup: "
            f"{len(meta['mark_lookup'])} makes, "
            f"{sum(len(v) for v in meta['mudel_lookup'].values())} models"
        )

    meta_path = MODEL_DIR / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(meta), f, indent=2, ensure_ascii=False)

    print(f"\nOK Model saved: {model_path}")
    print(f"OK Metadata saved: {meta_path}")


def predict_single(model: Pipeline, feature_names: list, **kwargs) -> float:
    """Predict pass probability for a single vehicle."""
    row = pd.DataFrame([kwargs])[feature_names]
    return float(model.predict_proba(row)[0][1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the inspection outcome model.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=DEFAULT_YEARS,
        help="Years to train/evaluate, for example --years 2023 2024 2025",
    )
    parser.add_argument(
        "--max-rows-per-year",
        type=int,
        default=None,
        help="Optional row limit per year for quick checks.",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Read remote sources even if local cache files exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_df = load_years(
        args.years,
        max_rows_per_year=args.max_rows_per_year,
        prefer_cache=not args.remote,
    )
    cleaned_df = clean_inspections(raw_df)
    X_train, X_test, y_train, y_test, features, split_info = prepare_data(cleaned_df)
    model = train_model(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test, features)
    calibration_analysis = temporal_calibration_analysis(cleaned_df)
    if calibration_analysis is not None:
        metrics["calibration_analysis"] = calibration_analysis
    save_model(model, metrics, features, cleaned_df, split_info=split_info)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = PROCESSED_DIR / "model_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            _json_safe({k: v for k, v in metrics.items() if k != "feature_importance"}),
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"OK Metrics saved: {metrics_path}")
    print("\n=== Done ===")


if __name__ == "__main__":
    sys.modules.setdefault("src.prediction", sys.modules[__name__])
    HistoricalRateEncoder.__module__ = "src.prediction"
    main()
