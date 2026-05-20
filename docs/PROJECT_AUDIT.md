# Project Audit

Koostatud: 2026-05-20

See fail fikseerib projekti lähteolukorra enne sisulisi parandusi ja hilisemad olulisemad muutused. Eesmärk on hoida eraldi kirjas, mis oli olemas, mis töötas, millised riskid on teada ja milliste mõõdikute vastu edasisi muudatusi võrrelda.

## Git ja keskkond

- Haru: `ai-tooversioon`
- Viimane commit: `a670274 Parandusi`
- Python lokaalses keskkonnas: 3.14.5
- Virtuaalkeskkond: `.venv/`
- Streamlit käivitus lokaalselt varem edukalt aadressil `http://localhost:8501`
- Pythoni süntaksikontroll:

```powershell
.\.venv\Scripts\python.exe -m compileall src dashboard
```

Tulemus: `src` ja `dashboard` kompileerusid vigadeta.

Praegune tööpuu sisaldab kahte sihitud lokaalset muudatust, mis tehti enne auditit töökindluse jaoks:

- `.gitignore` ignoreerib `.duckdb/`
- `src/data_loader.py` suunab DuckDB extension directory projekti alla, et vältida Windowsi kodukausta õiguste viga

Ignoreeritud lokaalsed failid/kaustad:

- `.venv/`
- `.duckdb/`
- `.streamlit/secrets.toml`
- `src/__pycache__/`
- `dashboard/__pycache__/`

## Andmefailid ja artefaktid

Repos olemas:

- `data/raw/rike.csv` - 1,107,843 baiti
- `data/processed/cluster_profiles.json`
- `data/processed/elbow_plot.png`
- `data/processed/model_evaluation.png`
- `models/random_forest.pkl`
- `models/model_metadata.json`

Repos ei ole olemas aastate raw CSV faile (`2010.csv` ... `2025.csv`) ja neid ei pea esitamisel kaasa panema. README kirjeldab nüüd ühte eelistatud töövoogu: `src/data_cache.py` laeb vajalikud aastad ignoreeritud `data/cache/` kausta ning dashboard kasutab cache'i olemasolul seda. Kui cache puudub, saavad päringud vajadusel ametlikust allikast lugeda.

## Praegune andmekasutus

`src/data_loader.py` loeb dashboardi päringutes CSV-d otse kaug-URL-idelt läbi DuckDB `read_csv_auto`. See võimaldab dashboardi ilma raw failideta käivitada, kuid on aeglane ja raskesti kontrollitav.

Tähelepanekud:

- Ühe aasta lihtne päring 2010 andmete peal töötas, kuid võttis ligikaudu 106 sekundit.
- Mitme aasta valim dashboardis võib seetõttu olla kasutaja jaoks väga aeglane.
- Sama andmestikku loetakse mitmes päringus korduvalt.
- Puudub lokaalne Parquet/DuckDB cache kiiremaks korduvkasutuseks.

## Praegune masinõppe mudel

Olemasolev mudel:

- Mudel: `RandomForestClassifier Pipeline with leakage-safe historical rates`
- Fail: `models/random_forest.pkl`
- Treeningandmed metadata järgi: 2023-2024
- Testandmed metadata järgi: 2025
- Treeningridu: `1 222 757`
- Testiridu: `619 702`
- Streamliti sisendtunnuseid: 13 (`MUDEL` lisandus ajaloolise margi-mudeli riskimäära arvutamiseks)
- Klassid: `0`, `1`

Mudeli parameetrid:

```json
{
  "class_weight": "balanced",
  "max_depth": 12,
  "min_samples_leaf": 10,
  "n_estimators": 40
}
```

Metadata mõõdikud:

```json
{
  "baseline_always_pass_accuracy": 0.849,
  "accuracy": 0.570,
  "balanced_accuracy": 0.658,
  "precision": 0.933,
  "recall": 0.532,
  "f1": 0.678,
  "roc_auc": 0.710
}
```

Olulisemad tunnused metadata järgi:

1. `num__HIST_MUDEL_FAIL_RATE` - 0.1978
2. `num__HIST_PUNKT_KATEGOORIA_FAIL_RATE` - 0.1065
3. `num__VANUS` - 0.0963
4. `num__VANUS_RUUT` - 0.0887
5. `num__HIST_KERETYYP_FAIL_RATE` - 0.0655

Mudelist on välja jäetud `MARK_LABIMISE_MAAR`, `MUDEL_LABIMISE_MAAR` ja `PUNKTI_RANGUS`, sest need olid algses töövoos arvutatud enne train/test split'i. Kvaliteediparandus lisas smoothed ajaloolised fail-rate tunnused (`HIST_*_FAIL_RATE`), kuid need õpitakse sklearn pipeline'i sees ainult treeningandmetelt. Seetõttu 2025 testiaasta sihttulemus ei leki tunnustesse.

`PUNKTI_KOOD` on lubatud kategoorilise tunnusena, sest see on enne ülevaatust teada olev jaamakood, mitte sihttunnusest arvutatud rangusnäitaja.

