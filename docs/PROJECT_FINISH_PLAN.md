# Projekti vaheanalüüs ja lõpuni viimise plaan

Koostatud: 2026-05-20

## Vaheanalüüs

Projekt on jõudnud seisu, kus hindamise põhiartefakt on olemas ja käivitatud:

- `notebooks/00_hindamise_notebook.ipynb` sisaldab andmete lugemist, puhastamist, visualiseerimist ja juhendatud mudelit.
- Notebook töötab 2023-2025 täismahus cache'i pealt.
- Mudel kasutab ajapõhist split'i: 2023-2024 treening, 2025 test.
- Lekkivad koguandmestiku tunnused `MARK_LABIMISE_MAAR`, `MUDEL_LABIMISE_MAAR` ja `PUNKTI_RANGUS` on lõppmudelist eemaldatud.
- Mudel kasutab nüüd leakage-safe ajaloolisi riskitunnuseid, mis õpitakse sklearn pipeline'i sees ainult treeningaastatelt.
- Metadata sisaldab nüüd tõenäosuste kvaliteedimõõdikuid ja ajapõhist isotonic-kalibreerimise kontrolli.
- `PUNKTI_KOOD` on lubatud kategoorilise tunnusena, sest see on enne ülevaatust teada olev jaamakood.
- `models/random_forest.pkl` ja `models/model_metadata.json` on sama loogika järgi üle treenitud.
- Streamliti ennustusvorm kasutab sama tunnusekomplekti nagu notebook ja kaitseb vana lekkiva metadata kasutamise eest.
- Hindamisnotebook sisaldab nüüd ka juhendamata lisaanalüüsi: leakage-safe K-Means klasterdamist.
- `src/clustering.py` ja Streamliti klastrite vaade on viidud samale skeemile nagu notebook.
- Unit-testid, notebooki valideerimine ja Streamliti käivitus on viimases kontrolliringis läbinud.

Praegune lõppmudeli seis 2025 testandmestikul:

- baseline `alati KORRAS` accuracy: `0.849`
- Random Forest accuracy: `0.570`
- balanced accuracy: `0.658`
- ROC AUC: `0.710`
- `Korras` precision/recall/F1: `0.933 / 0.532 / 0.678`
- läbikukkujate 0.80 recall'i lävi: riskilävi umbes `0.496`, precision `0.227`, riskirühma maht `53.1%`
- lõppmudeli tõenäosuste kvaliteet: Brier `0.222`, log-loss `0.632`, ECE `0.317`
- ajapõhises kalibreerimiskontrollis paranes isotonic-kalibreerimisega Brier `0.224 -> 0.120`, log-loss `0.637 -> 0.387`, ECE `0.320 -> 0.007`

Tõlgendus: mudel paranes, aga ei sobi endiselt automaatseks otsustamiseks. Kalibreerimiskontroll näitab, et absoluutseid tõenäosusi saab oluliselt paremaks teha, kuid praegune rakendus peab väljundit nimetama riskiskooriks. See järeldus on kooskõlas kursuse mudeli hindamise loenguga, kus accuracy üksi ei ole tasakaalustamata klasside korral piisav.

## Juhendamata õppe seis

Kursuse slaidid sisaldavad juhendamata õpet ja K-Meansi. See osa on nüüd olemas põhinotebookis `notebooks/00_hindamise_notebook.ipynb`, `src/clustering.py` skriptis ja Streamliti klastrite vaates. Vana `notebooks/03_ml.ipynb` eemaldati, sest see sisaldas aegunud masinõppe rada.

Klasterdamine ei kasuta enam `PUNKTI_RANGUS` tunnust. Sisendtunnused on enne ülevaatust teada olevad või sihttunnusest sõltumatud tunnused; läbimise määra kasutatakse ainult klastrite hilisemaks kirjeldamiseks.

Tegelik tulemus: `k=2` andis parima siluetiskoori (`0.130`), kuid see on madal. Järeldus notebookis peab seetõttu olema ettevaatlik: K-Means on kursusemetoodika demonstratsioon ja profiilide kirjeldus, mitte tugev tõend loomulike sõidukigruppide olemasolust.

## Kuidas klasterdamine lisati

### Metoodiline otsus

Klasterdamise sisendtunnused ei tohi sisaldada `LABIS_ESIMESEL`, `YLEVAATUSOTSUS`, `RIKKED`, `PUNKTI_RANGUS` ega margi/mudeli läbimismäärasid. Neid võib kasutada ainult klastrite hilisemaks kirjeldamiseks, mitte klastrite loomiseks.

Kasutatud klasterdamise sisendtunnused:

