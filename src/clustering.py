"""
K-Means clustering for inspection profile discovery.

This script mirrors the unsupervised section in the grading notebook. It uses
only leakage-safe input features for clustering and uses the pass/fail target
only afterwards to describe the discovered profiles.

Usage:
    python src/clustering.py --years 2023 2024 2025
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).parent.parent
MPLCONFIG_DIR = PROJECT_ROOT / ".matplotlib"
MPLCONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR))
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from src.prediction import (
        DEFAULT_YEARS,
        TARGET_COL,
        clean_inspections,
        create_model_frame,
        load_years,
    )
except ModuleNotFoundError:
    from prediction import (
        DEFAULT_YEARS,
        TARGET_COL,
        clean_inspections,
        create_model_frame,
        load_years,
    )

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

CLUSTER_NUMERIC_FEATURES = [
    "VANUS",
    "KUU_SIN",
    "KUU_COS",
    "MARK_SAGEDUS",
    "MUDEL_SAGEDUS",
    "EELMISED_YV",
]
CLUSTER_CATEGORICAL_FEATURES = ["KATEGOORIA", "KERETYYP", "PUNKTI_KOOD"]
CLUSTER_FEATURES = CLUSTER_NUMERIC_FEATURES + CLUSTER_CATEGORICAL_FEATURES


def top_value(series: pd.Series) -> str:
    values = series.dropna().astype(str)
    if values.empty:
        return ""
    return str(values.value_counts().index[0])


def make_cluster_frame(df: pd.DataFrame, sample_size: int = 100_000) -> pd.DataFrame:
    """Clean, feature-engineer and sample data for K-Means."""
    model_df = create_model_frame(df)
    cluster_df = model_df.dropna(
        subset=[TARGET_COL, "VANUS", "KATEGOORIA", "KERETYYP", "PUNKTI_KOOD"]
    ).copy()
    if len(cluster_df) > sample_size:
        cluster_df = cluster_df.sample(n=sample_size, random_state=42).copy()
    return cluster_df


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                CLUSTER_NUMERIC_FEATURES,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CLUSTER_CATEGORICAL_FEATURES,
            ),
        ]
    )


def score_k_values(X_cluster, k_values: Iterable[int]) -> pd.DataFrame:
    """Compute inertia and silhouette on a bounded silhouette sample."""
    X_silhouette = X_cluster[: min(10_000, X_cluster.shape[0])]
    rows = []
    for k in k_values:
        km = KMeans(n_clusters=int(k), random_state=42, n_init=10)
        labels = km.fit_predict(X_cluster)
        rows.append({
            "k": int(k),
            "inertia": float(km.inertia_),
            "silhouette": float(
                silhouette_score(X_silhouette, labels[: X_silhouette.shape[0]])
            ),
        })
        print(f"k={k}: inertia={km.inertia_:.0f}, silhouette={rows[-1]['silhouette']:.3f}")
    return pd.DataFrame(rows)


def plot_scores(scores: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    sns.lineplot(data=scores, x="k", y="inertia", marker="o", ax=axes[0])
    axes[0].set_title("Elbow method")
    axes[0].set_xlabel("Number of clusters")
    axes[0].set_ylabel("Inertia")

    sns.lineplot(data=scores, x="k", y="silhouette", marker="o", ax=axes[1], color="#e15759")
    axes[1].set_title("Silhouette score")
    axes[1].set_xlabel("Number of clusters")
    axes[1].set_ylabel("Silhouette")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"OK Elbow/silhouette plot saved: {output_path}")


def profile_clusters(cluster_df: pd.DataFrame) -> list[dict]:
    profiles = []
    for cluster_id in sorted(cluster_df["KLASTER"].unique()):
        subset = cluster_df[cluster_df["KLASTER"] == cluster_id]
        profiles.append({
            "cluster": int(cluster_id),
            "size": int(len(subset)),
            "pct": round(len(subset) / len(cluster_df) * 100, 1),
            "avg_age": round(float(subset["VANUS"].mean()), 1),
            "pass_rate": round(float(subset[TARGET_COL].mean() * 100), 1),
            "top_category": top_value(subset["KATEGOORIA"]),
            "top_body_type": top_value(subset["KERETYYP"]),
            "top_station_code": top_value(subset["PUNKTI_KOOD"]),
            "top_make": top_value(subset["MARK"]),
        })
    return profiles


def run_clustering(
    df: pd.DataFrame,
    sample_size: int = 100_000,
    n_clusters: int = 2,
    k_min: int = 2,
    k_max: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Run leakage-safe K-Means and save profile artifacts."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    cluster_df = make_cluster_frame(df, sample_size=sample_size)
    print(f"Clustering sample: {len(cluster_df):,} rows")

    preprocessor = build_preprocessor()
    X_cluster = preprocessor.fit_transform(cluster_df[CLUSTER_FEATURES])

    scores = score_k_values(X_cluster, range(k_min, k_max + 1))
    plot_scores(scores, PROCESSED_DIR / "elbow_plot.png")

    print(f"\nRunning K-Means with k={n_clusters}...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_df["KLASTER"] = kmeans.fit_predict(X_cluster)
    profiles = profile_clusters(cluster_df)

    with open(PROCESSED_DIR / "cluster_profiles.json", "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    metadata = {
        "sample_size": int(len(cluster_df)),
        "selected_k": int(n_clusters),
        "numeric_features": CLUSTER_NUMERIC_FEATURES,
        "categorical_features": CLUSTER_CATEGORICAL_FEATURES,
        "excluded_from_clustering": [
            TARGET_COL,
            "YLEVAATUSOTSUS",
            "RIKKED",
            "PUNKTI_RANGUS",
            "MARK_LABIMISE_MAAR",
            "MUDEL_LABIMISE_MAAR",
        ],
        "k_scores": scores.to_dict("records"),
    }
    with open(PROCESSED_DIR / "cluster_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    cluster_df[["KLASTER"]].to_csv(PROCESSED_DIR / "clustered.csv", index=True)

    print("\n=== Cluster profiles ===")
    print(pd.DataFrame(profiles).to_string(index=False))
    print(f"\nOK Profiles saved: {PROCESSED_DIR / 'cluster_profiles.json'}")
    print(f"OK Metadata saved: {PROCESSED_DIR / 'cluster_metadata.json'}")
    return cluster_df, scores, profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run leakage-safe K-Means clustering.")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--sample-size", type=int, default=100_000)
    parser.add_argument("--clusters", type=int, default=2)
    parser.add_argument("--remote", action="store_true", help="Read remote URLs even if cache exists")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_df = load_years(args.years, prefer_cache=not args.remote)
    clean_df = clean_inspections(raw_df)
    run_clustering(clean_df, sample_size=args.sample_size, n_clusters=args.clusters)


if __name__ == "__main__":
    main()
