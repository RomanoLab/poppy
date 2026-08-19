# Recipe: plant cleanup + common-name enrichment pipeline

End-to-end pipeline that cleans non-plant contamination out of `website/data/plants_index.json`
and attaches English common names to the plant taxa from four sources, with full provenance.
All scripts are stdlib-only and run from the repo root.

## Result on the reference run

Started 45,268 records → removed 1,883 non-plants/junk → **43,385 clean plant taxa**.
Common names on **18,939 (43.7%)**: gbif 15,825 · wikidata 1,829 · ncbi 1,046 · duke 239.
Remainder are taxa with no English common name in any of the four sources.

## Order of operations

Run these from the repo root, in order. Cleanup first, then enrichment (each enrichment pass is
gap-only — it never overwrites an existing common name). Steps that hit the network are marked;
wrap long ones in `caffeinate -i` on macOS so a closed lid doesn't kill them.

| # | Script | What | Network | Removes/edits |
|---|--------|------|---------|---------------|
| 1 | `classify_nonplants.py --remove-nonplants` | drop taxa outside NCBI Viridiplantae | taxdump DL once | removes non-plants |
| 2 | `reclassify_unmatched.py --remove-confirmed-nonplants` | GBIF-triage the NCBI-unmatched; rescue misspelled plants, drop confirmed animals/fungi | GBIF | removes confirmed non-plants |
| 3 | `tag_unmatched_junk.py --remove-junk` | drop drug-names/strains/non-plant common names from the residue | none | removes junk |
| 4 | `enrich_common_names_layered.py --sources gbif,ncbi` | common names from GBIF (+ accepted names) then NCBI | GBIF | adds `common` |
| 5 | `enrich_common_names_wikidata.py` | fill gaps from Wikidata P1843 + labels/aliases | Wikidata | adds `common` |
| 6 | `enrich_common_names_duke.py` | fill gaps from Dr. Duke's (FNFTAX⋈COMMON_NAMES) | none (local CSVs) | adds `common` |
| 7 | `build_common_name_sources.py` | backend per-organism source tag (ncbi/gbif/wikidata/duke) | none | writes sources TSV |

Every step is **report-first / backed up**: cleanup steps write a `.bak` and an itemized report
before removing; enrichment writes a `.bak`. Nothing is irreversible.

## Inputs

- NCBI taxdump: auto-downloads to `data/raw/taxdump/` on step 1 (~75 MB).
- Dr. Duke's: unzip `Duke-Source-CSV.zip` (Ag Data Commons) into `data/raw/` — steps 6 needs
  `FNFTAX.csv` + `COMMON_NAMES.csv`.
- Caches (resumable, keyed by name): `data/enrichment/gbif_cache.json`,
  `gbif_reclassify_cache.json`, `wikidata_cache.json`. Keep them to avoid re-querying; delete a
  cache only to force a clean re-query.

## Outputs / provenance (the paper's audit trail)

- `website/data/plants_index.json` — cleaned + enriched (the deployed website data).
- `data/enrichment/plant_classification.tsv` — plant/nonplant/unmatched per record (step 1).
- `data/enrichment/unmatched_reclassified.tsv` — GBIF triage of the unmatched (step 2).
- `data/enrichment/unmatched_junk_tags.tsv` — junk vs possible_plant (step 3).
- `data/enrichment/common_names_layered.tsv` — GBIF/NCBI provenance + GBIF accepted names (step 4).
- `data/enrichment/wikidata_common_names.tsv` — Wikidata QIDs + field used (step 5).
- `data/enrichment/duke_common_names.tsv` — Duke matches (step 6).
- `data/enrichment/common_name_sources.tsv` — **backend** per-organism source tag (step 7).
  Not added to `plants_index.json`; not shipped to the browser. Fold into the ontology RDF as a
  `dc:source` annotation per common-name triple during the next rebuild.

## Website

`Explore.js` already renders a record's `common` field as a vernacular name, so deploying the
enriched `plants_index.json` surfaces common names with no front-end change. After deploy, also
update the homepage plant count and `website/data/meta.json` (now ~43,385, not 45,268). The
`plant_edges/` and `compounds/` shards still reference removed non-plants — harmless (unrequested)
but regenerate from the build when convenient. The source tag is intentionally backend-only.

## Do NOT commit

Add to `.gitignore`: `data/enrichment/*_cache.json`, `website/data/*.bak`, and the large
`data/raw/` inputs (taxdump, Duke CSVs). Commit the scripts, the enriched `plants_index.json`,
and the provenance TSVs.
