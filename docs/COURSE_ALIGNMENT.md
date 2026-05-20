# Kooskõla kursuse slaididega

Koostatud: 2026-05-20

Allikad: `../kursuse slaidid/` kaustas olevad kuus loenguslaidide PDF-i:

- `Lecture 1 - Introduction to data science.pdf`
- `Loeng 2 - Kirjeldav analüüs.pdf`
- `Loeng 3. Juhendamata masinõpe.pdf`
- `Loeng 4. Juhendatud masinõpe.pdf`
- `Lecture 5 - Mudeli hindamine.pdf`
- `Loeng 6 - Mudeli juurutamine.pdf`

## Lühijäreldus

Projekt on kursuse sisuga üldiselt hästi kooskõlas. Põhivoog katab CRISP-DM loogika: andmete mõistmine, kvaliteedikontroll, puhastamine, tuletatud tunnused, visualiseerimine, mudeli loomine, hindamine ja lihtne juurutus Streamliti rakenduses.

Mõned lahendused erinevad lihtsatest loengunäidetest, kuid need ei ole sisulised vastuolud. Need on projekti andmestiku tõttu paremad valikud: andmed on ajapõhised, väga mahukad ja klassid on tasakaalustamata.

## Kooskõla kursuse teemade kaupa

### 1. CRISP-DM ja andmeteaduse töövoog

Kursus rõhutab andmete mõistmist, visualiseerimist, kvaliteedikontrolli, ettevalmistust, modelleerimist, hindamist ja juurutamist. Projekt järgib seda:

- `notebooks/00_hindamise_notebook.ipynb` sisaldab ühes kontrollitavas töövoos andmete lugemist, puhastamist, visualiseerimist ja mudelit.
- `src/data_cache.py` ja `data/README.md` teevad andmeallika ja cache'i töövoo korratavaks.
- `docs/PROJECT_AUDIT.md` dokumenteerib riskid, eeldused ja tehtud parandused.
- Streamlit rakendus on eraldi juurutuse/demonstratsiooni kiht, mitte notebooki asendus.

Hinnang: kooskõlas.

### 2. Kirjeldav analüüs, visualiseerimine ja statistilised testid

Kursus käsitleb tunnusetüüpe, tulpdiagramme, jaotusi, kahe tunnuse seose visualiseerimist, hii-ruut testi, t-testi/alternatiivseid kahe valimi teste, korrelatsiooni ja puhastamist.

Projektis on olemas:

- visualiseerimine vanusegrupi, margi ja rikete raskusastme järgi;
- hüpoteeside notebookides hii-ruut test, Mann-Whitney U test ning Pearsoni/Spearmani korrelatsioon;
- selged caveat'id, et markide ja jaamade võrdlus on kirjeldav, mitte põhjuslik;
- parandatud `RIKKED` parser ja kontroll, et `EOV` ei läheks ekslikult `OV` alla.

Hinnang: kooskõlas. Mann-Whitney U ei ole loengus põhitestina rõhutatud, kuid on põhjendatud parem valik, kui jaotused ei ole normaalsed või valimid on suured ja ebasümmeetrilised.

### 3. Juhendamata õpe

Kursus käsitleb K-Meansi, klasterdamise subjektiivsust, kaugusmõõte ja mõõtmete vähendamist. Projektis on `src/clustering.py`, `data/processed/cluster_profiles.json` ja Streamliti klastrite vaade.

2026-05-20 lisati sama lekkekindel K-Meansi lisaanalüüs ka hindamisnotebooki `notebooks/00_hindamise_notebook.ipynb`. Klasterdamise sisendites ei kasutata sihttunnust, `RIKKED` veergu, `PUNKTI_RANGUS` tunnust ega margi/mudeli läbimismäärasid. Läbimise määra kasutatakse ainult hiljem klastrite kirjeldamiseks.

