# POPPy — Phyto-Ontology Platform for Pharmacology

POPPy is a reproducible pipeline for building a phytotherapy ontology / knowledge graph.
It ingests CMAUP/ChEMBL/SQL sources, validates plants (NCBI/POWO), enriches compounds
(SMILES, MACCS via RDKit), and exports OWL/RDF (TTL/RDF/XML). A static site in `web/`
publishes build stats and downloads.

[![CI](https://github.com/RomanoLab/poppy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/RomanoLab/poppy/actions/workflows/ci.yml)
[![Pages](https://github.com/RomanoLab/poppy/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/RomanoLab/poppy/actions/workflows/pages.yml)

> See `INTEGRATION_NOTES.md` for a deeper tour of the structure and CSV/SQL mappings.

---

## Quickstart

```bash
# 1) Create env
python -m venv .venv && source .venv/bin/activate

# 2) Install (dev tools included: ruff/black/pytest)
pip install -e ".[dev]"

# 3) Build ontology from config (see configs/ontology.yaml)
python scripts/build_ontology.py --config configs/ontology.yaml

---

## Build commands (Makefile)

Run these from the repo root:

```bash
make -C build ontology   # build ontology via configs/ontology.yaml
make -C build figures    # optional example figure(s) -> docs/figures
make -C build web-data   # copy processed TTL + stats into web/data/
make -C build all        # ontology + figures + web-data
- [Ontology data ingest guide](docs/recipes/ontology-data-ingest.md)

- [Recipes index](docs/recipes/README.md)
- [Ontology data ingest guide](docs/recipes/ontology-data-ingest.md)
## Download the ontology
The full enriched POPPy ontology (RDF/XML) is hosted on Box:
<https://upenn.box.com/v/poppyontology>
