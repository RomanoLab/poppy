# CLAUDE.md — POPPy project guide

> Auto-loaded by Claude Code in any session, on any machine. Keep it current: it is
> the hand-off that survives `git push`/`pull`. The active work plan and session log are
> kept in local, gitignored working notes (not committed to the repo).

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

Get the resource (website + ontology/KG/DB) ready for **publication**. Two requirements
drive everything: (1) make it **scientifically impactful** and (2) make it **clearly
distinguishable** from existing phytotherapy resources — especially **COCONUT**
(COlleCtion of Open NatUral producTs).

## Repository map

| Path | What |
|---|---|
| `website/` | The live static site. **No build step, no framework.** Pages are **content-only HTML** (refactored 2026-06-24); styles/scripts live in their own files: shared `poppy.css` + per-page `<Page>.css` + per-page `<Page>.js` (`botanical-margins.js` is kept inlined as the known-good state). `Home.html` is the entry point. See `website/BUILD-NOTES.md`. |
| `website/data/` | Sharded JSON the Explore page lazy-loads: `plants_index.json` (~5 MB search index), `plant_edges/` (~43 MB), `compounds/` (~65 MB). Shard key `djb2(plantId)&255`. |
| `website/ontology-data.js` | Single source of truth for the in-page graph (`window.POPPY` with `NODES`/`EDGES`). |
| `website/poppy-ontology-real.js` | 24-species curated subset regenerated from the canonical RDF (small, committed). |
| `data/ontology/poppystructure.rdf` | Hand-curated TBox scaffold (classes/properties), edited in Protégé. |
| `data/SOURCES.md` | Every input dataset, version, access notes, and enrichment APIs. |
| `notebooks/Ontology_Work_clean.ipynb` | End-to-end build pipeline — authoritative record of how the ontology was produced. |
| `src/poppy/`, `scripts/`, `configs/` | Python package + CLI + YAML configs for the (modularized) build. |
| `deploy/` | AWS EC2 provisioning (`aws-setup.sh`) + cloud-init bootstrap (`user-data.sh`). |

## Data scale (POPPy v2.5, 2026-10-06)

Core (CC BY-NC 4.0): 12,933,298 triples; 43,828 plant nodes (39,941 with >=1 compound; same-species duplicates merged, map in
data/patches/v25_plant_merge_map.tsv.gz) · 208,939 compounds (205,769 linked to a plant; 183,868 with RDKit descriptors;
168,080 of 183,900 structured with a PubChem/ChEMBL/ChEBI/HMDB/DrugBank xref) · 1,013,231 plant-compound links · 62,407 genes · 4,569 pathways
· 1,583 DOID + 1,351 CMAUP ICD-11 diseases · 15,155 trials · 25,756 bioactivity measurements · 74,263 publications.
Module poppy_v2.5_drugcentral_chembl (CC BY-SA 4.0): 1,334 ProteinTarget + 18 MechanismOfAction nodes, 9,987 triples.
Browse layer (`website/data/meta.json`): 39,941 plants · 205,769 compounds · 1,013,231 links.
Build/validation history: `docs/recipes/ontology-v2-rebuild.md`; reports in `data/patches/v241_validation/`, `v25_validation/`.

## Hosting / deploy

- **Live:** `poppyontology.org` — nginx static host on an **AWS EC2** instance (Ubuntu),
  provisioned by `deploy/aws-setup.sh`, bootstrapped by `deploy/user-data.sh`.
- The instance clones the public repo to `/opt/poppy/repo` and serves `website/` from
  `/var/www/poppy`. Redeploy on the box with `sudo poppy-deploy` (git pull + rsync + nginx reload).
- **TLS:** Let's Encrypt via certbot's nginx plugin. One-time after DNS is pointed: `sudo poppy-tls`
  (obtains the cert, adds `listen 443` + an 80→443 redirect, installs the `certbot.timer`
  auto-renewal). The cert lives in `/etc/letsencrypt` and survives `poppy-deploy` (which doesn't
  rewrite the vhost). **Allocate an Elastic IP** and point DNS at it — a plain EC2 public IP
  changes on stop/start, which would break DNS *and* cert renewal.
- **EC2 is the only deployment.** GitHub Pages is NOT used (the Pages workflow was removed —
  it failed to run). Don't re-add a Pages workflow.
- Full ontology (POPPy v2.5: RDF/XML 1.5 GB + N-Triples .nt.gz 136 MB; DrugCentral/ChEMBL module separate, CC BY-SA 4.0) lives on **Box**: https://upenn.box.com/v/poppyontology
  (too large for git; linked from the Download page).

## Conventions / gotchas

- **No build step for the site.** Edit `.html` for content; styles are in `poppy.css` (shared) +
  per-page `<Page>.css`, page logic in per-page `<Page>.js`. `botanical-margins.js` is kept
  **inlined** into each page's `<script id="bm-inline">` block (edit the standalone file, then
  re-inline). It needs `body { isolation: isolate }` (set in its `init()`) so its `z-index:-1`
  specimens render above the body background — don't remove that. See `website/BUILD-NOTES.md`.
- **Cache-busting (no build step):** local `<link>`/`<script>` refs carry a content-hash
  `?v=<sha1>` so returning visitors don't get stale cached assets after a deploy. **After editing
  any `website/*.css` or `*.js`, run `python3 scripts/cache_bust.py`** (idempotent) and commit the
  rewritten HTML. The shared `graph.js` + `ontology-data.js` get one hash across all pages;
  external refs (Google Fonts) are left alone. HTML files themselves rely on nginx revalidation.
- External runtime APIs (degrade gracefully): Wikimedia Commons (plant photos), PubChem
  PUG-REST (structure images), NCBI Gene + UniProt (gene-chip links).
- The big RDF is **not** committed; regenerate `website/data/` from the notebook and commit
  the JSON when data changes.
- CI runs ruff + black on `src`/`scripts` (excludes `src/poppy/ontology/sources`, `scripts/ingest`).

## Persisting work across machines

The public repo is what syncs across machines. The plan + session log are kept in local,
gitignored working notes (not committed) — append a dated entry to the progress log and
update the roadmap there each session. Because they aren't committed, keep your own backup
to carry them between machines.
