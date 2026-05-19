# Estonian Vehicle Roadworthiness Analysis

Analysing 15+ years of Estonian vehicle roadworthiness inspection (tehnoülevaatus) data to discover patterns in vehicle pass rates, brand reliability, and inspection station behaviour. Uses unsupervised and supervised machine learning to profile inspection cases and predict outcomes.

## Data Source

[Maismaasõidukite tehnoülevaatused Eestis](https://andmed.eesti.ee/datasets/maismaasoidukite-tehnoulevaatused-eestis) — Estonian open data portal (Transpordiamet). One CSV per year (2010–2025), updated monthly. Supplemented by `rike.csv` — the official defect code lookup table.

See `data/README.md` for the full data dictionary.

## Research Questions

### Exploratory analysis
1. Which vehicle types pass and fail most often, per year?
2. Which inspector (TOOTAJA) is strictest — highest fail rate and per-inspector pass probability?
3. Which inspection stations attract which types of vehicles?
4. Which vehicle types share the most similar failure patterns? (top 10 most common defects)
5. Per month — what was the oldest vehicle that passed and failed? (make, model, year, type)

### Hypotheses
1. **Age effect** — Vehicles older than 10 years have a significantly lower first-time pass rate, with a sharp drop-off after the 10-year mark.
2. **Brand reliability** — Premium car brands pass first-time inspections at a higher rate than budget brands of the same age.
3. **Station strictness** — High-volume urban inspection stations reject vehicles at a higher rate than low-volume rural stations.

See `ANALYSIS_PLAN.md` for the full technical specification.

## Project Structure

```
sissejuhatus_andmeteadusesse_grupitoo/
├── data/
│   ├── raw/                  # Original yearly CSVs (2010.csv – 2025.csv) + rike.csv
│   ├── processed/            # Cleaned, combined, feature-engineered data
│   └── README.md             # Data dictionary (ET + EN)
├── notebooks/
│   ├── 01_eda.ipynb          # Exploratory data analysis & research questions
│   ├── 02_hypotheses.ipynb   # Hypothesis testing & visualisations
│   └── 03_modelling.ipynb    # ML experiments (clustering + classification)
├── src/
│   ├── data_loader.py        # Combine yearly CSVs into one dataset
│   ├── data_cleaner.py       # Encoding fixes, NaN handling, defect parsing
│   ├── feature_engineering.py# Feature creation for ML
│   ├── clustering.py         # K-Means clustering
│   └── prediction.py         # Random Forest classifier + evaluation
├── dashboard/
│   └── app.py                # Streamlit dashboard (5 pages)
├── .streamlit/
│   └── config.toml           # Theme config
├── ANALYSIS_PLAN.md          # Detailed technical spec for Claude Code
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
git clone https://github.com/TereKruut/sissejuhatus_andmeteadusesse_grupitoo.git
cd sissejuhatus_andmeteadusesse_grupitoo

python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### Download Data

Go to [the dataset page](https://andmed.eesti.ee/datasets/maismaasoidukite-tehnoulevaatused-eestis), download each year's CSV into `data/raw/` named as `2010.csv`, `2011.csv` … `2025.csv`. Download `rike.csv` into `data/raw/` as well.

### Run the pipeline

```bash
python src/data_loader.py                   # Combine raw CSVs
python src/data_cleaner.py                  # Clean and enrich
python src/feature_engineering.py           # Build ML features
python src/clustering.py                    # K-Means
python src/prediction.py                    # Random Forest
```

### Launch Dashboard

```bash
streamlit run dashboard/app.py
```

## License

Open data from the Estonian Transport Administration (Transpordiamet). Reuse permitted for commercial and non-commercial purposes.