Tõenäosuste kvaliteet lõppmudelil:

```json
{
  "brier_score": 0.222,
  "log_loss": 0.632,
  "expected_calibration_error": 0.317
}
```

Ajapõhine kalibreerimiskontroll näitas, et isotonic-kalibreerimine on järgmine realistlik kvaliteediparandus: Brier score paranes `0.224 -> 0.120`, log-loss `0.637 -> 0.387` ja ECE `0.320 -> 0.007`. Seda ei pandud veel lõppmudeli põhiväljundiks, sest puhas kontrollmudel kasutab 2024. aastat kalibreerimiseks, mitte baasmudeli treenimiseks. Dashboard nimetab väljundit seetõttu riskiskooriks.

Lookup tabelid metadata sees:

- `mark_lookup`: 2923 kirjet
- `mudel_lookup`: 26 376 margi-mudeli kirjet
- `category_options`, `body_type_options` ja `station_code_options` Streamliti vormi jaoks

## ML lähteprobleemid

Algset 2025-only mudelit tuli käsitleda prototüübina, mitte lõpliku teadusliku mudelina.

Peamised probleemid:

1. Mudel on treenitud ainult 2025. aasta andmetelt.
2. EDA ja hüpoteeside notebookid kasutavad vaikimisi 2015-2024 perioodi, ML notebook kasutab ainult 2025. See on metoodiline ebajärjekindlus.
3. `MARK_LABIMISE_MAAR`, `MUDEL_LABIMISE_MAAR` ja `PUNKTI_RANGUS` arvutatakse enne train/test split'i kogu andmestiku pealt. See tekitab target leakage riski.
4. Klassid on tugevalt tasakaalustamata. Eemaldatud varasema `notebooks/03_ml.ipynb` väljund näitas 2025 andmetel läbimise määra umbes 84.9%.
5. Mudeli accuracy 0.6183 on madalam kui naiivsel "alati läbib" baasmudelil, kuid ROC-AUC 0.7506 näitab mingit järjestuslikku signaali.
6. Metadata ei sisalda recall väärtust, kuigi tasakaalustamata klassi korral on see oluline.
7. Dashboardis kasutatakse ennustuses fikseeritud aastat 2025 vanuse arvutamiseks, mis muutub ajas valeks.

2026-05-20 uuendus: need kriitilised probleemid on põhivoos parandatud. `src/prediction.py` treenib mudeli 2023-2025 cache'i pealt, kasutab ajapõhist holdout'i, salvestab baseline/balanced accuracy/recall/lävendianalüüsi ning Streamliti ennustusleht ei luba kasutada vana lekkivate tunnustega metadata skeemi.

## Hüpoteeside ja notebookide seis

Notebookid:

- `notebooks/00_hindamise_notebook.ipynb`: 2026-05-20 lisatud ja täismahus 2023-2025 cache'i pealt käivitatud hindamise põhinotebook, mis koondab andmete lugemise, puhastamise, visualiseerimise, uurimisküsimuste/hüpoteeside kokkuvõtte, juhendamata K-Meansi lisaanalüüsi ja mudeli loomise ühte kontrollitavasse töövoogu.
- Vanad notebookid `01_eda.ipynb`, `02_hypotheses.ipynb` ja `03_ml.ipynb` eemaldati esituse lihtsustamiseks. Nende kasulik sisu koondati põhinotebooki lühikokkuvõttena; vana ML-notebook eemaldati ka seepärast, et see sisaldas aegunud 2025-only masinõppe rada.

Tähtsad tähelepanekud:

- H1 kasutab sobivat hii-ruut testi `<=10` vs `>10` vanusegruppide jaoks, kuid logistilise trendijoone loogika ei modelleeri otse rea tasemel `LABIS_ESIMESEL` tõenäosust.
- H2 kasutab premium vs eelarve võrdlust ja Mann-Whitney U testi, kuid kontrollib vanust ainult 5-15 aasta filtriga. See ei kontrolli piisavalt aastat, sõidukitüüpi, jaama ega valimi koosseisu.
- H3 kasutab Pearsoni ja Spearmani korrelatsiooni jaama mahu ning kukkumise protsendi vahel. See on esmane analüüs, kuid jaamade sõidukikoosseis võib tulemuse segada.
- Hindamiseks tuleb eelistada `00_hindamise_notebook.ipynb` faili, sest vanemad eraldi notebookid ei anna üksi terviklikku hindamisvoogu.
- Notebooki täismahus jooks kasutas 2 198 715 toorrida ja 1 842 459 mudeli sihttunnusega rida. Mudel treeniti 2023-2024 andmetel ja testiti 2025. aasta peal.
- Notebook sisaldab nüüd ka läbikukkujate riskilävendi analüüsi. Vähemalt 0,80 recall'i saavutamiseks on riskilävi umbes 0,496, precision on 0,227 ja riskirühma satub 53,1% testiridadest.

## Andmeõigsuse riskid ja parandused

