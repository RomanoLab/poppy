# Web

Static site for POPPy. Deploy with GitHub Pages.

## Local preview
Open `web/index.html` in a browser, or serve locally:
```bash
python -m http.server --directory web 8080
```

## Publishing
- Push to GitHub main branch with these files committed.
- The GitHub Actions workflow `.github/workflows/pages.yml` publishes `web/` to Pages.

## Data
- Place build outputs in `web/data/` (e.g., `ontology_stats.json`, `phytotherapies_enriched.ttl`).
- Run `make -C build web-data` to copy the latest build artifacts.
