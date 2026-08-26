#!/usr/bin/env python
"""
build_common_name_sources.py — per-organism provenance of WHERE each common name came from.

Backend-only. Reads the current plants_index.json plus the provenance TSVs written by the three
enrichment passes, and emits one row per organism that HAS a common name, tagged with its source:

    ncbi | gbif | wikidata | duke

Because the passes ran gap-only in a fixed order (layered GBIF/NCBI, then Wikidata, then Duke),
source is assigned by that precedence: whichever pass first supplied the name owns it.

Output: data/enrichment/common_name_sources.tsv  (organism_id, scientific_name, common_name, source)
This is NOT added to plants_index.json — it stays out of the website payload. It's the backend
record you can load for analysis or fold into the ontology RDF as a dc:source annotation per
common-name triple.

USAGE (run after all enrichment passes, from repo root)
  python3 scripts/build_common_name_sources.py
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENR = REPO / "data" / "enrichment"


def read_tsv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--layered", default=str(ENR / "common_names_layered.tsv"))
    ap.add_argument("--wikidata", default=str(ENR / "wikidata_common_names.tsv"))
    ap.add_argument("--duke", default=str(ENR / "duke_common_names.tsv"))
    ap.add_argument("--out", default=str(ENR / "common_name_sources.tsv"))
    args = ap.parse_args()

    records = json.loads(Path(args.plants_index).read_text())

    # organism_id -> source, from each pass (gap-only, so precedence = run order)
    lay = {}
    for r in read_tsv(Path(args.layered)):
        if r.get("display_common_name"):
            cs = (r.get("chosen_source") or "").strip()
            if cs in ("gbif", "ncbi"):
                lay[r["organism_id"]] = cs
    wd = {r["organism_id"] for r in read_tsv(Path(args.wikidata)) if r.get("wikidata_common_name")}
    dk = {r["organism_id"] for r in read_tsv(Path(args.duke)) if r.get("duke_common_name")}

    rows, tally, unattributed = [], {}, 0
    for rec in records:
        common = rec.get("common")
        if not common:
            continue
        oid = rec.get("id", "")
        if oid in lay:
            src = lay[oid]
        elif oid in wd:
            src = "wikidata"
        elif oid in dk:
            src = "duke"
        else:
            src = "unknown"
            unattributed += 1
        tally[src] = tally.get(src, 0) + 1
        rows.append(
            {
                "organism_id": oid,
                "scientific_name": rec.get("name", ""),
                "common_name": common,
                "source": src,
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = ["organism_id", "scientific_name", "common_name", "source"]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("# per-organism common-name source; precedence gbif/ncbi > wikidata > duke\n")
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    print(f"Wrote {len(rows):,} source-tagged rows -> {out}")
    for s in ("ncbi", "gbif", "wikidata", "duke", "unknown"):
        if tally.get(s):
            print(f"  {s:9s}: {tally[s]:,}")
    if unattributed:
        print(
            f"  NOTE: {unattributed:,} common names could not be attributed to a provenance file "
            "(re-run the enrichment passes so their TSVs match the current index)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
