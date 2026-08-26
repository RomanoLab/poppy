#!/usr/bin/env python
"""
classify_nonplants.py — flag (and optionally remove) non-plant records in POPPy.

POPPy's scope is "plant" == falls under NCBI Viridiplantae (taxid 33090) — the same test
scripts/rebuild_ontology.py uses. The COCONUT import let some non-plants (fungi, animals,
bacteria) through; this classifies every record in website/data/plants_index.json by walking
its NCBI lineage offline (the taxdump the enrichment step already downloaded) and reports:

    plant      lineage includes Viridiplantae
    nonplant   resolves to a taxon OUTSIDE Viridiplantae (kingdom named, e.g. Fungi/Metazoa)
    unmatched  name doesn't resolve in NCBI at all

REPORT-FIRST BY DEFAULT: writes data/enrichment/plant_classification.tsv and prints counts,
CHANGING NOTHING. Removal is opt-in:

    --remove-nonplants        drop POSITIVELY non-plant records from plants_index.json (+.bak)
    --also-remove-unmatched   additionally drop unmatched (NOT recommended: unmatched names are
                              often real plants NCBI can't resolve; you'd delete legit taxa)

IMPORTANT: plants_index.json is the WEBSITE index, not the ontology RDF. This cleans what the
site shows; the canonical fix for the ontology is rebuild_ontology.py --plants-only.

USAGE
  python3 scripts/classify_nonplants.py                       # report only
  python3 scripts/classify_nonplants.py --remove-nonplants    # report + prune definite non-plants
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdmp.zip"
VIRIDIPLANTAE = 33090
_NAME_CLASSES = {
    "scientific name",
    "synonym",
    "equivalent name",
    "genbank synonym",
    "common name",
    "genbank common name",
    "includes",
}
_KINGDOM_RANKS = {"kingdom"}
_SUPERKINGDOM_RANKS = {"superkingdom", "domain", "realm", "acellular root", "cellular root"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class Taxonomy:
    def __init__(self, names_dmp: Path, nodes_dmp: Path):
        self.parent: dict[int, int] = {}
        self.rank: dict[int, str] = {}
        self.name2taxid: dict[str, int] = {}
        self.sci: dict[int, str] = {}  # taxid -> scientific name (for kingdom labels)
        self._plant_cache: dict[int, bool] = {}
        with open(nodes_dmp, encoding="utf-8") as fh:
            for line in fh:
                p = line.split("\t|\t")
                if len(p) >= 3:
                    tid = int(p[0])
                    self.parent[tid] = int(p[1])
                    self.rank[tid] = p[2]
        with open(names_dmp, encoding="utf-8") as fh:
            for line in fh:
                p = line.split("\t|\t")
                if len(p) < 4:
                    continue
                nclass = p[3].rstrip("\t|").rstrip("\t|\n").strip()
                if nclass not in _NAME_CLASSES:
                    continue
                tid, name, key = int(p[0]), p[1].strip(), _norm(p[1])
                if nclass == "scientific name":
                    self.sci[tid] = name
                if key and not (key in self.name2taxid and nclass != "scientific name"):
                    self.name2taxid[key] = tid

    def resolve(self, name: str):
        n = _norm(name)
        toks = n.split()
        cands = [n]
        if len(toks) >= 2:
            cands.append(f"{toks[0]} {toks[1]}")
        if toks:
            cands.append(toks[0])
        seen = set()
        for key in cands:
            if key and key not in seen:
                seen.add(key)
                if key in self.name2taxid:
                    return self.name2taxid[key]
        return None

    def _lineage(self, taxid: int):
        seen, cur = set(), taxid
        while cur and cur not in seen:
            yield cur
            seen.add(cur)
            nxt = self.parent.get(cur)
            if nxt is None or nxt == cur:
                break
            cur = nxt

    def is_plant(self, taxid: int) -> bool:
        if taxid in self._plant_cache:
            return self._plant_cache[taxid]
        res = any(a == VIRIDIPLANTAE for a in self._lineage(taxid))
        self._plant_cache[taxid] = res
        return res

    def kingdom_of(self, taxid: int) -> str:
        """Name of the kingdom-ranked ancestor; fall back to superkingdom, else 'unknown'."""
        superk = ""
        for a in self._lineage(taxid):
            r = self.rank.get(a, "")
            if r in _KINGDOM_RANKS:
                return self.sci.get(a, f"taxid:{a}")
            if r in _SUPERKINGDOM_RANKS and not superk:
                superk = self.sci.get(a, f"taxid:{a}")
        return superk or "unknown"

    @classmethod
    def ensure(cls, taxdump_dir: Path) -> "Taxonomy":
        d = Path(taxdump_dir)
        d.mkdir(parents=True, exist_ok=True)
        names, nodes = d / "names.dmp", d / "nodes.dmp"
        if not names.exists() or not nodes.exists():
            zpath = d / "taxdmp.zip"
            if not zpath.exists():
                print(f"downloading taxdump -> {zpath} (~75 MB)...")
                with urlopen(TAXDUMP_URL) as r, open(zpath, "wb") as f:  # noqa: S310
                    f.write(r.read())
            with zipfile.ZipFile(zpath) as z:
                for m in ("names.dmp", "nodes.dmp"):
                    z.extract(m, d)
        return cls(names, nodes)


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--taxdump-dir", default=str(REPO / "data" / "raw" / "taxdump"))
    ap.add_argument(
        "--report-out", default=str(REPO / "data" / "enrichment" / "plant_classification.tsv")
    )
    ap.add_argument(
        "--remove-nonplants",
        action="store_true",
        help="Drop positively non-plant records from plants_index.json (writes .bak).",
    )
    ap.add_argument(
        "--also-remove-unmatched",
        action="store_true",
        help="ALSO drop unmatched records (risky: may delete real plants). Off by default.",
    )
    args = ap.parse_args()

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    print(f"Loaded {len(records):,} records from {plants_path}")

    tax = Taxonomy.ensure(Path(args.taxdump_dir))
    print(f"Taxdump ready: {len(tax.name2taxid):,} names")

    rows = []
    counts = {"plant": 0, "nonplant": 0, "unmatched": 0}
    kingdom_tally: dict[str, int] = {}
    for rec in records:
        sci = rec.get("name", "")
        tid = tax.resolve(sci)
        if tid is None:
            status, kingdom = "unmatched", ""
        elif tax.is_plant(tid):
            status, kingdom = "plant", "Viridiplantae"
        else:
            status, kingdom = "nonplant", tax.kingdom_of(tid)
            kingdom_tally[kingdom] = kingdom_tally.get(kingdom, 0) + 1
        counts[status] += 1
        rows.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "status": status,
                "matched_taxid": tid or "",
                "matched_rank": tax.rank.get(tid, "") if tid else "",
                "kingdom": kingdom,
            }
        )

    report = Path(args.report_out)
    report.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "status",
        "matched_taxid",
        "matched_rank",
        "kingdom",
    ]
    with open(report, "w", encoding="utf-8") as fh:
        fh.write("# classification: plant = under NCBI Viridiplantae (taxid 33090)\n")
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    print("\n=== CLASSIFICATION ===")
    for k in ("plant", "nonplant", "unmatched"):
        print(f"  {k:9s}: {counts[k]:,} ({100*counts[k]/total:.1f}%)")
    if kingdom_tally:
        print("  non-plant by kingdom:")
        for kg, n in sorted(kingdom_tally.items(), key=lambda x: -x[1]):
            print(f"      {kg:18s} {n:,}")
    print(f"  report: {report}")

    if not args.remove_nonplants:
        print(
            "\n[report only] plants_index.json NOT modified. Rerun with --remove-nonplants to prune."
        )
        return 0

    drop = {"nonplant"} | ({"unmatched"} if args.also_remove_unmatched else set())
    keep = [rec for rec, r in zip(records, rows) if r["status"] not in drop]
    removed = len(records) - len(keep)
    backup = plants_path.with_suffix(plants_path.suffix + ".bak")
    shutil.copy2(plants_path, backup)
    plants_path.write_text(json.dumps(keep, ensure_ascii=False, separators=sep))
    print(
        f"\nRemoved {removed:,} records ({'nonplant' if not args.also_remove_unmatched else 'nonplant+unmatched'}); "
        f"kept {len(keep):,}. Backup at {backup}."
    )
    print(
        "NOTE: website plant_edges/ and compounds/ shards may now reference dropped plants; "
        "regenerate site data from the build, or leave orphaned shards (they simply go unrequested)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
