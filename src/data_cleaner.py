"""
Clean and preprocess roadworthiness inspection data.

Handles:
- Mojibake encoding fixes (Latin-1 misread as UTF-8)
- Missing value handling
- Data type conversions
- RIKKED (defects) column parsing
- Joining with rike.csv defect codes

Usage:
    python src/data_cleaner.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


# --- Encoding fixes ---


def fix_mojibake(text: str) -> str:
    """
    Fix mojibake encoding issues.

    The data appears to be UTF-8 content that was misread as Latin-1,
    producing patterns like: TÃ¤hva → Tähva, Ãœlevaatus → Ülevaatus

    Strategy: try to re-encode from latin-1 back to utf-8.
    """
    if not isinstance(text, str):
        return text
    try:
        # Try to reverse the mojibake: encode as latin-1, decode as utf-8
        fixed = text.encode("latin-1").decode("utf-8")
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        # If it fails, the text is probably already correct
        return text


def fix_encoding_in_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply mojibake fix to all string columns."""
    text_columns = [
        "TEHNOYLEVAATUSPUNKT",
        "TOOTAJA",
        "MARK",
        "MUDEL",
        "KERETYYP",
        "YLEVAATUSLIIK",
        "YLEVAATUSOTSUS",
        "RIKKED",
    ]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(fix_mojibake)
    return df


# --- Data type conversions ---


def convert_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns to appropriate data types."""
    # Integer columns
    int_cols = ["SOIDUK_ID", "ESMANE_REG_AASTA"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # Keep as float to preserve NaN, convert to Int64 (nullable int)
            df[col] = df[col].astype("Int64")

    # Parse inspection date (YYYY-MM format)
    if "YV_KUUPAEV" in df.columns:
        df["YV_AASTA"] = df["YV_KUUPAEV"].str[:4].astype("Int64")
        df["YV_KUU"] = df["YV_KUUPAEV"].str[5:7].astype("Int64")

    return df


# --- Vehicle age calculation ---


def add_vehicle_age(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate vehicle age at time of inspection."""
    if "YV_AASTA" in df.columns and "ESMANE_REG_AASTA" in df.columns:
        df["VANUS"] = df["YV_AASTA"] - df["ESMANE_REG_AASTA"]
        # Remove nonsensical ages (negative or extremely old)
        df.loc[df["VANUS"] < 0, "VANUS"] = pd.NA
        df.loc[df["VANUS"] > 100, "VANUS"] = pd.NA
    return df


# --- Defect (RIKKED) parsing ---


def parse_rikked(rikked_str: str) -> list:
    """
    Parse the RIKKED column into a list of (severity, defect_id) tuples.

    Input format examples:
        "VO:100101460"           → [("VO", 100101460)]
        "OV:100103882"           → [("OV", 100103882)]
        "VO:100101460,OV:100103882" → [("VO", 100101460), ("OV", 100103882)]
        ""  or NaN               → []

    Severity levels:
        VO  = VäheOluline (minor)
        OV  = Oluline Viga (significant)
        EOV = Eriti Ohtlik Viga (dangerous)
    """
    if not isinstance(rikked_str, str) or rikked_str.strip() == "":
        return []

    defects = []
    # Split by common delimiters (newline, comma, semicolon)
    parts = rikked_str.replace("\n", ",").replace(";", ",").split(",")
    for part in parts:
        part = part.strip()
        if ":" in part:
            severity, defect_id = part.split(":", 1)
            severity = severity.strip()
            try:
                defect_id = int(defect_id.strip())
                defects.append((severity, defect_id))
            except ValueError:
                continue
    return defects


