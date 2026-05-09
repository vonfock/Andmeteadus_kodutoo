# Data Dictionary

## Inspection data (yearly CSVs: 2010.csv – 2025.csv)

| Column | Type | Description (ET) | Description (EN) |
|--------|------|-------------------|-------------------|
| TEHNOYLEVAATUSPUNKT | text | Ülevaatuse teostanud punkt | Inspection station name |
| PUNKTI_KOOD | text | Tehnoülevaatuspunkti kood | Station code (2 letters) |
| TOOTAJA | text | Ülevaatust teostanud ülevaataja | Inspector employee ID |
| YV_KUUPAEV | text | Ülevaatuse aasta ja kuu (YYYY-MM) | Inspection year and month |
| YLEVAATUSLIIK | text | Ülevaatuse liik | Inspection type: KORRALINE (regular), KORDUV (repeat), EURO6, RAHVUSVAHELINE |
| YLEVAATUSOTSUS | text | Ülevaatuse otsus | Decision: KORRAS (pass), KORDUVALE (fail/repeat needed), VASTAB_NOUETELE |
| RIKKED | text | Avastatud rikked (TASE:RIKE_ID) | Defects found (SEVERITY:DEFECT_ID) — VO=minor, OV=significant, EOV=dangerous |
| SOIDUK_ID | integer | Anonümiseeritud sõiduki ID | Anonymised vehicle ID |
| ESMANE_REG_AASTA | integer | Esmase registreerimise aasta | First registration year |
| MARK | text | Sõiduki mark | Vehicle make (e.g. VOLKSWAGEN, BMW) |
| MUDEL | text | Sõiduki mudel | Vehicle model |
| KATEGOORIA | text | Sõiduki kategooria | Vehicle category (M1, N1, O1, L3e, etc.) |
| KERETYYP | text | Sõiduki keretüüp | Body type (SEDAAN, UNIVERSAAL, KAUBIK, etc.) |

## Defect codes (rike.csv)

| Column | Type | Description |
|--------|------|-------------|
| ID | integer | Unique defect ID (referenced in RIKKED column) |
| NIMETUS | text | Defect description in Estonian |
| TYYP | text | Entry type: GRUPP (group), ALAMGRUPP (subgroup), NIMETUS (specific defect) |
| RIKKE_LIIK | text | Which inspection type the defect applies to (YLEVAATUS, POLITSEI) |
| VANEM_ID | text | Parent ID — links subgroup→group or defect→subgroup |
| VO | text | Can be minor defect (Jah/Ei) |
| OV | text | Can be significant defect (Jah/Ei) |
| EOV | text | Can be dangerous defect (Jah/Ei) |
| KUVAMISE_JARJEKORD | integer | Display order |
| ALGUS | timestamp | Validity start date |
| LOPP | timestamp | Validity end date (NULL = currently valid) |
| KOOD | text | External reference code |
| KEHTIV_RIKE_ID | integer | If expired, points to the replacement defect ID |

## Key relationships

- `RIKKED` column in inspection data contains `SEVERITY:DEFECT_ID` pairs
- `DEFECT_ID` maps to `rike.csv → ID`
- Severity levels: VO (VäheOluline/minor), OV (Oluline Viga/significant), EOV (Eriti Ohtlik Viga/dangerous)
- A single inspection can have multiple defects separated within the RIKKED field
