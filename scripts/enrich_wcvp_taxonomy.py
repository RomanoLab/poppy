#!/usr/bin/env python
"""
enrich_wcvp_taxonomy.py — map POPPy plants to WCVP accepted names + POWO/IPNI IDs.

Kew's World Checklist of Vascular Plants (WCVP) is the authority for plant nomenclature. This
joins each record in website/data/plants_index.json to WCVP by scientific name and emits a
BACKEND provenance table with, per organism:

    wcvp_status        Accepted | Synonym | ... (WCVP's status for the matched name)
    wcvp_accepted_name the currently accepted scientific name (resolves synonyms)
    is_synonym         True when your name is an outdated synonym of a different accepted name
    powo_id, ipni_id   stable external identifiers (great for a Scientific Data resource)
    family

This does NOT modify plants_index.json (keeps the website payload lean) — it's a backend file
to fold into the ontology RDF (e.g. skos:exactMatch to the POWO ID, dwc:acceptedNameUsage).
Local bulk join, NO per-name web calls.

Get WCVP: download + unzip Kew's WCVP distribution and point --wcvp-names at wcvp_names.csv
(a '|'-delimited dump). The parser auto-detects the delimiter and the relevant columns, and
prints the columns it found if names differ from what it expects.

USAGE
  python3 scripts/enrich_wcvp_taxonomy.py --wcvp-names data/raw/wcvp/wcvp_names.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def pick(fieldnames, candidates):
    low = {f.lower(): f for f in (fieldnames or [])}
    for c in candidates:
        if c in low:
            return low[c]
    return None


def sniff_delimiter(path: Path) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = fh.readline()
    # WCVP ships pipe-delimited; fall back to tab/comma by whichever splits the header most.
    return max("|\t,", key=lambda d: header.count(d))


def load_wcvp(path: Path):
    delim = sniff_delimiter(path)
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delim)
        cols = reader.fieldnames or []
        name_c = pick(cols, ["taxon_name", "scientificname", "name"])
        status_c = pick(cols, ["taxon_status", "taxonomicstatus", "status"])
        id_c = pick(cols, ["plant_name_id", "plantnameid", "kew_id"])
        acc_c = pick(cols, ["accepted_plant_name_id", "acceptedplantnameid", "accepted_name_id"])
        powo_c = pick(cols, ["powo_id", "powoid"])
        ipni_c = pick(cols, ["ipni_id", "ipniid"])
        fam_c = pick(cols, ["family"])
        rank_c = pick(cols, ["taxon_rank", "rank"])
        if not (name_c and status_c and id_c):
            raise SystemExit(
                f"[wcvp] could not find taxon_name/taxon_status/plant_name_id columns.\n"
                f"       delimiter sniffed: {delim!r}; columns present: {cols}"
            )
        id2name: dict[str, str] = {}
        name2rows: dict[str, list[dict]] = {}
        rows = []
        for row in reader:
            pid = (row.get(id_c) or "").strip()
            nm = (row.get(name_c) or "").strip()
            if pid and nm:
                id2name[pid] = nm
            rec = {
                "name": nm,
                "status": (row.get(status_c) or "").strip(),
                "accepted_id": (row.get(acc_c) or "").strip() if acc_c else "",
                "powo_id": (row.get(powo_c) or "").strip() if powo_c else "",
                "ipni_id": (row.get(ipni_c) or "").strip() if ipni_c else "",
                "family": (row.get(fam_c) or "").strip() if fam_c else "",
                "rank": (row.get(rank_c) or "").strip() if rank_c else "",
            }
            rows.append(rec)
            if nm:
                name2rows.setdefault(_norm(nm), []).append(rec)
    return id2name, name2rows, {"delimiter": delim, "columns": cols, "rows": len(rows)}


def choose_row(rows):
    """Prefer an Accepted match; else the first."""
    for r in rows:
        if r["status"].lower() == "accepted":
            return r
    return rows[0]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--wcvp-names", default=str(REPO / "data" / "raw" / "wcvp" / "wcvp_names.csv"))
    ap.add_argument("--out", default=str(REPO / "data" / "enrichment" / "wcvp_taxonomy.tsv"))
    args = ap.parse_args()

    id2name, name2rows, meta = load_wcvp(Path(args.wcvp_names))
    print(f"[wcvp] loaded {meta['rows']:,} names (delimiter {meta['delimiter']!r})")

    records = json.loads(Path(args.plants_index).read_text())
    print(f"Loaded {len(records):,} plant records")

    rows_out = []
    n_match = n_syn = n_acc = 0
    for rec in records:
        sci = rec.get("name", "")
        hits = name2rows.get(_norm(sci)) or []
        if not hits:
            # genus+species fallback
            toks = _norm(sci).split()
            if len(toks) >= 2:
                hits = name2rows.get(f"{toks[0]} {toks[1]}") or []
        if not hits:
            rows_out.append(
                {
                    "organism_id": rec.get("id", ""),
                    "scientific_name": sci,
                    "wcvp_status": "unmatched",
                    "wcvp_accepted_name": "",
                    "is_synonym": "",
                    "powo_id": "",
                    "ipni_id": "",
                    "family": "",
                }
            )
            continue
        r = choose_row(hits)
        n_match += 1
        if r["status"].lower() == "accepted":
            accepted = r["name"]
            n_acc += 1
        else:
            accepted = id2name.get(r["accepted_id"], "") or ""
        is_syn = bool(accepted) and _norm(accepted) != _norm(r["name"])
        if is_syn:
            n_syn += 1
        rows_out.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "wcvp_status": r["status"],
                "wcvp_accepted_name": accepted,
                "is_synonym": "yes" if is_syn else "no",
                "powo_id": r["powo_id"],
                "ipni_id": r["ipni_id"],
                "family": r["family"],
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "wcvp_status",
        "wcvp_accepted_name",
        "is_synonym",
        "powo_id",
        "ipni_id",
        "family",
    ]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(
            "# source: Kew WCVP (World Checklist of Vascular Plants); matched by scientific name\n"
        )
        fh.write("\t".join(header) + "\n")
        for r in rows_out:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    print("\n=== WCVP TAXONOMY ===")
    print(f"  matched to WCVP:    {n_match:,}/{len(records):,} ({100*n_match/total:.1f}%)")
    print(f"    accepted as-is:   {n_acc:,}")
    print(f"    outdated synonym: {n_syn:,}  (your name differs from WCVP's accepted name)")
    print(f"    unmatched:        {len(records)-n_match:,}")
    print(f"  backend table:      {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
