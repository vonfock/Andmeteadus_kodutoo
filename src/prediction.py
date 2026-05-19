"""
Random Forest classifier for predicting roadworthiness inspection outcomes.

Predicts whether a vehicle will pass its first regular inspection (KORRALINE)
based on vehicle characteristics and inspection station.

Usage:
    python src/prediction.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve
)
from pathlib import Path
import json
import pickle

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"

# Features to use for prediction
FEATURE_COLS = [
    "VANUS",
    "VANUS_RUUT",
    "ON_VANA",
    "KUU_SIN",
    "KUU_COS",
    "MARK_SAGEDUS",
    "MARK_LABIMISE_MAAR",
    "MUDEL_SAGEDUS",
    "MUDEL_LABIMISE_MAAR",
    "KERETYYP_KOOD",
    "PUNKTI_RANGUS",
    "EELMISED_YV",
]

TARGET_COL = "LABIS_ESIMESEL"


def prepare_data(df: pd.DataFrame) -> tuple:
    """
    Prepare train/test split for the classifier.
    
    Returns (X_train, X_test, y_train, y_test)
    """
    # Only rows with target and all features present
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    ml_df = df.dropna(subset=available_features + [TARGET_COL]).copy()
    ml_df[TARGET_COL] = ml_df[TARGET_COL].astype(int)

    X = ml_df[available_features]
    y = ml_df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Dataset: {len(ml_df):,} rows")
    print(f"Features: {len(available_features)}")
    print(f"Train set: {len(X_train):,} | Test set: {len(X_test):,}")
    print(f"Pass rate: {y.mean() * 100:.1f}%")

    return X_train, X_test, y_train, y_test, available_features


def train_model(X_train, y_train) -> RandomForestClassifier:
    """Train Random Forest classifier."""
    print("\nTraining Random Forest...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",  # Handle class imbalance
    )
    model.fit(X_train, y_train)
    print("Model trained")
    return model


def evaluate_model(model, X_test, y_test, feature_names: list) -> dict:
    """
    Evaluate model performance and generate reports.
    
    Returns dict with all metrics.
    """
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    # Metrics
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_prob),
    }

    print(f"\n=== Model Performance ===")
    print(f"Accuracy:  {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1 Score:  {metrics['f1']:.3f}")
    print(f"ROC AUC:   {metrics['roc_auc']:.3f}")

    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=["Kukkus läbi", "Läbis"]))

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
                xticklabels=["Kukkus läbi", "Läbis"],
                yticklabels=["Kukkus läbi", "Läbis"])
    axes[0].set_xlabel("Ennustatud")
    axes[0].set_ylabel("Tegelik")
    axes[0].set_title("Segadusmatriks (Confusion Matrix)")

    # Feature importance
    importance = pd.DataFrame({
        "feature": feature_names,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=True)

    axes[1].barh(importance["feature"], importance["importance"])
    axes[1].set_xlabel("Olulisus (Importance)")
    axes[1].set_title("Tunnuste olulisus (Feature Importance)")

    plt.tight_layout()
    plot_path = PROCESSED_DIR / "model_evaluation.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nOK Evaluation plots saved: {plot_path}")

    # ROC Curve
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

    metrics["feature_importance"] = importance.to_dict("records")

    return metrics


def build_lookups(df: pd.DataFrame) -> tuple[dict, dict]:
    """Build mark and model lookup dicts from the feature dataframe."""
    mark_lookup = {}
    if "MARK" in df.columns and "MARK_SAGEDUS" in df.columns:
        for mark, grp in df.groupby("MARK"):
            if pd.notna(mark) and str(mark).strip():
                mark_lookup[str(mark)] = {
                    "sagedus": int(grp["MARK_SAGEDUS"].iloc[0]),
                    "labimise_maar": float(grp["MARK_LABIMISE_MAAR"].iloc[0]),
                }

    mudel_lookup: dict = {}
    if "MUDEL" in df.columns and "MUDEL_SAGEDUS" in df.columns:
        for (mark, mudel), grp in df.groupby(["MARK", "MUDEL"]):
            if pd.notna(mark) and pd.notna(mudel) and str(mark).strip() and str(mudel).strip():
                mark_key = str(mark)
                if mark_key not in mudel_lookup:
                    mudel_lookup[mark_key] = {}
                mudel_lookup[mark_key][str(mudel)] = {
                    "sagedus": int(grp["MUDEL_SAGEDUS"].iloc[0]),
                    "labimise_maar": float(grp["MUDEL_LABIMISE_MAAR"].iloc[0]),
                }

    return mark_lookup, mudel_lookup


def save_model(model, metrics: dict, feature_names: list, df: pd.DataFrame = None):
    """Save trained model and metadata."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "random_forest.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    meta = {
        "features": feature_names,
        "metrics": {k: v for k, v in metrics.items() if k != "feature_importance"},
        "feature_importance": metrics.get("feature_importance", []),
    }

    if df is not None:
        mark_lookup, mudel_lookup = build_lookups(df)
        meta["mark_lookup"] = mark_lookup
        meta["mudel_lookup"] = mudel_lookup
        print(f"  Lookup: {len(mark_lookup)} margid, {sum(len(v) for v in mudel_lookup.values())} mudelid")

    meta_path = MODEL_DIR / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\nOK Model saved: {model_path}")
    print(f"OK Metadata saved: {meta_path}")


def predict_single(model, feature_names: list, **kwargs) -> float:
    """
    Predict pass probability for a single vehicle.
    
    Example:
        predict_single(model, feature_names,
            VANUS=12, KERETYYP_KOOD=0, PUNKTI_RANGUS=25.0, ...)
    """
    row = pd.DataFrame([kwargs])[feature_names]
    prob = model.predict_proba(row)[0][1]
    return prob


if __name__ == "__main__":
    input_path = PROCESSED_DIR / "features.csv"
    if not input_path.exists():
        print(f"ERROR Feature data not found at {input_path}")
        print("  Run feature_engineering.py first.")
    else:
        df = pd.read_csv(input_path)
        X_train, X_test, y_train, y_test, features = prepare_data(df)
        model = train_model(X_train, y_train)
        metrics = evaluate_model(model, X_test, y_test, features)
        save_model(model, metrics, features, df)

        # Save metrics summary
        metrics_path = PROCESSED_DIR / "model_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(
                {k: v for k, v in metrics.items() if k != "feature_importance"},
                f, indent=2
            )
        print(f"\n=== Done ===")