def expand_defects(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create additional columns from parsed defects:
    - RIKETE_ARV: total number of defects
    - VO_ARV: number of minor defects
    - OV_ARV: number of significant defects
    - EOV_ARV: number of dangerous defects
    - RIKE_IDS: list of defect IDs (for joining with rike.csv)
    """
    parsed = df["RIKKED"].apply(parse_rikked)

    df["RIKETE_ARV"] = parsed.apply(len)
    df["VO_ARV"] = parsed.apply(lambda x: sum(1 for s, _ in x if s == "VO"))
    df["OV_ARV"] = parsed.apply(lambda x: sum(1 for s, _ in x if s == "OV"))
    df["EOV_ARV"] = parsed.apply(lambda x: sum(1 for s, _ in x if s == "EOV"))
    df["RIKE_IDS"] = parsed.apply(lambda x: [did for _, did in x])

    return df


# --- Target variable ---


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create binary target variable for ML:
    LABIS_ESIMESEL = 1 if the vehicle passed on first regular inspection, 0 otherwise.

    Only considers KORRALINE (regular) inspections.
    """
    # Filter: only regular inspections have a meaningful "first-time pass"
    df["LABIS_ESIMESEL"] = pd.NA
    mask_regular = df["YLEVAATUSLIIK"] == "KORRALINE"
    df.loc[mask_regular & (df["YLEVAATUSOTSUS"] == "KORRAS"), "LABIS_ESIMESEL"] = 1
    df.loc[mask_regular & (df["YLEVAATUSOTSUS"] == "KORDUVALE"), "LABIS_ESIMESEL"] = 0
    df["LABIS_ESIMESEL"] = df["LABIS_ESIMESEL"].astype("Int64")

    return df


# --- Missing values ---


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values:
    - Rows missing SOIDUK_ID, MARK, or ESMANE_REG_AASTA are flagged but kept
    - A column ANDMED_PUUDULIKUD flags incomplete rows
    """
    critical_cols = ["SOIDUK_ID", "MARK", "ESMANE_REG_AASTA"]
    existing_critical = [c for c in critical_cols if c in df.columns]
    df["ANDMED_PUUDULIKUD"] = df[existing_critical].isna().any(axis=1).astype(int)

    missing_pct = df["ANDMED_PUUDULIKUD"].mean() * 100
    print(f"  Rows with missing critical data: {missing_pct:.1f}%")

    return df


# --- Station strictness index ---


def add_station_strictness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate historical fail rate per inspection station.
    PUNKTI_RANGUS = percentage of KORRALINE inspections that result in KORDUVALE.
    """
    regular = df[df["YLEVAATUSLIIK"] == "KORRALINE"].copy()
    if len(regular) == 0:
        return df

    station_stats = (
        regular.groupby("PUNKTI_KOOD")
        .agg(
            kokku=("YLEVAATUSOTSUS", "count"),
            kukkus_labi=("YLEVAATUSOTSUS", lambda x: (x == "KORDUVALE").sum()),
        )
        .reset_index()
    )

    station_stats["PUNKTI_RANGUS"] = (
        station_stats["kukkus_labi"] / station_stats["kokku"] * 100
    ).round(2)

    # Only keep stations with enough data (at least 50 inspections)
    station_stats = station_stats[station_stats["kokku"] >= 50]

    df = df.merge(
        station_stats[["PUNKTI_KOOD", "PUNKTI_RANGUS"]], on="PUNKTI_KOOD", how="left"
    )

    return df


# --- Main pipeline ---


def load_rike_table() -> pd.DataFrame:
    """Load the defect codes lookup table."""
    rike_path = RAW_DIR / "rike.csv"
    if not rike_path.exists():
        print(f"  ⚠ rike.csv not found at {rike_path}")
        return pd.DataFrame()

    df = pd.read_csv(rike_path, dtype=str)
    # Fix encoding in defect descriptions too
    if "NIMETUS" in df.columns:
        df["NIMETUS"] = df["NIMETUS"].apply(fix_mojibake)
    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    return df


def clean_data(input_path: Path = None) -> pd.DataFrame:
    """
    Run the full cleaning pipeline.

    Returns cleaned DataFrame and saves to data/processed/cleaned.csv
    """
    if input_path is None:
        input_path = PROCESSED_DIR / "combined_raw.csv"

    print(f"=== Data Cleaning Pipeline ===\n")
    print(f"Reading: {input_path}")
    df = pd.read_csv(input_path, dtype=str)
    print(f"  Rows: {len(df):,}")

    print("\n1. Fixing encoding...")
    df = fix_encoding_in_dataframe(df)

    print("2. Converting data types...")
    df = convert_types(df)

    print("3. Calculating vehicle age...")
    df = add_vehicle_age(df)

    print("4. Parsing defects...")
    df = expand_defects(df)

    print("5. Creating target variable...")
    df = add_target(df)

    print("6. Handling missing values...")
    df = handle_missing_values(df)

    print("7. Calculating station strictness...")
    df = add_station_strictness(df)

    # Save
    output_path = PROCESSED_DIR / "cleaned.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Saved cleaned data: {output_path} ({len(df):,} rows)")

    # Summary
    print(f"\n=== Cleaning Summary ===")
    print(f"Total rows: {len(df):,}")
    if "VANUS" in df.columns:
        print(f"Vehicle age range: {df['VANUS'].min()} – {df['VANUS'].max()}")
    if "LABIS_ESIMESEL" in df.columns:
        pass_rate = df["LABIS_ESIMESEL"].mean()
        if pass_rate is not pd.NA:
            print(f"First-time pass rate (regular): {pass_rate * 100:.1f}%")
    print(f"Defects found in {(df['RIKETE_ARV'] > 0).sum():,} inspections")

    return df


if __name__ == "__main__":
    clean_data()
