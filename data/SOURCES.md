# Data sources

Inputs the build notebook (`notebooks/Ontology_Work_clean.ipynb`) consumes, and where
to get them. Large/regenerable files are **not** committed — they live on Box or are
downloaded from the sources below. Fill in the `version` column with what you actually
used, and verify URLs (they drift).

## Credentials / config (environment variables)

| Variable | Used for | Notes |
|---|---|---|
| `ROMANO_DB_PASSWORD` | PMACS `opendata` Postgres (COCONUT schema) | **Gated** — Penn/lab access only |
| `ENTREZ_EMAIL` | NCBI Entrez (taxonomy validation) | any valid email |

DrugCentral uses a **public** read-only mirror (`unmtid-dbs.net:5433`, `drugman/dosage`) —
no secret needed.

## Scaffold (in this repo)

| File | What | How produced |
|---|---|---|
| `data/ontology/poppystructure.rdf` | Hand-curated TBox (classes, properties) | Edited in Protégé, exported as RDF/XML |

## Build inputs (download — not committed)

| Source | What it provides | Obtain (verify URL) | Version | Access |
|---|---|---|---|---|
| **COCONUT** (PMACS DB) | base plants + compounds (organisms, molecules, properties) | PMACS `opendata` DB, `coconut.*` schema | _fill in_ | **Gated** (Penn). Non-Penn: use the public COCONUT download below |
| **CMAUP v2.0** | plant–ingredient–target associations | https://bidd.group/CMAUP/ | v2.0 | public |
| **NPASS** | natural-product target names | https://bidd.group/NPASS/ | _fill in_ | public |
| **DrugCentral** | action types, targets, ATC codes | `unmtid-dbs.net:5433` (public mirror) | _fill in_ | public |
| **ChEMBL drug mechanisms** | mechanism of action, targets | https://www.ebi.ac.uk/chembl/explore/drug_mechanisms/ (export CSV → `ChEMBL_drug_mechanisms.csv`) | _fill in_ | public (CC BY-SA) |
| **Dr. Duke's Phytochemical & Ethnobotanical DB** | ethnobotanical activities, dosages, refs | https://phytochem.nal.usda.gov/ (ACTIVITIES, AGGREGAC, CHEMICALS, DOSAGE, ETHNOBOT, REFERENCES CSVs) | _fill in_ | public (USDA) |
| **ChEBI** | chemical ontology alignment | https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi_lite.owl | _fill in_ | public (CC BY) |
| **ComptoxAI** | `GeneticEntity` classes + gene individuals (`comptox_populated.rdf`) | https://comptox.ai/ | _fill in_ | _verify_ |
| **COCONUT 2.0 (SDF)** | expanded compound–organism occurrences | https://coconut.naturalproducts.net/download → `coconut_sdf_2d-*.zip` | 06-2026 | public (CC0) |

## Enrichment services (live APIs, called by Stages 14–15)

| Service | Provides | Endpoint |
|---|---|---|
| **PubChem PUG-REST** | common names, IUPAC names, CIDs | https://pubchem.ncbi.nlm.nih.gov/rest/pug/ |
| **UniChem** (EMBL-EBI) | cross-refs (ChEMBL/ChEBI/DrugBank/KEGG/HMDB) | https://www.ebi.ac.uk/unichem/api/v1/ |
| **NPClassifier** (GNPS2) | NP pathway/superclass/class | https://npclassifier.gnps2.org/classify |

API lookups are cached to JSON (`pubchem_names.json`, `iupac_names.json`, etc.) and are
resumable — re-running skips work already done.

## Outputs (hosted on Box — not committed)

| File | What |
|---|---|
| `phytotherapies_named.rdf` | ontology + PubChem/ChEBI names + IUPAC names |
| `phytotherapies_named_coconut.rdf` | above + COCONUT 2.0 occurrences (**canonical**) |
| `website/poppy-ontology-real.js` | 24-species subset regenerated from the canonical RDF (committed; it's small) |

> Box link: https://upenn.box.com/v/poppyontology
