# POPPy — Website (full source)

The complete front-end source for the **POPPy** (Phyto-Ontology Platform for
Pharmacology) website. This is the *whole thing* — there is **no build step and
no framework**. Every page is a self-contained HTML file that holds its own
markup, CSS (in a `<style>` block), and JavaScript (in `<script>` blocks). Open
any `.html` file in a browser and it runs. To recreate the site, you only need
these files served over HTTP.

## Live pages (site root)

| File | Page |
|------|------|
| `Home.html` | Home — hero, search, connection graph, featured species |
| `Explore.html` | Explore — entity register: connections, attributes, NCBI gene layer, CSV export, specimen images |
| `About.html` | About / Overview |
| `Method.html` | Method — how the ontology is built |
| `Team.html` | Team |
| `Citation.html` | Citation + documentation link |
| `Download.html` | Download builder |
| `Herbarium.html` | Herbarium plate gallery |
| `Contact.html` | Contact |
| `Privacy.html` · `Terms.html` | Legal |

`Home.html` is the entry point. Internal links use `Home.html` (not
`index.html`) — see **Hosting** below if you deploy to a static host.

## Shared code & data

- **`ontology-data.js`** — the single source of truth for the knowledge graph.
  Exposes `window.POPPY` with `NODES` (entities) and `EDGES` (relationships),
  plus helper functions. **Home and Explore both read from this one file.**
  To wire in the real ontology, replace `NODES` and `EDGES` here (keep the
  documented shape) and every feature — graph, register, CSV, gene chips,
  image lookups — updates automatically. The shape is documented at the top
  of the file.
- **`botanical-margins.js`** — the scroll-driven specimen-margin engine. NOTE:
  this is the *editable source*; in the live pages it is **inlined** inside a
  `<script id="bm-inline">` block (an external `<script src>` caused blank
  pages). To change it: edit this file, then re-paste it into each page's
  `bm-inline` block. See `BUILD-NOTES.md`.

## Assets

`assets/` — `poppy-logo.png`, plus `cutouts/` (transparent specimen PNGs) and
`plates/` (full Köhler plate scans) used by the Herbarium and the botanical
margins. 24 species each.

## External services (hot-linked at runtime — nothing stored in the repo)

- **Wikimedia Commons** (MediaWiki API) — plant photographs on Explore + featured species
- **PubChem** (PUG REST) — 2D compound structure images on Explore
- **NCBI Gene** + **UniProt** — outbound links from the gene chips on Explore

A hosted copy needs internet access for these to resolve; the pages degrade
gracefully (placeholder) if a lookup fails.

## design-explorations/

Earlier design studies kept for provenance — **not part of the live site** and
not linked from it: React/JSX prototypes (`*.jsx`) and alternate layout drafts
(`Designs.html`, `*-options.html`, `Subpage Layouts.html`, `Herbarium
Options.html`). Safe to delete if you only want the shipping site.

## Run locally

```bash
# from this folder
python3 -m http.server 8000
# then open http://localhost:8000/Home.html
```

(Any static file server works. Opening `Home.html` directly via `file://` also
mostly works, but a server is recommended so the external API calls behave.)

## Hosting (e.g. GitHub Pages)

Static hosts serve `index.html` at a directory root. Two options:
1. Copy `Home.html` to `index.html` (and update the `href="Home.html"` links to
   `href="index.html"`), **or**
2. Add a redirect `index.html` that points at `Home.html`.

## Build notes

See `BUILD-NOTES.md` (the project's working notes) for details on the botanical
margins system, the tweak panel, and asset handling.