Tulemus on metoodiliselt aus: parim testitud lahendus oli `k=2`, kuid siluetiskoor jäi madalaks (`0.130`). See tähendab, et andmetes ei ole K-Meansi jaoks väga selgeid loomulikke klasse. Projekt esitab klasterdamist seetõttu lisaprofiilina, mitte põhitulemusena.

Hinnang: kooskõlas. Lahendus katab kursuse juhendamata õppe teema ning teeb selgelt vahet klastrite loomise ja klastrite hilisema tõlgendamise vahel.

### 4. Juhendatud masinõpe

Kursus õpetab juhendatud õppe toru: preprocessing, feature extraction, train/test split, mudeli valik, hüperparameetrid, treenimine, testandmestikul hindamine ja tulemuste raporteerimine. Projektis on see olemas:

- `RandomForestClassifier` on kursuses käsitletud mudeliperega kooskõlas.
- `ColumnTransformer`, `SimpleImputer` ja `OneHotEncoder` moodustavad selge modelleerimispipeline'i.
- Mudel kasutab numbrilisi tunnuseid ja kategoorilisi tunnuseid, sh `PUNKTI_KOOD`.
- Mudel salvestatakse `models/random_forest.pkl` ja metadata `models/model_metadata.json`.

Hinnang: kooskõlas.

### 5. Mudeli hindamine ja tasakaalustamata klassid

Loeng 5 rõhutab, et accuracy võib tasakaalustamata klasside korral olla eksitav, ning käsitleb confusion matrix'it, precision'it, recall'i, F1 skoori, ROC kõverat ja AUC-d.

Projekt järgib seda hästi:

- notebook näitab baseline'i `alati KORRAS`;
- raporteeritud on accuracy, balanced accuracy, precision, recall, F1 ja ROC AUC;
- olemas on confusion matrix ja ROC kõver;
- lisatud on riskilävendi analüüs läbikukkujate leidmiseks.

See on eriti oluline, sest 2025 testandmetel on `KORRAS` klass umbes 84,9%. Ainult accuracy järgi oleks naiivne baseline eksitavalt tugev.

Hinnang: väga hästi kooskõlas.

### 6. Mudeli juurutamine

Loeng 6 käsitleb pipeline'i, mudeli serialiseerimist, monitooringut, tõrkekindlust, unit-teste ja training-serving skew riski.

Projektis on olemas:

- mudeli serialiseerimine pickle failina;
- metadata JSON;
- Streamliti ennustusvorm;
- unit-testid parserile, cache'ile ja prediction töövoole;
- kaitse vana lekkivate tunnustega metadata vastu;
- sama tunnusekomplekt notebookis, `prediction.py` skriptis ja Streamliti vormis.

Puudub production-tasemel monitooring, kuid kursuseprojekti kontekstis on Streamlit + salvestatud mudel + testid piisav praktiline juurutus.

Hinnang: kooskõlas kursuseprojekti tasemel.

## Teadlikud erinevused ja miks need on paremad

### Ajapõhine split, mitte juhuslik 80/20 split

Loengus kasutatakse sageli lihtsat train/test jaotust ja ristvalideerimist. Projekt kasutab mitme aasta korral ajapõhist jaotust: 2023-2024 treening, 2025 test.

See on parem, sest eesmärk on hinnata, kas mudel üldistub tulevikuandmetele. Juhuslik split segaks aastad kokku ja annaks ajapõhise andmestiku puhul liiga optimistliku tulemuse.

### Target-derived tunnuste eemaldamine

Varasem mudel kasutas `MARK_LABIMISE_MAAR`, `MUDEL_LABIMISE_MAAR` ja `PUNKTI_RANGUS`, mis olid arvutatud kogu andmestiku pealt enne train/test split'i. Need tunnused võivad sisaldada sihttunnuse infot.

Projektis eemaldati need lõppmudelist. See on parem kui naiivne feature engineering, sest väldib target leakage'it ja on kooskõlas mudeli hindamise põhimõttega: testandmestiku infot ei tohi treeningusse lekkida.

