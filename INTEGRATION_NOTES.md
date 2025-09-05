# Integration Notes (Notebook → Modules)

- DB queries live in `src/poppy/io/db.py` and are configured in `configs/ontology.yaml`.
- CSV loaders live in `src/poppy/io/csvs.py` and are configured in `configs/ontology.yaml`.
- rdflib enrichment functions live in `src/poppy/ontology/enrich.py`.
- The orchestrated build is `src/poppy/ontology/pipeline.py` with CLI in `scripts/build_ontology.py`.

## CSV/SQL Mappings
- CMAUP:
  - `CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt` → rename `Plant_ID`→`plant_id`, `Ingredient_ID`→`compound_id`
  - `CMAUPv2.0_download_Plants.txt` → rename `Plant_ID`→`plant_id`, `Scientific_Name`→`scientific_name`
  - `CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt` → `Ingredient_ID`→`compound_id`, `Target_ID`→`gene_id`
- NPASS: `NPASSv1.0_download_naturalProducts_targetInfo.txt` → `NP_ID`→`compound_id`, `Target`→`gene_id`
- ChEMBL mechanisms: `ChEMBL_drug_mechanisms.csv` → `molecule_chembl_id`→`compound_id`, `target_chembl_id`→`gene_id`

- COCONUT (SQL examples):
  - `SELECT id AS plant_id, name AS scientific_name FROM coconut.organisms;`
  - A compound join across `coconut.properties`, `coconut.entries`, `coconut.structures`, `coconut.organism_map`

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/build_ontology.py --config configs/ontology.yaml
```