- `VANUS`
- `MARK_SAGEDUS`
- `MUDEL_SAGEDUS`
- `EELMISED_YV`
- `KUU_SIN`
- `KUU_COS`
- `KATEGOORIA`
- `KERETYYP`
- `PUNKTI_KOOD`

Selgitus:

- numbrilised tunnused skaleeritakse `StandardScaler` abil;
- kategoorilised tunnused kodeeritakse `OneHotEncoder` abil;
- `KMeans` sobib kursuse sisuga;
- `LABIS_ESIMESEL` kasutatakse ainult profiilitabelis, et näha, millistes klastrites on suurem kordusülevaatuse risk.

### Mahuotsus

Täismahus andmestik on 1.84 miljonit mudeli sihttunnusega rida. K-Meansi ja silhouette'i jaoks ei ole vaja kogu andmestikku kasutada.

Rakendatud otsus:

- võtta reprodutseeritav valim, näiteks `100_000` rida;
- arvutada elbow ja silhouette `k = 2..6` peal;
- valida k siluetiskoori ja tõlgendatavuse järgi; praeguses jooksus valiti `k = 2`;
- profiilida klastrid samal valimil;
- markdownis selgelt öelda, et see on juhendamata lisaanalüüs valimil, mitte lõppmudeli treening.

### Notebooki lisatavad väljundid

Notebooki peaks lisanduma:

1. Lühike markdown, mis selgitab juhendamata õppe eesmärki.
2. K-Meansi koodi plokk:
   - valim;
   - `ColumnTransformer`;
   - `StandardScaler`;
   - `OneHotEncoder`;
   - `KMeans`;
   - inertia ja silhouette tabel.
3. Graafik:
   - elbow/inertia;
   - silhouette.
4. Klastrite profiilitabel:
   - klaster;
   - suurus;
   - keskmine vanus;
   - läbimise määr;
   - top kategooria;
   - top keretüüp;
   - top jaamakood;
   - top mark.
5. Markdown-järeldus:
   - klasterdamine näitab profiile, mitte põhjuslikke seoseid;
   - läbimise määr on profiili tõlgendamiseks, mitte klasterdamise sisend;
   - tulemused toetavad juhendatud mudeli leidusid, eriti vanuse ja sõidukitüübi mõju.

## Korrigeeritud lõpetamise põhimõte

2026-05-20 täpsustus: lõppprojekt ei tohi olla tööajaloo arhiiv. Esitamisel peab projekt olema jagatud kaheks selgeks osaks:

1. **Hindamise põhifail** — üks notebook, mis sisaldab kogu hinnatavat andmeteaduse töövoogu.
2. **Rakenduse ja taasesituse failid** — Streamlit, `src/` moodulid, mudeli artefaktid, vajalikud andmeabifailid ja käivitusjuhised.

Vanu notebooke ei esitata eraldi, kui nende sisu on kas aegunud või juba põhinotebookis. Kui mõni vana notebook sisaldab olulist infot, tuleb see koondada lühidalt `notebooks/00_hindamise_notebook.ipynb` sisse või README-sse, mitte jätta paralleelseks hindamisteeks.

Soovitatav lõppstruktuur:

```text
Andmeteadus_kodutoo/
├── README.md
├── requirements.txt
├── notebooks/
│   └── 00_hindamise_notebook.ipynb
├── dashboard/
│   └── app.py
├── src/
│   ├── data_cache.py
│   ├── data_cleaner.py
│   ├── data_loader.py
│   ├── defects.py
│   ├── prediction.py
│   ├── clustering.py
│   └── year_sources.py
├── data/
│   ├── README.md
│   ├── raw/rike.csv
│   └── processed/
│       ├── cluster_profiles.json
│       ├── elbow_plot.png
│       ├── model_evaluation.png
│       └── model_metrics.json
├── models/
│   ├── random_forest.pkl
│   └── model_metadata.json
├── tests/
└── docs/
    ├── COURSE_ALIGNMENT.md
    ├── PROJECT_AUDIT.md
    └── PROJECT_FINISH_PLAN.md
```

Märkus: ajalooline `Analysis plan`, `DEVCONTAINER_SETUP.md` ja `.devcontainer/` eemaldati, sest kõik vajalik on nüüd `README.md`, `docs/` failides ja põhinotebookis.

## Lõpuni viimise plaan

### Samm 1. Lisada K-Means põhinotebooki — tehtud

Fail: `notebooks/00_hindamise_notebook.ipynb`

Tegevused:

- lisada importidesse `KMeans`, `silhouette_score`, `StandardScaler`;
- lisada uus sektsioon pärast mudeli järeldust ja enne kokkuvõtet;
- kasutada leakage-safe tunnuseid;
- käivitada notebook täismahus uuesti;
- uuendada kokkuvõtet hindajale, et notebook sisaldab ka juhendamata lisaanalüüsi.

