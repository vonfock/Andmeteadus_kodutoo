"""
K-Means clustering for inspection profile discovery.

Clusters inspection records by vehicle characteristics and station behaviour
to find hidden patterns (e.g. "new SUVs in lenient stations" vs "old sedans
in strict stations").

Usage:
    python src/clustering.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Features used for clustering
CLUSTER_FEATURES = [
    "VANUS",           # Vehicle age
    "KERETYYP_KOOD",   # Body type (encoded)
    "PUNKTI_RANGUS",   # Station strictness index
]


def prepare_clustering_data(df: pd.DataFrame) -> tuple:
    """
    Prepare data for clustering: select features, drop NaN, scale.
    
    Returns (scaled_data, scaler, clean_df)
    """
    # Use only rows that have all clustering features
    clean = df.dropna(subset=CLUSTER_FEATURES).copy()
    X = clean[CLUSTER_FEATURES].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print(f"Clustering data: {len(clean):,} rows, {len(CLUSTER_FEATURES)} features")
    return X_scaled, scaler, clean


def find_optimal_k(X: np.ndarray, k_range: range = range(2, 11)) -> dict:
    """
    Find optimal number of clusters using elbow method and silhouette score.
    
    Returns dict with inertia and silhouette scores for each k.
    """
    results = {"k": [], "inertia": [], "silhouette": []}

    print("\nFinding optimal k:")
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels)
        results["k"].append(k)
        results["inertia"].append(km.inertia_)
        results["silhouette"].append(sil)
        print(f"  k={k}: inertia={km.inertia_:.0f}, silhouette={sil:.3f}")

    return results


def plot_elbow(results: dict, save_path: Path = None):
    """Plot elbow curve and silhouette scores."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(results["k"], results["inertia"], "bo-")
    ax1.set_xlabel("Number of clusters (k)")
    ax1.set_ylabel("Inertia")
    ax1.set_title("Elbow Method")

    ax2.plot(results["k"], results["silhouette"], "ro-")
    ax2.set_xlabel("Number of clusters (k)")
    ax2.set_ylabel("Silhouette Score")
    ax2.set_title("Silhouette Analysis")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\n✓ Elbow plot saved: {save_path}")
    plt.close()


def run_clustering(df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """
    Run K-Means clustering and add cluster labels to DataFrame.
    
    Returns DataFrame with KLASTER column added.
    """
    X_scaled, scaler, clean_df = prepare_clustering_data(df)

    # Find optimal k
    results = find_optimal_k(X_scaled)
    plot_path = PROCESSED_DIR / "elbow_plot.png"
    plot_elbow(results, plot_path)

    # Run final clustering
    print(f"\nRunning K-Means with k={n_clusters}...")
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clean_df["KLASTER"] = km.fit_predict(X_scaled)

    # Describe each cluster
    print(f"\n=== Cluster Profiles ===")
    cluster_profiles = []
    for c in range(n_clusters):
        cluster_data = clean_df[clean_df["KLASTER"] == c]
        profile = {
            "cluster": c,
            "size": len(cluster_data),
            "pct": f"{len(cluster_data) / len(clean_df) * 100:.1f}%",
            "avg_age": cluster_data["VANUS"].mean(),
            "avg_strictness": cluster_data["PUNKTI_RANGUS"].mean(),
            "pass_rate": cluster_data["LABIS_ESIMESEL"].mean() * 100
            if "LABIS_ESIMESEL" in cluster_data.columns else None,
            "top_makes": cluster_data["MARK"].value_counts().head(3).to_dict()
            if "MARK" in cluster_data.columns else {},
        }
        cluster_profiles.append(profile)
        print(f"\n  Cluster {c} ({profile['pct']} of data):")
        print(f"    Avg age: {profile['avg_age']:.1f} years")
        print(f"    Avg station strictness: {profile['avg_strictness']:.1f}%")
        if profile["pass_rate"] is not None:
            print(f"    Pass rate: {profile['pass_rate']:.1f}%")
        print(f"    Top makes: {profile['top_makes']}")

    # Save profiles
    profiles_path = PROCESSED_DIR / "cluster_profiles.json"
    with open(profiles_path, "w", encoding="utf-8") as f:
        json.dump(cluster_profiles, f, indent=2, ensure_ascii=False, default=str)

    # Merge cluster labels back to original df
    df = df.merge(
        clean_df[["KLASTER"]],
        left_index=True, right_index=True,
        how="left"
    )

    return df


if __name__ == "__main__":
    input_path = PROCESSED_DIR / "features.csv"
    if not input_path.exists():
        print(f"✗ Feature data not found at {input_path}")
        print("  Run feature_engineering.py first.")
    else:
        df = pd.read_csv(input_path)
        df = run_clustering(df, n_clusters=4)
        output_path = PROCESSED_DIR / "clustered.csv"
        df.to_csv(output_path, index=False)
        print(f"\n✓ Clustered data saved: {output_path}")
