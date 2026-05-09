"""
DuckDB-based data loader for Estonian roadworthiness inspection data.
All heavy aggregations happen at query time — only small result sets enter pandas.

RIKKED column format: "VO:100101460,OV:100103882"
  Severity prefixes: VO = minor, OV = significant, EOV = dangerous
  Everything after the colon is the defect ID (links to rike.csv)
"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

# ── Encoding fix (mirrors data_cleaner.fix_mojibake) ─────────────────────────


def _fix_encoding(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


YEAR_URLS = {
    2010: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/9b2d3dbe-e35c-4b5f-baed-6990baa408d0/download-s3",
    2011: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/5139abc3-6823-4121-8d2c-0c82928ac8ac/download-s3",
    2012: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/53f52202-e94e-4cb8-9149-4e311e6f2fdb/download-s3",
    2013: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/3f859ecc-7296-4b9c-ae9b-625b95c90ad9/download-s3",
    2014: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/10103f5a-0b6d-46fc-bd16-99a5c433625e/download-s3",
    2015: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/788a9115-a5da-4f47-bbcc-c1c3b644d3b3/download-s3",
    2016: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/f4f0b51e-8343-4832-9c07-4c04448b8f21/download-s3",
    2017: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/b5a08ea9-0fa8-4cb5-b0bc-7109571d8de4/download-s3",
    2018: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/2d018cd8-f3d7-4242-8514-99633120992a/download-s3",
    2019: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/7ba50767-9844-40bb-8561-af89b634e201/download-s3",
    2020: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/6371e8dc-9906-4555-af9f-f927f2ccf938/download-s3",
    2021: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/f3fe9ef1-897c-45b3-b2dd-908b810aae9c/download-s3",
    2022: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/ba317d52-71b7-473d-bc87-aec0cde38434/download-s3",
    2023: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/1943aed4-8e53-4e70-9946-7fc8ad1f7dfe/download-s3",
    2024: "https://andmed.eesti.ee/api/datasets/ae47fec7-63d0-4b7a-969b-fbdfed21d52a/files/af5b081a-3db1-495d-90f3-c334a860938a/download-s3",
    2025: "https://pilv.transpordiamet.ee/s/Iiee4OAYFq4lT1v/download?path=%2F&files=yv_2025.csv",
}

# ── Paths ─────────────────────────────────────────────────────────────────────

# ── Project paths ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# ── Metadata / lookup file paths ─────────────────────────────────────────────

RIKE_PATH = RAW_DATA_DIR / "rike.csv"

RIKE_METADATA_PATH = RAW_DATA_DIR / "rike_metadata.csv"

YV_METADATA_PATH = RAW_DATA_DIR / "YV-metadata.json"

# ── Safe loading helpers ─────────────────────────────────────────────────────


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _safe_read_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── Metadata / lookup tables ─────────────────────────────────────────────────

rike_df = _safe_read_csv(RIKE_PATH)
if not rike_df.empty and "NIMETUS" in rike_df.columns:
    rike_df["NIMETUS"] = rike_df["NIMETUS"].apply(_fix_encoding)

rike_metadata_df = _safe_read_csv(RIKE_METADATA_PATH)

yv_metadata = _safe_read_json(YV_METADATA_PATH)

# Pre-build rike ID → name lookup (TYYP=NIMETUS rows, keyed by string ID)
_RIKE_LOOKUP: dict = {}
if not rike_df.empty and {"ID", "NIMETUS", "TYYP"}.issubset(rike_df.columns):
    _nimetus = rike_df[rike_df["TYYP"] == "NIMETUS"][["ID", "NIMETUS"]].dropna()
    _RIKE_LOOKUP = dict(zip(_nimetus["ID"].astype(str), _nimetus["NIMETUS"]))


def get_available_years() -> list:
    return sorted(YEAR_URLS.keys())


def get_url(year: int) -> str:
    if year not in YEAR_URLS:
        raise ValueError(f"No URL for year {year}.")
    return YEAR_URLS[year]


def _urls_list(years: list) -> str:
    urls = [get_url(y) for y in sorted(years)]
    quoted = ", ".join(f"'{u}'" for u in urls)
    return f"[{quoted}]"


# ── Q1: Top 3 marks + top 5 models each — summed across selected years ────────


@st.cache_data(show_spinner=False)
def q_top_mark_and_models(years: list) -> tuple:
    urls = _urls_list(years)
    mark_df = duckdb.sql(f"""
        SELECT MARK, COUNT(*) AS arv
        FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
        WHERE MARK IS NOT NULL AND MARK != ''
        GROUP BY MARK
        ORDER BY arv DESC
        LIMIT 3
    """).df()

    models_df = duckdb.sql(f"""
        WITH top_marks AS (
            SELECT MARK
            FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
            WHERE MARK IS NOT NULL AND MARK != ''
            GROUP BY MARK
            ORDER BY COUNT(*) DESC
            LIMIT 3
        ),
        model_counts AS (
            SELECT d.MARK, d.MUDEL, COUNT(*) AS arv
            FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8') d
            INNER JOIN top_marks t ON d.MARK = t.MARK
            WHERE d.MUDEL IS NOT NULL AND d.MUDEL != ''
            GROUP BY d.MARK, d.MUDEL
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY MARK ORDER BY arv DESC) AS rnk
            FROM model_counts
        )
        SELECT MARK, MUDEL, arv FROM ranked
        WHERE rnk <= 5 ORDER BY MARK, rnk
    """).df()

    return mark_df, models_df


# ── Q2a: Station strictness ───────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def q_station_strictness(years: list) -> pd.DataFrame:
    urls = _urls_list(years)
    return duckdb.sql(f"""
        SELECT
            TEHNOYLEVAATUSPUNKT                                     AS jaam,
            PUNKTI_KOOD                                             AS jaama_kood,
            COUNT(*)                                                AS kokku,
            SUM(CASE WHEN YLEVAATUSOTSUS='KORRAS'    THEN 1 ELSE 0 END) AS labis_esimesel,
            SUM(CASE WHEN YLEVAATUSOTSUS='KORDUVALE' THEN 1 ELSE 0 END) AS kukkus_esimesel,
            ROUND(100.0 *
                SUM(CASE WHEN YLEVAATUSOTSUS='KORRAS' THEN 1 ELSE 0 END)
                / COUNT(*), 1)                                      AS labimise_protsent
        FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
        WHERE YLEVAATUSLIIK  = 'KORRALINE'
          AND YLEVAATUSOTSUS IN ('KORRAS', 'KORDUVALE')
          AND TEHNOYLEVAATUSPUNKT IS NOT NULL AND TEHNOYLEVAATUSPUNKT != ''
        GROUP BY TEHNOYLEVAATUSPUNKT, PUNKTI_KOOD
        HAVING COUNT(*) >= 100
        ORDER BY labimise_protsent ASC
    """).df()


# ── Q2b: Inspector strictness (paginated in app) ──────────────────────────────


@st.cache_data(show_spinner=False)
def q_inspector_strictness(years: list) -> pd.DataFrame:
    urls = _urls_list(years)
    return duckdb.sql(f"""
        SELECT
            TOOTAJA                                                 AS inspektori_kood,
            TEHNOYLEVAATUSPUNKT                                     AS jaam,
            PUNKTI_KOOD                                             AS jaama_kood,
            COUNT(*)                                                AS kokku,
            SUM(CASE WHEN YLEVAATUSOTSUS='KORRAS'    THEN 1 ELSE 0 END) AS labis_esimesel,
            SUM(CASE WHEN YLEVAATUSOTSUS='KORDUVALE' THEN 1 ELSE 0 END) AS kukkus_esimesel,
            ROUND(100.0 *
                SUM(CASE WHEN YLEVAATUSOTSUS='KORRAS' THEN 1 ELSE 0 END)
                / COUNT(*), 1)                                      AS labimise_protsent
        FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
        WHERE YLEVAATUSLIIK  = 'KORRALINE'
          AND YLEVAATUSOTSUS IN ('KORRAS', 'KORDUVALE')
          AND TOOTAJA IS NOT NULL AND TOOTAJA != ''
        GROUP BY TOOTAJA, TEHNOYLEVAATUSPUNKT, PUNKTI_KOOD
        HAVING COUNT(*) >= 50
        ORDER BY labimise_protsent ASC
    """).df()


# ── Q3: Oldest car per month ──────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def q_oldest_car_per_month(year: int) -> pd.DataFrame:
    url = get_url(year)
    return duckdb.sql(f"""
        WITH aged AS (
            SELECT
                CAST(SUBSTR(YV_KUUPAEV, 6, 2) AS INTEGER)          AS kuu,
                MARK, MUDEL, KERETYYP,
                CAST(ESMANE_REG_AASTA AS INTEGER)                   AS reg_aasta,
                CAST(SUBSTR(YV_KUUPAEV, 1, 4) AS INTEGER)
                    - CAST(ESMANE_REG_AASTA AS INTEGER)             AS vanus,
                ROW_NUMBER() OVER (
                    PARTITION BY CAST(SUBSTR(YV_KUUPAEV, 6, 2) AS INTEGER)
                    ORDER BY CAST(ESMANE_REG_AASTA AS INTEGER) ASC
                ) AS rnk
            FROM read_csv_auto('{url}', delim=',', header=true, encoding='utf-8')
            WHERE YLEVAATUSLIIK  = 'KORRALINE'
              AND YLEVAATUSOTSUS = 'KORRAS'
              AND ESMANE_REG_AASTA IS NOT NULL
              AND TRY_CAST(ESMANE_REG_AASTA AS INTEGER) > 1900
        )
        SELECT kuu, MARK, MUDEL, KERETYYP, reg_aasta, vanus
        FROM aged WHERE rnk = 1 ORDER BY kuu
    """).df()


# ── Q4: Age effect on pass rate ───────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def q_age_effect(years: list) -> pd.DataFrame:
    urls = _urls_list(years)
    return duckdb.sql(f"""
        WITH aged AS (
            SELECT
                CAST(SUBSTR(YV_KUUPAEV, 1, 4) AS INTEGER)
                    - CAST(ESMANE_REG_AASTA AS INTEGER)             AS vanus,
                CASE WHEN YLEVAATUSOTSUS='KORRAS' THEN 1 ELSE 0 END AS labis
            FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
            WHERE YLEVAATUSLIIK  = 'KORRALINE'
              AND YLEVAATUSOTSUS IN ('KORRAS', 'KORDUVALE')
              AND ESMANE_REG_AASTA IS NOT NULL
              AND TRY_CAST(ESMANE_REG_AASTA AS INTEGER) > 1900
        ),
        grouped AS (
            SELECT
                CASE
                    WHEN vanus BETWEEN 0  AND 1  THEN '0–1 (uus)'
                    WHEN vanus BETWEEN 2  AND 5  THEN '2–5'
                    WHEN vanus BETWEEN 6  AND 10 THEN '6–10'
                    WHEN vanus BETWEEN 11 AND 15 THEN '11–15'
                    WHEN vanus BETWEEN 16 AND 20 THEN '16–20'
                    WHEN vanus BETWEEN 21 AND 30 THEN '21–30'
                    WHEN vanus BETWEEN 31 AND 40 THEN '31–40'
                    WHEN vanus > 40              THEN '41+'
                    ELSE NULL
                END AS vanusegrupp,
                CASE
                    WHEN vanus BETWEEN 0  AND 1  THEN 1
                    WHEN vanus BETWEEN 2  AND 5  THEN 2
                    WHEN vanus BETWEEN 6  AND 10 THEN 3
                    WHEN vanus BETWEEN 11 AND 15 THEN 4
                    WHEN vanus BETWEEN 16 AND 20 THEN 5
                    WHEN vanus BETWEEN 21 AND 30 THEN 6
                    WHEN vanus BETWEEN 31 AND 40 THEN 7
                    WHEN vanus > 40              THEN 8
                    ELSE NULL
                END AS sorteering,
                labis
            FROM aged WHERE vanus BETWEEN 0 AND 100
        )
        SELECT
            vanusegrupp, sorteering,
            COUNT(*) AS kokku, SUM(labis) AS labis_arv,
            ROUND(100.0 * AVG(labis), 1) AS labimise_protsent
        FROM grouped WHERE vanusegrupp IS NOT NULL
        GROUP BY vanusegrupp, sorteering ORDER BY sorteering
    """).df()


# ── Q5: Mark pass rate by age group ──────────────────────────────────────────


@st.cache_data(show_spinner=False)
def q_mark_pass_by_age(years: list, mark: str) -> pd.DataFrame:
    urls = _urls_list(years)
    mark_upper = mark.strip().upper()
    return duckdb.sql(f"""
        WITH aged AS (
            SELECT
                CAST(SUBSTR(YV_KUUPAEV, 1, 4) AS INTEGER)
                    - CAST(ESMANE_REG_AASTA AS INTEGER)             AS vanus,
                CASE WHEN YLEVAATUSOTSUS='KORRAS' THEN 1 ELSE 0 END AS labis
            FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
            WHERE YLEVAATUSLIIK  = 'KORRALINE'
              AND YLEVAATUSOTSUS IN ('KORRAS', 'KORDUVALE')
              AND UPPER(MARK) = '{mark_upper}'
              AND ESMANE_REG_AASTA IS NOT NULL
              AND TRY_CAST(ESMANE_REG_AASTA AS INTEGER) > 1900
        ),
        grouped AS (
            SELECT
                CASE
                    WHEN vanus BETWEEN 0  AND 1  THEN '0–1 (uus)'
                    WHEN vanus BETWEEN 2  AND 5  THEN '2–5'
                    WHEN vanus BETWEEN 6  AND 10 THEN '6–10'
                    WHEN vanus BETWEEN 11 AND 15 THEN '11–15'
                    WHEN vanus BETWEEN 16 AND 20 THEN '16–20'
                    WHEN vanus BETWEEN 21 AND 30 THEN '21–30'
                    WHEN vanus BETWEEN 31 AND 40 THEN '31–40'
                    WHEN vanus > 40              THEN '41+'
                    ELSE NULL
                END AS vanusegrupp,
                CASE
                    WHEN vanus BETWEEN 0  AND 1  THEN 1
                    WHEN vanus BETWEEN 2  AND 5  THEN 2
                    WHEN vanus BETWEEN 6  AND 10 THEN 3
                    WHEN vanus BETWEEN 11 AND 15 THEN 4
                    WHEN vanus BETWEEN 16 AND 20 THEN 5
                    WHEN vanus BETWEEN 21 AND 30 THEN 6
                    WHEN vanus BETWEEN 31 AND 40 THEN 7
                    WHEN vanus > 40              THEN 8
                    ELSE NULL
                END AS sorteering,
                labis
            FROM aged WHERE vanus BETWEEN 0 AND 100
        )
        SELECT
            vanusegrupp, sorteering,
            COUNT(*) AS kokku, SUM(labis) AS labis_arv,
            ROUND(100.0 * AVG(labis), 1) AS labimise_protsent
        FROM grouped WHERE vanusegrupp IS NOT NULL
        GROUP BY vanusegrupp, sorteering ORDER BY sorteering
    """).df()


@st.cache_data(show_spinner=False)
def q_available_marks(years: list) -> list:
    urls = _urls_list(years)
    df = duckdb.sql(f"""
        SELECT DISTINCT UPPER(MARK) AS mark
        FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
        WHERE MARK IS NOT NULL AND MARK != ''
        ORDER BY mark
    """).df()
    return df["mark"].tolist()


# ── Q6: Defect analysis ───────────────────────────────────────────────────────
#
# The RIKKED column contains comma-separated entries like "VO:100101460,OV:100103882"
# DuckDB's string_split + unnest lets us explode these into individual rows.
# We extract the severity prefix (before ':') and defect ID (after ':').


@st.cache_data(show_spinner=False)
def q_defect_overview(years: list) -> pd.DataFrame:
    """
    Overview of defect counts by severity level (VO / OV / EOV) per year.
    Returns one row per year with counts of inspections that had each severity.
    """
    urls = _urls_list(years)
    return duckdb.sql(f"""
        SELECT
            CAST(SUBSTR(YV_KUUPAEV, 1, 4) AS INTEGER)              AS aasta,
            COUNT(*)                                                AS kokku_ylevaatusi,
            SUM(CASE WHEN RIKKED IS NOT NULL
                      AND RIKKED != ''
                     THEN 1 ELSE 0 END)                            AS riketega_ylevaatusi,
            SUM(CASE WHEN RIKKED LIKE '%VO:%'  THEN 1 ELSE 0 END)  AS vo_arv,
            SUM(CASE WHEN RIKKED LIKE '%OV:%'  THEN 1 ELSE 0 END)  AS ov_arv,
            SUM(CASE WHEN RIKKED LIKE '%EOV:%' THEN 1 ELSE 0 END)  AS eov_arv
        FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
        WHERE YLEVAATUSLIIK = 'KORRALINE'
        GROUP BY aasta
        ORDER BY aasta
    """).df()


@st.cache_data(show_spinner=False)
def q_top_defects(years: list, top_n: int = 15) -> pd.DataFrame:
    """
    Top N most common defect IDs across all inspections in selected years.
    Returns: rike_id, raskusaste, esinemisi, nimetus (defect name from rike.csv)
    """
    urls = _urls_list(years)
    df = duckdb.sql(f"""
        WITH exploded AS (
            SELECT
                TRIM(entry)                                             AS entry,
                TRIM(SPLIT_PART(TRIM(entry), ':', 1))                  AS tase,
                TRIM(SPLIT_PART(TRIM(entry), ':', 2))                  AS rike_id
            FROM (
                SELECT UNNEST(STRING_SPLIT(RIKKED, ',')) AS entry
                FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
                WHERE RIKKED IS NOT NULL AND RIKKED != ''
                  AND YLEVAATUSLIIK = 'KORRALINE'
            )
            WHERE TRIM(entry) != ''
              AND TRIM(SPLIT_PART(TRIM(entry), ':', 2)) != ''
        )
        SELECT
            rike_id,
            tase                    AS raskusaste,
            COUNT(*)                AS esinemisi
        FROM exploded
        WHERE tase IN ('VO', 'OV', 'EOV')
          AND TRY_CAST(rike_id AS INTEGER) IS NOT NULL
        GROUP BY rike_id, tase
        ORDER BY esinemisi DESC
        LIMIT {top_n}
    """).df()
    df["nimetus"] = df["rike_id"].map(_RIKE_LOOKUP).fillna("")
    return df


@st.cache_data(show_spinner=False)
def q_defects_by_mark_model_year(
    years: list,
    top_defect_ids: list,
    mark: str = None,
    mudel: str = None,
    reg_aasta: int = None,
) -> pd.DataFrame:
    """
    For the given top defect IDs, show how often each defect appears
    broken down by MARK, MUDEL, and ESMANE_REG_AASTA.

    Filters:
        mark       — specific car make (optional, user input)
        mudel      — specific model (optional, user input)
        reg_aasta  — specific registration year (optional)

    Returns a DataFrame with columns:
        MARK, MUDEL, ESMANE_REG_AASTA, rike_id, raskusaste, esinemisi
    """
    urls = _urls_list(years)

    # Build optional WHERE filters
    filters = ["YLEVAATUSLIIK = 'KORRALINE'", "RIKKED IS NOT NULL", "RIKKED != ''"]
    if mark:
        filters.append(f"UPPER(MARK) = '{mark.strip().upper()}'")
    if mudel:
        filters.append(f"UPPER(MUDEL) = '{mudel.strip().upper()}'")
    if reg_aasta:
        filters.append(f"TRY_CAST(ESMANE_REG_AASTA AS INTEGER) = {reg_aasta}")

    where_clause = " AND ".join(filters)

    # Build the IN list for defect IDs
    id_list = ", ".join(f"'{str(d)}'" for d in top_defect_ids)

    return duckdb.sql(f"""
        WITH exploded AS (
            SELECT
                MARK,
                MUDEL,
                TRY_CAST(ESMANE_REG_AASTA AS INTEGER)              AS reg_aasta,
                TRIM(SPLIT_PART(TRIM(entry), ':', 1))               AS raskusaste,
                TRIM(SPLIT_PART(TRIM(entry), ':', 2))               AS rike_id
            FROM (
                SELECT
                    MARK, MUDEL, ESMANE_REG_AASTA,
                    UNNEST(STRING_SPLIT(RIKKED, ',')) AS entry
                FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
                WHERE {where_clause}
            )
            WHERE TRIM(entry) != ''
              AND TRIM(SPLIT_PART(TRIM(entry), ':', 2)) != ''
        )
        SELECT
            MARK, MUDEL, reg_aasta,
            rike_id, raskusaste,
            COUNT(*) AS esinemisi
        FROM exploded
        WHERE raskusaste IN ('VO', 'OV', 'EOV')
          AND rike_id IN ({id_list})
          AND TRY_CAST(rike_id AS INTEGER) IS NOT NULL
          AND MARK IS NOT NULL AND MARK != ''
        GROUP BY MARK, MUDEL, reg_aasta, rike_id, raskusaste
        ORDER BY esinemisi DESC
    """).df()
    df["nimetus"] = df["rike_id"].map(_RIKE_LOOKUP).fillna("")
    return df


@st.cache_data(show_spinner=False)
def q_defects_summary_by_mark(years: list, top_n: int = 20) -> pd.DataFrame:
    """
    Top N car marks ranked by total number of defects found (all severities).
    Used for the overview chart on the defects page.
    """
    urls = _urls_list(years)
    return duckdb.sql(f"""
        WITH exploded AS (
            SELECT
                MARK,
                TRIM(SPLIT_PART(TRIM(entry), ':', 1)) AS raskusaste,
                TRIM(SPLIT_PART(TRIM(entry), ':', 2)) AS rike_id
            FROM (
                SELECT MARK,
                       UNNEST(STRING_SPLIT(RIKKED, ',')) AS entry
                FROM read_csv_auto({urls}, delim=',', header=true, encoding='utf-8')
                WHERE RIKKED IS NOT NULL AND RIKKED != ''
                  AND YLEVAATUSLIIK = 'KORRALINE'
                  AND MARK IS NOT NULL AND MARK != ''
            )
            WHERE TRIM(entry) != ''
        )
        SELECT
            MARK,
            COUNT(*)                                                AS rikeid_kokku,
            SUM(CASE WHEN raskusaste='VO'  THEN 1 ELSE 0 END)      AS vo,
            SUM(CASE WHEN raskusaste='OV'  THEN 1 ELSE 0 END)      AS ov,
            SUM(CASE WHEN raskusaste='EOV' THEN 1 ELSE 0 END)      AS eov
        FROM exploded
        WHERE raskusaste IN ('VO', 'OV', 'EOV')
          AND TRY_CAST(rike_id AS INTEGER) IS NOT NULL
        GROUP BY MARK
        ORDER BY rikeid_kokku DESC
        LIMIT {top_n}
    """).df()
