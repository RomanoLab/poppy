# Bringing POPPy online — handoff notes

The website is built and wired to the real ontology; it just needs to be published.
Everything below happens in **RomanoLab/poppy** after the PR from `ohewryk:main` is merged.

## Publish the website (AWS EC2)

> **Historical note:** earlier drafts of this doc described a GitHub Pages deploy. **Pages is
> no longer used** (the workflow was removed). The live site is hosted on **AWS EC2** at
> **poppyontology.org**.

1. Provision the server with `bash deploy/aws-setup.sh` (nginx + static host; see
   `deploy/user-data.sh` for the cloud-init bootstrap). Point `poppyontology.org` DNS at the
   instance's public IP.
2. The instance clones the public repo to `/opt/poppy/repo` and serves `website/` from
   `/var/www/poppy`.
3. To deploy updates after pushing to `main`: SSH in and run `sudo poppy-deploy`
   (git pull + rsync + nginx reload).
4. **Verify:** open https://poppyontology.org → **Explore** → search a plant
   (e.g. *Panax ginseng*) → confirm it loads and lists compounds. `index.html` redirects to
   `Home.html`.

## What lives where

- **`website/`** — the static site (plain HTML/CSS/JS, no build step). `Home.html` and
  `Explore.html` are wired to real ontology data.
- **`website/data/`** — sharded JSON the Explore page loads at runtime: `plants_index.json`
  (search), `plant_edges/` and `compounds/` (lazy-loaded per plant). ~50 MB, committed.
- **Full ontology (RDF/XML, ~2 GB)** — on **Box**: https://upenn.box.com/v/poppyontology
  (linked from the Download page). Too large for Git, intentionally not committed.
- **`notebooks/Ontology_Work_clean.ipynb`** — the end-to-end build pipeline; the
  authoritative record of how the ontology was produced.
- **`data/SOURCES.md`** — every input dataset, version, and where to obtain it.
- **`data/ontology/poppystructure.rdf`** — the hand-curated TBox scaffold.

## How the site uses the ontology

The Explore page searches **all ~59,700 organisms** in the data layer and lazy-loads each
one's compounds on click. The 24 curated "plate" species render richer (targets,
therapeutic effects, citations); the rest show the plant and its compounds.

## Updating the data later

Re-run the notebook → regenerate `website/data/` (the data-layer cell) → commit. Push to
`main` and Pages redeploys automatically. The big RDF goes to Box, not the repo.

## Known limitation

The full organism set currently includes some **non-plant organisms** (bacteria, fungi,
e.g. *Streptomyces*, *Penicillium*, *Homo sapiens*) pulled in by the COCONUT 2.0 import,
which did not run the NCBI/POWO plant validation the base pipeline uses. A taxonomy filter
to restrict the browse to true plants is a planned follow-up; it does not affect the
curated species or the site's functionality.
