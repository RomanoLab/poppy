#!/usr/bin/env python
"""
enrich_common_names_duke.py — fill remaining common-name gaps from Dr. Duke's database.

Runs ONLY on plants_index.json records that still lack a ``common`` field after the
GBIF/NCBI/Wikidata passes, and fills them from Dr. Duke's ethnobotanical common names.

Duke's keys common names on an internal taxon id (FNFNUM), so this joins two of Duke's tables:
    FNFTAX.csv       FNFNUM -> TAXON (scientific name)          [verified: FNFNUM 1 = Abelmoschus esculentus]
    COMMON_NAMES.csv CNNAM  -> FNFNUM (common name -> taxon id)
giving scientific-name -> common-name(s), matched to plants_index by scientific name
(full name, then genus+species). Local CSV join, NO network. Gap-only: never overwrites an
existing common name. Writes a provenance TSV and reports the coverage lift.

USAGE (run after the other enrichment passes)
  python3 scripts/enrich_common_names_duke.py --dry-run
  python3 scripts/enrich_common_names_duke.py
Defaults expect the unzipped Duke-Source-CSV in data/raw/ (FNFTAX.csv, COMMON_NAMES.csv).
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def build_duke_map(fnftax_path: Path, common_path: Path):
    """Return {normalised scientific name: [common names]} and some stats."""
    id2taxon: dict[str, str] = {}
    with open(fnftax_path, encoding="utf-8", errors="replace") as fh:
        r = csv.DictReader(fh)
        if not r.fieldnames or "FNFNUM" not in r.fieldnames or "TAXON" not in r.fieldnames:
            raise SystemExit(f"[duke] FNFTAX.csv missing FNFNUM/TAXON columns; has {r.fieldnames}")
        for row in r:
            fid, taxon = (row.get("FNFNUM") or "").strip(), (row.get("TAXON") or "").strip()
            if fid and taxon:
                id2taxon[fid] = taxon

    sci2common: dict[str, list[str]] = {}
    n_rows = 0
    with open(common_path, encoding="utf-8", errors="replace") as fh:
        r = csv.DictReader(fh)
        if not r.fieldnames or "CNNAM" not in r.fieldnames or "FNFNUM" not in r.fieldnames:
            raise SystemExit(
                f"[duke] COMMON_NAMES.csv missing CNNAM/FNFNUM columns; has {r.fieldnames}"
            )
        for row in r:
            cn, fid = (row.get("CNNAM") or "").strip(), (row.get("FNFNUM") or "").strip()
            taxon = id2taxon.get(fid)
            if cn and taxon:
                key = _norm(taxon)
                sci2common.setdefault(key, [])
                if cn not in sci2common[key]:
                    sci2common[key].append(cn)
                n_rows += 1
    return sci2common, {
        "taxa": len(id2taxon),
        "sci_with_common": len(sci2common),
        "name_rows": n_rows,
    }


def duke_lookup(sci2common, name):
    n = _norm(name)
    toks = n.split()
    for key in (n, f"{toks[0]} {toks[1]}" if len(toks) >= 2 else None):
        if key and key in sci2common:
            return sci2common[key]
    return None


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--fnftax", default=str(REPO / "data" / "raw" / "FNFTAX.csv"))
    ap.add_argument("--common-names", default=str(REPO / "data" / "raw" / "COMMON_NAMES.csv"))
    ap.add_argument(
        "--provenance-out", default=str(REPO / "data" / "enrichment" / "duke_common_names.tsv")
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sci2common, stats = build_duke_map(Path(args.fnftax), Path(args.common_names))
    print(
        f"[duke] {stats['taxa']:,} taxa in FNFTAX; {stats['sci_with_common']:,} taxa with common names "
        f"({stats['name_rows']:,} name rows)"
    )

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    already = sum(1 for r in records if r.get("common"))
    gaps = [r for r in records if not r.get("common")]
    print(f"Loaded {len(records):,} records; {already:,} already named; {len(gaps):,} gaps to try")

    retrieved = _dt.date.today().isoformat()
    prov, filled = [], 0
    for rec in gaps:
        sci = rec.get("name", "")
        commons = duke_lookup(sci2common, sci)
        name = commons[0] if commons else None
        if name:
            rec["common"] = name
            filled += 1
        prov.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "duke_common_name": name or "",
                "all_duke_common_names": "; ".join(commons or []),
            }
        )

    prov_path = Path(args.provenance_out)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    header = ["organism_id", "scientific_name", "duke_common_name", "all_duke_common_names"]
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# source: Dr. Duke's Phytochemical & Ethnobotanical Database "
            "(COMMON_NAMES.csv joined to FNFTAX.csv via FNFNUM)\n"
        )
        fh.write(f"# retrieved/processed: {retrieved}\n")
        fh.write("\t".join(header) + "\n")
        for r in prov:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    new_total = already + filled
    print("\n=== DUKE GAP-FILL ===")
    print(f"  filled this pass:   {filled:,}/{len(gaps):,} gaps")
    print(f"  coverage before:    {already:,}/{len(records):,} ({100*already/total:.1f}%)")
    print(f"  coverage after:     {new_total:,}/{len(records):,} ({100*new_total/total:.1f}%)")
    print(f"  provenance table:   {prov_path}")

    if args.dry_run:
        print("\n[dry-run] plants_index.json NOT modified.")
        return 0

    backup = plants_path.with_suffix(plants_path.suffix + ".bak")
    shutil.copy2(plants_path, backup)
    plants_path.write_text(json.dumps(records, ensure_ascii=False, separators=sep))
    print(f"\nWrote enriched {plants_path} (backup at {backup}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
