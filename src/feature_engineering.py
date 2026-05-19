"""
Feature engineering for roadworthiness inspection prediction.

Creates features for K-Means clustering and Random Forest classification.

Usage:
    python src/feature_engineering.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def create_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create feature matrix for machine learning.
    
    Input: cleaned DataFrame from data_cleaner.py
    Output: DataFrame with engineered features, ready for modelling
    """
    print("=== Feature Engineering ===\n")

    # Work with regular inspections only (where target variable exists)
    ml_df = df[df["LABIS_ESIMESEL"].notna()].copy()
    print(f"Regular inspections with target: {len(ml_df):,}")

    # Drop rows missing critical features
    required = ["VANUS", "MARK", "KATEGOORIA", "KERETYYP"]
    ml_df = ml_df.dropna(subset=[c for c in required if c in ml_df.columns])
    print(f"After dropping rows with missing features: {len(ml_df):,}")

    # --- Feature: Vehicle age ---
    # Already computed in cleaning step as VANUS

    # --- Feature: Inspection month (seasonality) ---
    if "YV_KUU" in ml_df.columns:
        ml_df["KUU_SIN"] = np.sin(2 * np.pi * ml_df["YV_KUU"] / 12)
        ml_df["KUU_COS"] = np.cos(2 * np.pi * ml_df["YV_KUU"] / 12)

    # --- Feature: Brand frequency encoding ---
    brand_counts = ml_df["MARK"].value_counts()
    ml_df["MARK_SAGEDUS"] = ml_df["MARK"].map(brand_counts)

    # --- Feature: Brand pass rate (target encoding with smoothing) ---
    global_pass_rate = ml_df["LABIS_ESIMESEL"].mean()
    brand_stats = ml_df.groupby("MARK").agg(
        mark_kokku=("LABIS_ESIMESEL", "count"),
        mark_labis=("LABIS_ESIMESEL", "mean")
    )
    # Smoothing: blend brand rate with global rate, weight by sample size
    smoothing_factor = 100  # minimum samples for full trust in brand rate
    brand_stats["MARK_LABIMISE_MAAR"] = (
        (brand_stats["mark_labis"] * brand_stats["mark_kokku"] +
         global_pass_rate * smoothing_factor) /
        (brand_stats["mark_kokku"] + smoothing_factor)
    )
    ml_df = ml_df.merge(
        brand_stats[["MARK_LABIMISE_MAAR"]],
        left_on="MARK", right_index=True, how="left"
    )

    # --- Feature: Model frequency encoding ---
    if "MUDEL" in ml_df.columns:
        mudel_counts = ml_df["MUDEL"].value_counts()
        ml_df["MUDEL_SAGEDUS"] = ml_df["MUDEL"].map(mudel_counts).fillna(0)

        mudel_stats = ml_df.groupby("MUDEL").agg(
            mudel_kokku=("LABIS_ESIMESEL", "count"),
            mudel_labis=("LABIS_ESIMESEL", "mean")
        )
        mudel_stats["MUDEL_LABIMISE_MAAR"] = (
            (mudel_stats["mudel_labis"] * mudel_stats["mudel_kokku"] +
             global_pass_rate * smoothing_factor) /
            (mudel_stats["mudel_kokku"] + smoothing_factor)
        )
        ml_df = ml_df.merge(
            mudel_stats[["MUDEL_LABIMISE_MAAR"]],
            left_on="MUDEL", right_index=True, how="left"
        )

    # --- Feature: Body type encoding ---
    body_map = {
        "SEDAAN": 0, "UNIVERSAAL": 1, "LUUKPÄRA": 2,
        "MAHTUNIVERSAAL": 3, "KAUBIK": 4, "KUPEE": 5,
        "LAHTINE": 6, "PIKAP": 7, "MOOTORRATAS": 8,
        "MITMEOTSTARBELINE SÕIDUK": 9, "MADEL": 10,
        "ELAMU": 11, "SADUL": 12, "PAADIVEOK": 13,
        "KVADRIK": 14,
    }
    if "KERETYYP" in ml_df.columns:
        ml_df["KERETYYP_KOOD"] = ml_df["KERETYYP"].map(body_map)
        # For unknown body types, use -1
        ml_df["KERETYYP_KOOD"] = ml_df["KERETYYP_KOOD"].fillna(-1).astype(int)

    # --- Feature: Vehicle category group ---
    # M1 = passenger car, N1 = light commercial, etc.
    if "KATEGOORIA" in ml_df.columns:
        ml_df["KAT_GRUPP"] = ml_df["KATEGOORIA"].str.extract(r"^([A-Z]+)", expand=False)

    # --- Feature: Station strictness ---
    # Already computed in cleaning step as PUNKTI_RANGUS

    # --- Feature: Previous inspection count per vehicle ---
    if "SOIDUK_ID" in ml_df.columns:
        vehicle_counts = ml_df.groupby("SOIDUK_ID").cumcount()
        ml_df["EELMISED_YV"] = vehicle_counts

    # --- Feature: Age squared (non-linear age effect) ---
    if "VANUS" in ml_df.columns:
        ml_df["VANUS_RUUT"] = ml_df["VANUS"] ** 2

    # --- Feature: Is old vehicle (> 10 years) ---
    if "VANUS" in ml_df.columns:
        ml_df["ON_VANA"] = (ml_df["VANUS"] > 10).astype(int)

    print(f"\nCreated features:")
    feature_cols = [
        "VANUS", "VANUS_RUUT", "ON_VANA",
        "KUU_SIN", "KUU_COS",
        "MARK_SAGEDUS", "MARK_LABIMISE_MAAR",
        "MUDEL_SAGEDUS", "MUDEL_LABIMISE_MAAR",
        "KERETYYP_KOOD",
        "PUNKTI_RANGUS",
        "EELMISED_YV",
    ]
    for col in feature_cols:
        if col in ml_df.columns:
            non_null = ml_df[col].notna().sum()
            print(f"  • {col}: {non_null:,} non-null values")

    return ml_df


def get_feature_columns() -> list:
    """Return the list of feature column names for modelling."""
    return [
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


if __name__ == "__main__":
    input_path = PROCESSED_DIR / "cleaned.csv"
    if not input_path.exists():
        print(f"ERROR Cleaned data not found at {input_path}")
        print("  Run data_cleaner.py first.")
    else:
        df = pd.read_csv(input_path)
        ml_df = create_ml_features(df)
        output_path = PROCESSED_DIR / "features.csv"
        ml_df.to_csv(output_path, index=False)
        print(f"\nOK Feature matrix saved: {output_path} ({len(ml_df):,} rows)")
