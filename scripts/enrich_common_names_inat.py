#!/usr/bin/env python
"""
enrich_common_names_inat.py — fill remaining common-name gaps from iNaturalist.

Runs ONLY on plants_index.json records that still lack a ``common`` field after the
GBIF/NCBI/Wikidata/Duke passes, and fills them from iNaturalist's ``preferred_common_name``.

For each unnamed scientific name it queries the iNat taxa API
(``/v1/taxa?q=<name>&rank=species``), takes the result whose scientific ``name`` matches the
query, and uses its ``preferred_common_name`` (English by default). Gap-only: never overwrites
an existing common name. Cached (resumable). Writes a provenance TSV; reports the coverage lift.

RATE: iNat asks for a descriptive User-Agent and modest rates (~1 req/s). With ~24k gaps this
is a multi-hour run — but it's cached to disk and resumable, so run it overnight; reruns are
instant for names already fetched.

USAGE (run after the other enrichment passes; needs network)
  python3 scripts/enrich_common_names_inat.py --dry-run     # coverage lift + TSV, no JSON edit
  python3 scripts/enrich_common_names_inat.py --limit 50 --dry-run   # smoke test
  python3 scripts/enrich_common_names_inat.py               # fill gaps in plants_index.json (+.bak)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INAT_API = "https://api.inaturalist.org/v1/taxa"
UA = "poppy-inat-enrich/1.0 (https://github.com/RomanoLab/poppy; ontology common-name enrichment)"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class INatSource:
    def __init__(self, cache_path: Path, sleep=1.0, timeout=30):
        self.cache_path = Path(cache_path)
        self.sleep, self.timeout = sleep, timeout
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text())
            except Exception:
                self.cache = {}
        self._dirty = 0

    def _get(self, params):
        url = INAT_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                    return json.loads(r.read().decode())
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1.0 * (2**attempt))
        return None

    def lookup(self, name):
        key = _norm(name)
        if key not in self.cache:
            rec = {"common": "", "inat_id": None, "matched_name": ""}
            try:
                r = self._get({"q": name, "rank": "species", "per_page": 5, "is_active": "true"})
                for res in (r or {}).get("results", []):
                    if _norm(res.get("name", "")) == key:
                        rec = {
                            "common": (res.get("preferred_common_name") or "").strip(),
                            "inat_id": res.get("id"),
                            "matched_name": res.get("name", ""),
                        }
                        break
            except Exception:
                pass
            self.cache[key] = rec
            self._dirty += 1
            time.sleep(self.sleep)
            if self._dirty >= 100:
                self._flush()
        return self.cache[key]

    def _flush(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache))
        self._dirty = 0

    def close(self):
        if self._dirty:
            self._flush()


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--cache", default=str(REPO / "data" / "enrichment" / "inat_cache.json"))
    ap.add_argument(
        "--provenance-out", default=str(REPO / "data" / "enrichment" / "inat_common_names.tsv")
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="Process only first N gap records (smoke test)."
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    already = sum(1 for r in records if r.get("common"))
    gaps = [r for r in records if not r.get("common")]
    if args.limit:
        gaps = gaps[: args.limit]
    print(
        f"Loaded {len(records):,} records; {already:,} already named; {len(gaps):,} gaps to try"
        + (f" (limited to {args.limit})" if args.limit else "")
    )

    inat = INatSource(Path(args.cache))
    print(f"[inat] cache: {len(inat.cache):,} memoized")

    retrieved = _dt.date.today().isoformat()
    prov, filled = [], 0
    for i, rec in enumerate(gaps):
        sci = rec.get("name", "")
        r = inat.lookup(sci)
        name = (r.get("common") or "").strip()
        if name:
            rec["common"] = name
            filled += 1
        prov.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "inat_common_name": name,
                "inat_taxon_id": r.get("inat_id") or "",
            }
        )
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1:,}/{len(gaps):,} tried, {filled:,} filled")
    inat.close()

    prov_path = Path(args.provenance_out)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    header = ["organism_id", "scientific_name", "inat_common_name", "inat_taxon_id"]
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# source: iNaturalist taxa API (preferred_common_name), matched by scientific name\n"
        )
        fh.write(f"# retrieved: {retrieved}\n")
        fh.write("\t".join(header) + "\n")
        for r in prov:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    new_total = already + filled
    print("\n=== iNATURALIST GAP-FILL ===")
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
