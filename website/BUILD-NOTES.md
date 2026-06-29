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
  `<script id="bm-inline">` block (at the end of `<body>`). To update: edit the file, then re-inline
  by replacing each page's `<script id="bm-inline">…</script>` body with the file's contents (no
  literal `</script>` allowed in the JS). A small re-inline loop is in the session notes.
- **z-index/stacking requirement (2026-06-29):** specimens render at `z-index:-1` (behind content).
  `<body>` has an opaque background, so it MUST be a stacking context or the negative-z specimens
  paint *behind* the body background and are invisible at rest (only appearing on hover, when
  z-index jumps to +55). The engine's `init()` now sets `body.style.isolation = "isolate"` to
  guarantee this — **don't remove it.** (This — not inline-vs-external — was the real cause of the
  "margins don't render" regression; an earlier note wrongly blamed external `<script src>`.)
- Inlined vs external is therefore NOT what controls correctness; the engine is kept inlined as the
  known-good state, but the margins bug was purely the stacking-context issue above.
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