1. `RIKKED` eraldaja oli algses seisus ebaühtlaselt käsitletud.
   - Kontrollitud 2015, 2020 ja 2025 näidised kasutavad mitme rikke puhul semikoolonit, näiteks `VO:100101460;VO:100103933`.
   - 2026-05-20 lisatud ühine parser `src/defects.py`, mida kasutab `src/data_cleaner.py`.
   - DuckDB päringud normaliseerivad enne lahtiharutamist semikooloni, koma ja reavahetuse.

2. `OV` ja `EOV` loendamise risk oli algses seisus `LIKE '%OV:%'` kasutuses.
   - 2026-05-20 eemaldatud alamstringipõhine loendus `src/data_loader.py` päringutest.
   - Loendus toimub nüüd parseeritud raskusastme väärtuse järgi, et `EOV` ei läheks `OV` alla.

3. Vanuse arvutamisel tuleb igal pool kasutada turvalist `TRY_CAST` ja piirata ebareaalsed vanused.

4. `YLEVAATUSOTSUS = 'VASTAB_NOUETELE'` jäetakse mitmes kohas välja. See võib olla õige, kui eesmärk on ainult `KORRAS` vs `KORDUVALE`, kuid otsus peab olema dokumenteeritud.

5. 2023-2025 valideerimisraport näitas `RIKKED` parseri jaoks 0 vigast kirjet ja 0 tundmatu raskusastmega kirjet; kõik kasutatud rikke-ID-d leidusid `rike.csv` tabelis.

## Dokumentatsiooni vastuolud

2026-05-20 kontrolliringis parandatud README ja projekti struktuuri vastuolud:

- repo nimi on nüüd `Andmeteadus_kodutoo`;
- tehnilise plaani ja auditimärkmed on `docs/` kaustas;
- dashboardi kirjeldus ei väida enam ekslikult, et rakenduses on täpselt "5 pages".
- `DEVCONTAINER_SETUP.md` ja `.devcontainer/` eemaldati, sest esituse töövoog kasutab lokaalset Python/venv lahendust;
- vanad notebookid eemaldati, et hindamisel oleks üks selge põhifail.

Hindamisel tuleks suunata õppejõud eelkõige `notebooks/00_hindamise_notebook.ipynb` ja `README.md` juurde. `docs/` kaustas olevad failid on toetav taustamaterjal.

## Kursuse praktikumidega kooskõla

Praktikumide põhjal on projektis kasutusel mitmed oodatud elemendid:

- andmepuhastus ja tunnuste konstrueerimine;
- hii-ruut test;
- K-Means ja `StandardScaler`; 2026-05-20 lisatud hindamisnotebooki ja `src/clustering.py` skripti lekkekindlal kujul;
- train/test split;
- GridSearchCV;
- Random Forest;
- confusion matrix, precision, recall, F1, ROC-AUC kontseptsioonid;
- tasakaalustamata klasside käsitlus `class_weight='balanced'` kaudu.

Kooskõla nõrgad kohad:

- algses mudelis toimus target encoding enne split'i;
- algses mudelis kasutati ainult ühte aastat, kuigi andmestik on ajaperioodiline;
- hüpoteeside notebookid ei sisalda käivitatud tulemusi;
- algses metadata failis ei hinnatud vähemusklassi kasulikkust piisavalt; praegune metadata sisaldab classification report'i ja riskilävendi kokkuvõtet.
- K-Meansi siluetiskoor on madal (`0.130`), mistõttu klastrid on pigem kirjeldav lisavaade kui tugev loomulik andmejaotus.

## Järgmise sammu fookus

Andmelepingu, `RIKKED` parseri, cache'i, hindamisnotebooki põhitöö, juhendamata K-Meansi lisaanalüüs ja esimene mudeli kvaliteediparandus on tehtud. Notebooki mudel on ausam kui algne 2025-only mudel ning ajalooliste treeningandmetelt õpitud riskitunnuste lisamine parandas tulemusi: baseline `alati KORRAS` accuracy 0,849, Random Foresti accuracy 0,570, balanced accuracy 0,658 ja ROC AUC 0,710. Läbikukkujate recall on vaikimisi lävel umbes 0,78 ja precision umbes 0,23.

Lävendianalüüs ja kalibreerimiskontroll näitavad, et mudelit tuleb käsitleda riskiskoori, mitte automaatse otsustajana. 0,80 läbikukkujate recall'i korral on precision 0,227 ja riskirühma maht 53,1% testandmetest; 0,90 recall'i korral langeb precision 0,206 peale ja riskirühm kasvab 65,8% peale.

Järgmine muutmise etapp peaks olema mudeli riskiskoori täiendav parandamine või kalibreerimine:

1. otsustada, kas teha kalibreeritud mudel eraldi lõppartefaktiks või jätta kalibreerimine analüüsina;
2. testida mõnda alternatiivset mudelit samal ajapõhisel split'il;
3. vajadusel lihvida README ja Streamliti kasutusjuhist, kuid mitte taastada vanu paralleelseid notebooke.
