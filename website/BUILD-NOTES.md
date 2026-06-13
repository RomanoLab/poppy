# POPPy — project notes

## Pending task (next session)
- **DONE (2026-06):** Cut-out PNGs in `assets/cutouts/` were downscaled to ~900px longest edge
  (transparency preserved). All 24 now ~0.5–1.1 MB.
- Optional, still open: re-encode `assets/plates/*.jpg` to ~1300px to shrink the hover-reveal scans.

## Botanical margins system
- Engine: `botanical-margins.js`, INLINED into Home/About/Download/Contact inside
  `<script id="bm-inline">` (do NOT rely on an external <script src> — it caused blank pages).
  To update: edit `botanical-margins.js`, then re-inline by replacing everything from
  `<script id="bm-inline">` through `</body>` in each page. Never let a literal `</script>`
  appear in the JS (breaks the inline tag).
- Behavior: diagonal ladder of recycling "specimen slots", alternating L/R. Each slot draws the
  next species from a rotating sequence on every viewport entrance, so scrolling up/down shows
  fresh plants. Cut-out at rest + Latin name; hold cursor 1s → full Köhler plate fades in.
- Tunable via CSS vars on :root: `--bm-rest-op`, `--bm-full-op`, `--bm-scale`; `body.bm-hidden` hides all.

## Tweaks panel (Home.html only)
- Vanilla, in `<script id="tw-inline">`. Controls: Specimens show/hide, Fade, Size, Accent color.
- Persistence JSON lives in the `/*EDITMODE-BEGIN*/ ... /*EDITMODE-END*/` block.

## Source
- `src/` is the user's local Astro repo (read-only mount). The HTML files here are the previewable
  build the user reviews. Can't write back to `src/`; provide integration notes if porting.