Kontroll tehtud:

- notebook valideerub `nbformat` abil;
- notebooki lähtekoodis ei ole `?` täpitähtede asemel;
- notebooki täiskäivitus ei lähe ebamõistlikult aeglaseks.

### Samm 2. Uuendada `src/clustering.py` — tehtud

Skript on joondatud notebooki uue K-Meansi loogikaga.

Tegevused:

- asendada `CLUSTER_FEATURES`;
- kasutada `ColumnTransformer`-põhist preprocessingut;
- salvestada `cluster_profiles.json` uue skeemiga;
- vajadusel lisada `cluster_metadata.json`, kus on kasutatud tunnused, sample size, k väärtused ja silhouette.

Kontroll tehtud:

- `python src/clustering.py --years 2023 2024 2025` töötab ilma `features.csv` sõltuvuseta;
- `data/processed/cluster_profiles.json` ei sisalda enam `avg_strictness` kui põhivälja.

### Samm 3. Uuendada Streamliti klastrite leht — tehtud

Fail: `dashboard/app.py`

Tegevused:

- kuvada uue `cluster_profiles.json` skeemi väljad;
- eemaldada või ümber nimetada `Rangus`, kui `avg_strictness` enam ei ole;
- näidata klastrite suurust, vanust, läbimise määra, top kategooriat/keretüüpi/marki/jaamakoodi.

Kontroll:

- Streamlit avaneb `http://localhost:8501`;
- klastrite leht ei eelda vana JSON skeemi.

### Samm 4. Dokumentatsioon ja kooskõla — tehtud

Failid:

- `docs/COURSE_ALIGNMENT.md`
- `docs/PROJECT_AUDIT.md`
- `docs/PROJECT_FINISH_PLAN.md`
- `README.md`

Tegevused:

- märkida, et juhendamata õpe on nüüd ka põhinotebookis;
- kirjeldada, miks klasterdamises ei kasutata `PUNKTI_RANGUS`;
- lisada lühike juhis, kuidas K-Meansi artefakte uuendada.

### Samm 5. Lõppkontrollid — tehtud

Käsud:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_defects tests.test_data_cache tests.test_prediction
.\.venv\Scripts\python.exe -m compileall src dashboard tests
.\.venv\Scripts\python.exe -c "import nbformat; nb=nbformat.read('notebooks/00_hindamise_notebook.ipynb', as_version=4); nbformat.validate(nb); print('nbformat OK')"
git diff --check
```

Lisaks:

- kontrollida, et `models/model_metadata.json` ei sisalda lekkivaid tunnuseid;
- kontrollida, et Streamlit vastab;
- kontrollida `git status`, et oleks selge, millised failid tuleb esitada/commit'ida.

2026-05-20 kontrolliringi tulemus:

- `src/clustering.py --years 2023 2024 2025` töötas ja uuendas klastrite artefaktid;
- unit-testid läbisid viimases kontrolliringis: 17 testi OK;
- `compileall` läbis `src`, `dashboard` ja `tests` peal;
- hindamisnotebook käivitus uuesti `nbconvert --execute --inplace` abil;
- `nbformat` valideerus ja notebooki lähtekoodis ei jäänud täpitähtede asemel kahtlasi märke;
- `git diff --check` läbis, ainult Git hoiatas kahe faili LF/CRLF teisenduse kohta;
- Streamlit vastas aadressil `http://localhost:8501` HTTP 200;
- `models/model_metadata.json` ei sisalda lekkivaid koguandmestiku tunnuseid `MARK_LABIMISE_MAAR`, `MUDEL_LABIMISE_MAAR` ega `PUNKTI_RANGUS`;
- metadata sisaldab uut `historical_rate_features` plokki, mille tunnused õpitakse pipeline'i sees ainult treeningandmetelt.
- metadata sisaldab `probability_quality` ja `calibration_analysis` plokke.

### Samm 6. Vana sisu koondamine ja üleliigse eemaldamine — tehtud

Failid:

- `notebooks/01_eda.ipynb`
- `notebooks/02_hypotheses.ipynb`
- `notebooks/03_ml.ipynb`

Otsus:

- `01_eda.ipynb` sisaldab kasulikku uurivate küsimuste struktuuri, kuid lõpphindamiseks ei pea seda eraldi notebookina esitama.
- `02_hypotheses.ipynb` sisaldab kasulikku hüpoteeside testimise mõtet, kuid tulemused ja caveat'id tuleb koondada põhinotebooki lühikesse sektsiooni.
- `03_ml.ipynb` on lõppseisus pigem kahjulik, sest sisaldab vana masinõppe rada ja võib jätta mulje, et projektis on mitu vastuolulist lõppmudelit.

