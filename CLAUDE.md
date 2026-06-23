# CLAUDE.md — POPPy project guide

> Auto-loaded by Claude Code in any session, on any machine. Keep it current: it is
> the hand-off that survives `git push`/`pull`. For the active work plan and session
> log, see **`docs/nar-submission/ROADMAP.md`** and **`docs/nar-submission/PROGRESS.md`**.

## What POPPy is

POPPy (**Phyto-Ontology Platform for Pharmacology**) is an ontology / knowledge graph of
medicinal-plant phytochemistry, plus a static website that disseminates and visualizes it.
Built and maintained by the **Romano Lab, University of Pennsylvania**.

It links five top-level concepts and the named relationships between them:

- **PlantConcept** — species, taxonomy, geography, ethnobotanical context
- **ChemicalConcept** — molecules (SMILES, canonical SMILES, InChIKey, IUPAC, formula, MW, MACCS fingerprint), subclassed (polyphenols, carotenoids, phytosterols, saponins, etc.) via SMILES heuristics + ChEBI alignment
- **HumanConcept** — pathways, proteins, genes (drug targets)
- **TherapeuticConcept** — mechanism-of-action, therapeutic effects, ATC, dosage, toxicity
- **ResearchConcept** — evidence layer: papers (DOI), clinical trials (NCT), citation graph

## Current goal

Get the resource (website + ontology/KG/DB) ready for submission to the **NAR Database
Issue**. Two requirements drive everything: (1) make it **scientifically impactful** and
(2) make it **clearly distinguishable** from existing phytotherapy resources — especially
**COCONUT** (COlleCtion of Open NatUral producTs), which has been published in NAR.

## Repository map

| Path | What |
|---|---|
| `website/` | The live static site. **No build step, no framework** — each `.html` page is self-contained (markup + `<style>` + `<script>`). `Home.html` is the entry point. |
| `website/data/` | Sharded JSON the Explore page lazy-loads: `plants_index.json` (~5 MB search index), `plant_edges/` (~43 MB), `compounds/` (~65 MB). Shard key `djb2(plantId)&255`. |
| `website/ontology-data.js` | Single source of truth for the in-page graph (`window.POPPY` with `NODES`/`EDGES`). |
| `website/poppy-ontology-real.js` | 24-species curated subset regenerated from the canonical RDF (small, committed). |
| `data/ontology/poppystructure.rdf` | Hand-curated TBox scaffold (classes/properties), edited in Protégé. |
| `data/SOURCES.md` | Every input dataset, version, access notes, and enrichment APIs. |
| `notebooks/Ontology_Work_clean.ipynb` | End-to-end build pipeline — authoritative record of how the ontology was produced. |
| `src/poppy/`, `scripts/`, `configs/` | Python package + CLI + YAML configs for the (modularized) build. |
| `deploy/` | AWS EC2 provisioning (`aws-setup.sh`) + cloud-init bootstrap (`user-data.sh`). |
| `docs/nar-submission/` | **Our working plan + progress log for the NAR push.** |

## Data scale (`website/data/meta.json`)

~59,700 organisms · ~278,000 compounds · ~1.24 M plant–compound links.
**Caveat:** the organism set still includes non-plant organisms (bacteria, fungi, *Homo
sapiens*) pulled in by the COCONUT 2.0 import, which skipped the NCBI/POWO plant
validation. A taxonomy filter to restrict the browse to true plants is a planned follow-up.

## Hosting / deploy

- **Live:** `poppyontology.org` — nginx static host on an **AWS EC2** instance (Ubuntu),
  provisioned by `deploy/aws-setup.sh`, bootstrapped by `deploy/user-data.sh`.
- The instance clones the public repo to `/opt/poppy/repo` and serves `website/` from
  `/var/www/poppy`. Redeploy on the box with `sudo poppy-deploy` (git pull + rsync + nginx reload).
- A **GitHub Pages** workflow (`.github/workflows/pages.yml`) also publishes `website/` on
  push to `main` (`romanolab.github.io/poppy/`) — a secondary mirror.
- Full enriched ontology (RDF/XML, ~2 GB) lives on **Box**: https://upenn.box.com/v/poppyontology
  (too large for git; linked from the Download page).

## Conventions / gotchas

- **No build step for the site.** Edit the `.html` directly. `botanical-margins.js` is the
  editable source but is *inlined* into each page's `<script id="bm-inline">` block — see
  `website/BUILD-NOTES.md` before changing it.
- External runtime APIs (degrade gracefully): Wikimedia Commons (plant photos), PubChem
  PUG-REST (structure images), NCBI Gene + UniProt (gene-chip links).
- The big RDF is **not** committed; regenerate `website/data/` from the notebook and commit
  the JSON when data changes.
- CI runs ruff + black on `src`/`scripts` (excludes `src/poppy/ontology/sources`, `scripts/ingest`).

## Persisting work across machines

This repo is the only thing that syncs. When you finish a working session, append a dated
entry to `docs/nar-submission/PROGRESS.md` and update the checklist in `ROADMAP.md`, then
commit. The next session (on any machine) starts by reading those two files.
