# Estonian Vehicle Roadworthiness Analysis

Analysing 15+ years of Estonian vehicle roadworthiness inspection (tehnoülevaatus) data to discover patterns in vehicle pass rates, brand reliability, and inspection station behaviour. Uses unsupervised and supervised machine learning to profile inspection cases and predict outcomes.

## Data Source

[Maismaasõidukite tehnoülevaatused Eestis](https://andmed.eesti.ee/datasets/maismaasoidukite-tehnoulevaatused-eestis) — Estonian open data portal (Transpordiamet). One CSV per year (2010–2025), updated monthly. Supplemented by `rike.csv` — the official defect code lookup table.

See `data/README.md` for the full data dictionary.

## Grading Notebook

The main artifact for assessment is:

```text
notebooks/00_hindamise_notebook.ipynb
```

This notebook contains the full assessable workflow in one place: data loading, data cleaning, visualisations, leakage-safe K-Means supplement, model training, evaluation metrics, and markdown conclusions. The Streamlit app is submitted separately as an interactive supplement, not as a replacement for the notebook.

Older exploratory notebooks were removed from the submission path. Their relevant research questions, hypothesis caveats and modelling conclusions have been consolidated into `00_hindamise_notebook.ipynb` so the lecturer has one coherent file to review.

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

See `docs/PROJECT_FINISH_PLAN.md`, `docs/PROJECT_AUDIT.md` and `docs/COURSE_ALIGNMENT.md` for planning notes, audit details and course-alignment rationale.

## Project Structure

```
Andmeteadus_kodutoo/
├── notebooks/
│   └── 00_hindamise_notebook.ipynb # Main grading notebook
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── src/
│   ├── data_cache.py         # Cache official yearly CSVs locally
│   ├── data_loader.py        # Dashboard queries over cached/remote CSVs
│   ├── defects.py            # Shared RIKKED parser
│   ├── clustering.py         # K-Means clustering
│   └── prediction.py         # Random Forest classifier + evaluation
├── data/
│   ├── raw/rike.csv          # Defect code reference table
│   ├── processed/            # Tracked model/cluster output artifacts
│   └── README.md             # Data dictionary (ET + EN)
├── models/
│   ├── random_forest.pkl
│   └── model_metadata.json
├── tests/
├── docs/
│   ├── COURSE_ALIGNMENT.md
│   ├── PROJECT_AUDIT.md
│   └── PROJECT_FINISH_PLAN.md
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
git clone https://github.com/vonfock/Andmeteadus_kodutoo.git
cd Andmeteadus_kodutoo

python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### Cache Data

The yearly inspection CSVs are not committed to the repository. For repeatable local work, cache selected yearly files before running the notebook or retraining the model:

```bash
python src/data_cache.py --years 2023 2024 2025
python src/data_cache.py --years 2023 2024 2025 --validate-only
```

### Run the pipeline

```bash
python src/data_cache.py --years 2023 2024 2025
python src/data_cache.py --years 2023 2024 2025 --validate-only
python src/prediction.py --years 2023 2024 2025
python src/clustering.py --years 2023 2024 2025
```

`src/prediction.py` reads the cached yearly files directly, trains the leakage-safe Random Forest pipeline with a temporal split, and regenerates `models/random_forest.pkl` plus `models/model_metadata.json`. The saved model intentionally excludes full-dataset target-derived pass-rate features and station strictness. It does use smoothed historical fail-rate features fitted inside the pipeline from training years only, plus the pre-inspection station code `PUNKTI_KOOD` as a categorical feature.

Current 2025 holdout metrics after the historical-rate improvement: accuracy `0.570`, balanced accuracy `0.658`, ROC AUC `0.710`, and `Korras` F1 `0.678`. The model is still documented as a risk score, not an automatic decision system.

The metadata also includes a temporal calibration check. Isotonic calibration trained without the 2025 test year improved probability quality substantially in the check (`Brier 0.224 -> 0.120`, `log loss 0.637 -> 0.387`), but the saved dashboard output is still presented as a risk score rather than an absolute probability.

`src/clustering.py` regenerates the K-Means cluster profiles and elbow/silhouette plot for the Streamlit cluster page. It uses leakage-safe inputs and does not use pass/fail outcome or station strictness as clustering features.

### Launch Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard opens without a password by default. If `.streamlit/secrets.toml` defines `APP_PASSWORD`, the app asks for that password before showing the pages.

### Run the grading notebook

Open `notebooks/00_hindamise_notebook.ipynb` in Jupyter or VS Code and run all cells. For faster repeated runs, build the local CSV cache first:

```bash
python src/data_cache.py --years 2023 2024 2025
```

## License

Open data from the Estonian Transport Administration (Transpordiamet). Reuse permitted for commercial and non-commercial purposes.