Hiljem lisatud kvaliteediparandus kasutab samuti ajaloolisi läbikukkumise määrasid, kuid teisel kujul: `HIST_*_FAIL_RATE` tunnused õpitakse sklearn pipeline'i sees ainult treeningandmetelt ja rakendatakse seejärel testiaastale. See ei ole vastuolu varasema leakage'i vältimise otsusega. Vahe on selles, kas määr arvutatakse kogu andmestiku pealt ette või fititakse ainult treeningperioodil.

### `PUNKTI_KOOD` kasutamine on lubatud, `PUNKTI_RANGUS` mitte

`PUNKTI_KOOD` on enne ülevaatust teada olev kategooriline tunnus. `PUNKTI_RANGUS` on aga sihttunnusest arvutatud koondnäitaja. Seetõttu on `PUNKTI_KOOD` lõppmudelis lubatud, kuid `PUNKTI_RANGUS` välja jäetud.

See on metoodiliselt parem kompromiss: mudel võib õppida jaamade süsteemseid erinevusi ilma, et talle antaks otse sama andmestiku läbikukkumise määra.

Uus `HIST_PUNKT_FAIL_RATE` ja `HIST_PUNKT_KATEGOORIA_FAIL_RATE` on lubatav kitsendus ainult seepärast, et need arvutatakse treeningaastatelt. Neid tuleb notebookis esitada kui ajaloolist riskisignaali, mitte kui objektiivset väidet jaama ranguse kohta.

### Täismahus cache, mitte väike failipõhine näide

Kursuse näited töötavad väikeste andmestikega. Projektis kasutatakse 2023-2025 täismahtu ehk 2 198 715 toorrida. Cache ja allikate haldus ei ole vastuolu, vaid vajalik insenertehniline täiendus, et analüüs oleks korratav ja mõistliku ajaga käivitatav.

### Lävendianalüüs automaatse otsuse asemel

Mudeli precision läbikukkujate klassile on madal, kuigi recall on kõrge. Seetõttu ei esitata mudelit automaatse otsustajana, vaid riskiskoorina.

See on parem ja ausam tõlgendus kui ainult "mudel ennustab" narratiiv. See on kooskõlas loengu 5 rõhuasetusega valepositiivsete ja valenegatiivsete kompromissile.

Lisaks lisati Brier score, log-loss, ECE ja ajapõhine isotonic-kalibreerimise kontroll. See läheb kursuse mudeli hindamise teemast sammu edasi, kuid ei ole vastuolus: tasakaalustamata klasside puhul ei piisa ainult accuracy või ROC AUC vaatamisest, sest kasutajale näidatav riskiskoor peab olema ka tõlgendatav.

## Võimalikud nõrgad kohad

1. K-Meansi siluetiskoor on madal. See ei ole vastuolu kursusega, vaid oluline negatiivne tulemus: klasterdamine ei leia väga tugevat loomulikku jaotust.
2. Hüperparameetreid ei valita lõppmudelis ristvalideerimisega. See on aktsepteeritav, sest andmestik on suur ja ajapõhine holdout on tähtsam. Kui aega jääb, võiks lisada väiksema valimi peal `TimeSeriesSplit` või eraldi valideerimisaasta.
3. Production-monitooring puudub. Kursuseprojekti jaoks pole see kriitiline, kuid loeng 6 mõttes võiks README-s märkida, mida päris juurutuses jälgida: andmejaotuse muutus, mudeli drift, sisendvigade osakaal ja ennustuste jaotus.

## Lõpphinnang

Projekt ei ole kursuse sisuga vastuolus. Vastupidi: projekt kasutab kursuse põhimeetodeid ja lisab mõnes kohas tugevamaid praktikaid, mis on andmestiku mahu ja ajalisuse tõttu põhjendatud. Kõige olulisem on notebookis selgelt välja öelda, miks kasutati ajapõhist splitti, miks eemaldati lekkivad koondtunnused ja miks mudelit tõlgendatakse riskiskoorina, mitte automaatse otsustajana.
