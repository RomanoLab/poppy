# Bringing POPPy online — handoff notes

The website is built and wired to the real ontology; it just needs to be published.
Everything below happens in **RomanoLab/poppy** after the PR from `ohewryk:main` is merged.

## Publish the website (GitHub Pages)

1. **Review & merge** the open PR (`ohewryk:main → main`). The diff adds the static
   site (`website/`), its data layer (`website/data/`), the build notebook
   (`notebooks/`), a Pages workflow, and a Box download link; it removes the old
   `web/` stub.
2. In **Settings → Pages → Build and deployment → Source**, choose **GitHub Actions**.
3. The workflow `.github/workflows/pages.yml` publishes the `website/` folder on every
   push to `main`. The first run deploys it; the live URL appears at the top of
   Settings → Pages (it will be `https://romanolab.github.io/poppy/`).
4. **Verify:** open that URL → **Explore** → search a plant (e.g. *Panax ginseng*) →
   confirm it loads and lists compounds. The homepage redirects from `index.html` to
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
