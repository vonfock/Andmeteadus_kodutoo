"""Local cache and validation helpers for yearly inspection CSVs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd
import requests

try:
    from src.defects import VALID_SEVERITIES, split_rikked_entries
    from src.year_sources import available_years, get_year_url
except ModuleNotFoundError:
    from defects import VALID_SEVERITIES, split_rikked_entries
    from year_sources import available_years, get_year_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

VALIDATION_CSV_PATH = PROCESSED_DATA_DIR / "data_validation.csv"
VALIDATION_JSON_PATH = PROCESSED_DATA_DIR / "data_validation.json"


def cached_year_path(year: int) -> Path:
    """Return the expected local cache path for a yearly CSV."""
    return CACHE_DIR / f"yv_{year}.csv"


def has_cached_year(year: int) -> bool:
    """Return True when a non-empty local cache file exists."""
    path = cached_year_path(year)
    return path.exists() and path.stat().st_size > 0


def source_for_year(year: int, prefer_cache: bool = True) -> str:
    """Return local cache path when available, otherwise the remote URL."""
    if prefer_cache and has_cached_year(year):
        return cached_year_path(year).resolve().as_posix()
    return get_year_url(year)


def _duckdb_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def source_list_sql(years: Iterable[int], prefer_cache: bool = True) -> str:
    """Return a DuckDB list literal of sources for read_csv_auto."""
    sources = [_duckdb_literal(source_for_year(int(year), prefer_cache)) for year in sorted(years)]
    return "[" + ", ".join(sources) + "]"


def download_year(year: int, force: bool = False) -> Path:
    """Download one yearly CSV into data/cache/ and return the local path."""
    target = cached_year_path(year)
    if target.exists() and not force:
        return target

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(".csv.tmp")
    url = get_year_url(year)

    with requests.get(url, stream=True, timeout=(10, 180)) as response:
        response.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    if tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded empty file for {year}.")

    tmp_path.replace(target)
    return target


def build_cache(years: Iterable[int], force: bool = False) -> list[Path]:
    """Download missing yearly CSVs to the local cache."""
    cached_paths = []
    for year in sorted(int(y) for y in years):
        path = cached_year_path(year)
        if path.exists() and not force:
            print(f"{year}: cache exists at {path}")
        else:
            print(f"{year}: downloading to {path}")
        cached_paths.append(download_year(year, force=force))
    return cached_paths


def _read_known_defect_ids() -> set[int]:
    rike_path = RAW_DATA_DIR / "rike.csv"
    if not rike_path.exists():
        return set()

    df = pd.read_csv(rike_path, dtype=str)
    if "ID" not in df.columns:
        return set()

    ids = pd.to_numeric(df["ID"], errors="coerce").dropna().astype(int)
    return set(ids.tolist())


def _read_scalar_summary(year: int, source: str) -> dict:
    literal = _duckdb_literal(source)
    query = f"""
        WITH raw AS (
            SELECT *
            FROM read_csv_auto({literal}, delim=',', header=true, encoding='utf-8', all_varchar=true)
        ),
        typed AS (
            SELECT
                *,
                TRY_CAST(SUBSTR(YV_KUUPAEV, 1, 4) AS INTEGER) AS yv_aasta,
                TRY_CAST(ESMANE_REG_AASTA AS INTEGER) AS reg_aasta
            FROM raw
        )
        SELECT
            COUNT(*) AS rows_total,
            SUM(CASE WHEN YLEVAATUSLIIK = 'KORRALINE' THEN 1 ELSE 0 END) AS regular_rows,
            SUM(CASE WHEN YLEVAATUSLIIK = 'KORRALINE'
                      AND YLEVAATUSOTSUS IN ('KORRAS', 'KORDUVALE')
                     THEN 1 ELSE 0 END) AS target_rows,
            SUM(CASE WHEN YLEVAATUSLIIK = 'KORRALINE'
                      AND YLEVAATUSOTSUS NOT IN ('KORRAS', 'KORDUVALE')
                     THEN 1 ELSE 0 END) AS regular_other_decision_rows,
            SUM(CASE WHEN SOIDUK_ID IS NULL OR TRIM(SOIDUK_ID) = '' THEN 1 ELSE 0 END) AS missing_vehicle_id_rows,
            SUM(CASE WHEN MARK IS NULL OR TRIM(MARK) = '' THEN 1 ELSE 0 END) AS missing_mark_rows,
            SUM(CASE WHEN reg_aasta IS NULL THEN 1 ELSE 0 END) AS invalid_reg_year_rows,
            SUM(CASE WHEN yv_aasta IS NOT NULL AND reg_aasta IS NOT NULL
                      AND (yv_aasta - reg_aasta < 0 OR yv_aasta - reg_aasta > 100)
                     THEN 1 ELSE 0 END) AS invalid_age_rows,
            MIN(yv_aasta - reg_aasta) AS min_vehicle_age,
            MAX(yv_aasta - reg_aasta) AS max_vehicle_age,
            SUM(CASE WHEN RIKKED IS NOT NULL AND TRIM(RIKKED) != '' THEN 1 ELSE 0 END) AS rikked_nonempty_rows
        FROM typed
    """
    row = duckdb.sql(query).df().iloc[0].to_dict()
    return {key: _python_scalar(value) for key, value in row.items()}


def _python_scalar(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _read_rikked_values(source: str) -> pd.Series:
    literal = _duckdb_literal(source)
    return duckdb.sql(f"""
        SELECT RIKKED
        FROM read_csv_auto({literal}, delim=',', header=true, encoding='utf-8', all_varchar=true)
        WHERE RIKKED IS NOT NULL AND TRIM(RIKKED) != ''
    """).df()["RIKKED"]


def _defect_summary(source: str, known_defect_ids: set[int]) -> dict:
    values = _read_rikked_values(source)
    parsed_defects = 0
    malformed_entries = 0
    unknown_severity_entries = 0
    defect_ids: set[int] = set()

    for value in values:
        for entry in split_rikked_entries(value):
            if ":" not in entry:
                malformed_entries += 1
                continue

            severity, defect_id_raw = entry.split(":", 1)
            severity = severity.strip().upper()
            if severity not in VALID_SEVERITIES:
                unknown_severity_entries += 1
                continue

            try:
                defect_id = int(defect_id_raw.strip())
            except ValueError:
                malformed_entries += 1
                continue

            parsed_defects += 1
            defect_ids.add(defect_id)

    missing_ids = defect_ids - known_defect_ids if known_defect_ids else set()
    return {
        "parsed_defects": parsed_defects,
        "malformed_defect_entries": malformed_entries,
        "unknown_severity_entries": unknown_severity_entries,
        "unique_defect_ids": len(defect_ids),
        "defect_ids_missing_from_rike": len(missing_ids) if known_defect_ids else None,
    }


def validate_year(year: int, prefer_cache: bool = True) -> dict:
    """Validate one year and return a summary dict."""
    source = source_for_year(year, prefer_cache=prefer_cache)
    known_defect_ids = _read_known_defect_ids()
    summary = {
        "year": year,
        "source": "cache" if source == cached_year_path(year).resolve().as_posix() else "remote",
        "cached": has_cached_year(year),
    }
    summary.update(_read_scalar_summary(year, source))
    summary.update(_defect_summary(source, known_defect_ids))
    return summary


def validate_years(years: Iterable[int], prefer_cache: bool = True) -> pd.DataFrame:
    """Validate multiple years and save CSV/JSON reports."""
    rows = [validate_year(int(year), prefer_cache=prefer_cache) for year in sorted(years)]
    df = pd.DataFrame(rows)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(VALIDATION_CSV_PATH, index=False)
    with open(VALIDATION_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    return df


def _parse_year_args(values: list[int] | None, use_all: bool) -> list[int]:
    if use_all:
        return available_years()
    if values:
        return sorted(set(values))
    return [max(available_years())]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local CSV cache and data validation reports.")
    parser.add_argument("--years", nargs="+", type=int, help="Years to process, for example --years 2023 2024 2025")
    parser.add_argument("--all", action="store_true", help="Process all known years")
    parser.add_argument("--force", action="store_true", help="Redownload cache files even when they already exist")
    parser.add_argument("--validate-only", action="store_true", help="Skip downloading and only validate available sources")
    parser.add_argument("--remote", action="store_true", help="Validate remote URLs even if cache files exist")
    args = parser.parse_args()

    years = _parse_year_args(args.years, args.all)
    if not args.validate_only:
        build_cache(years, force=args.force)

    report = validate_years(years, prefer_cache=not args.remote)
    print(report.to_string(index=False))
    print(f"\nValidation CSV: {VALIDATION_CSV_PATH}")
    print(f"Validation JSON: {VALIDATION_JSON_PATH}")


if __name__ == "__main__":
    main()