Tehtud:

1. Lisatud `00_hindamise_notebook.ipynb` sisse lühike sektsioon "Uurimisküsimused ja hüpoteeside kokkuvõte", kus on näha:
   - vanuse mõju;
   - margi võrdluse piirangud;
   - jaama/ranguse analüüsi caveat;
   - miks lõppmudel kasutab riskiskoori, mitte automaatset otsust.
2. Kontrollitud, et sisuliselt vajalik vanadest notebookidest on põhinotebookis või README-s.
3. Eemaldatud vanad notebookid:
   - `notebooks/01_eda.ipynb`
   - `notebooks/02_hypotheses.ipynb`
   - `notebooks/03_ml.ipynb`
4. `notebooks/` kausta jäi ainult `00_hindamise_notebook.ipynb`.

Kontroll:

- README ütleb selgelt, et hindamise põhifail on `notebooks/00_hindamise_notebook.ipynb`.
- Repos ei ole paralleelset vana ML-notebooki, mis lõppmudeliga vastuollu läheks.
- Notebooki markdown sisaldab piisavalt konteksti, et vanu notebooke pole vaja avada.

### Samm 7. Projekti kausta korrastamine — tehtud

Eesmärk: hoida root-kaust võimalikult selge.

Tehtud:

1. Loodud `docs/` kaust.
2. Tõstetud sinna:
   - `COURSE_ALIGNMENT.md`
   - `PROJECT_AUDIT.md`
   - `PROJECT_FINISH_PLAN.md`
3. Eemaldatud `Analysis plan`, sest vajalik info on juba README-s, docs-failides ja põhinotebookis.
4. Eemaldatud `DEVCONTAINER_SETUP.md`, `.devcontainer/` ja vana `download_data.py`, sest esituse töövoog kasutab `src/data_cache.py` ja lokaalset Python/venv seadistust.
5. Kontrollitud, et ajutised lokaalsed kataloogid ei ole jälgitavad ega lähe commiti:
   - `.venv/`
   - `.duckdb/`
   - `.ipython/`
   - `.jupyter/`
   - `.jupyter_data/`
   - `.jupyter_runtime/`
   - `.matplotlib/`
   - `data/cache/`

### Samm 8. Lõplik esituse kontroll ja push — kontroll tehtud, push ootel

Enne commit'i:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_defects tests.test_data_cache tests.test_prediction
.\.venv\Scripts\python.exe -m compileall src dashboard tests
.\.venv\Scripts\python.exe -c "import nbformat; nb=nbformat.read('notebooks/00_hindamise_notebook.ipynb', as_version=4); nbformat.validate(nb); print('nbformat OK')"
git diff --check
git status --short --untracked-files=all
```

2026-05-20 korrastuse järel tehtud kontroll:

- 17 unit-testi OK;
- `compileall src dashboard tests` OK;
- põhinotebook valideerub `nbformat` abil ja täpitähtede kontroll on puhas;
- `git diff --check` OK, ainult LF/CRLF hoiatused;
- mudel laeb eraldi protsessis ja ennustab;
- Streamlit vastab aadressil `http://localhost:8501` HTTP 200.

Commit'i ettevalmistus:

1. Vaadata koos üle `git status`.
2. Lisada ainult vajalikud failid.
3. Commit'i kirjeldus peaks olema sisuline, näiteks:

```text
Finalize assessment notebook and leakage-safe model workflow

- add single grading notebook with cleaning, visualisation, modelling and K-Means supplement
- replace leakage-prone features with temporal split and pipeline-fitted historical risk features
- add probability-quality and calibration analysis
- align Streamlit app with saved model metadata
- add tests for defect parsing, data cache and prediction workflow
- remove obsolete exploratory notebooks from submission path
```

Push:

```powershell
git push origin ai-tooversioon
```

## Prioriteedid

Kõige tähtsam enne esitamist:

1. Põhinotebook peab olema käivitatav ja loetav.
2. Põhinotebook peab sisaldama hindajale vajalikke järeldusi markdownis.
3. Juhendamata õppe lisamine peab olema metoodiliselt puhas, mitte vastuolus leakage'i vältimise põhimõttega.
4. Streamlit on lisaväljund; see ei tohi notebooki asendada.
5. Vanad notebookid tuleb kas eemaldada või nende oluline sisu põhinotebooki koondada. Eelistus: eemaldada, et hindaja näeks ühte selget hindamisteed.

## Soovitatav järgmine tööetapp

Järgmine praktiline etapp on koondada vanade notebookide vajalik sisu põhinotebooki, eemaldada vanad notebookid ja korrastada projekti kaust esituse jaoks.
