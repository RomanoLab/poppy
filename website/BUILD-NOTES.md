# POPPy — project notes

## Pending task (next session)
- **DONE (2026-06):** Cut-out PNGs in `assets/cutouts/` were downscaled to ~900px longest edge
  (transparency preserved). All 24 now ~0.5–1.1 MB.
- Optional, still open: re-encode `assets/plates/*.jpg` to ~1300px to shrink the hover-reveal scans.

## Asset organization (refactored 2026-06-24)
Pages are now **content-only HTML**; styles and scripts live in their own files (still **no build
step** — nginx serves the `.css`/`.js` directly):
- **`poppy.css`** — shared base stylesheet, linked by the pages that match it (Team, About,
  Citation, Privacy, Terms).
- **`<Page>.css`** — page-specific stylesheet for pages whose styles had drifted from the base
  (Home, Method, Explore, Download, Contact, Herbarium); these link only their own sheet.
  *(Reconciling these back onto `poppy.css` is a safe future cleanup.)*
- **`<Page>.js`** — page-specific scripts (Home, Explore, Download, Contact, Citation, Herbarium).
- External `<script src>` data files (`ontology-data.js`, etc.) stay as they were.
- Two small in-markup `<style>` blocks remain inline (Method, Download) — they sit next to the
  content they style; left intentionally.

## Botanical margins system
- Engine: `botanical-margins.js` is the editable SOURCE; it is **INLINED** into each page's
  `<script id="bm-inline">` block (at the end of `<body>`). **Do NOT switch it to an external
  `<script src>`** — tried again 2026-06-24 during the asset refactor and the margins stopped
  rendering (confirmed in-browser; consistent with the original author's note). External CSS is
  fine; only the bm *script* must stay inlined. The standalone file is byte-identical to the
  inlined copy, so to update: edit `botanical-margins.js`, then re-inline by replacing each page's
  `<script id="bm-inline">…</script>` body with the file's contents (no literal `</script>` allowed
  in the JS). A small re-inline loop is in the session notes if needed.
- Behavior: diagonal ladder of recycling "specimen slots", alternating L/R. Each slot draws the
  next species from a rotating sequence on every viewport entrance, so scrolling up/down shows
  fresh plants. Cut-out at rest + Latin name; hold cursor 1s → full Köhler plate fades in.
- Per-page rotation via `<body data-bm-start="N">`. Tunable via CSS vars on :root:
  `--bm-rest-op`, `--bm-full-op`, `--bm-scale`; `body.bm-hidden` hides all.

## Tweaks panel — REMOVED 2026-06-24
- The dev-only Tweaks panel (`tw-style`/`tw-panel`/`tw-inline`) was deleted from Home & Method
  (it was never meant to ship). The Contact "Preview note" demo block was also removed.

## Source
- `src/` is the user's local Astro repo (read-only mount). The HTML files here are the previewable
  build the user reviews. Can't write back to `src/`; provide integration notes if porting.
