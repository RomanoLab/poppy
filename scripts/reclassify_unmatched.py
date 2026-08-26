#!/usr/bin/env python
"""
reclassify_unmatched.py — triage the NCBI-unmatched POPPy records via GBIF.

classify_nonplants.py leaves an "unmatched" bucket: names NCBI couldn't resolve. That bucket
is a MIX — real plants that failed on a typo/synonym/author string, plus non-plants (fish,
sponges, fungi) whose names also don't resolve, plus non-taxa (drug names, common names). This
runs each unmatched name through GBIF's fuzzy matcher (which is good at typos and synonyms and
returns the kingdom), and reclassifies it:

    plant            GBIF matched it under kingdom Plantae  (rescued; accepted name recorded)
    nonplant         GBIF matched it under Animalia/Fungi/Bacteria/... (kingdom recorded)
    still_unmatched  GBIF couldn't match either (genuine junk or non-taxonomic name)

Input is the report from classify_nonplants.py (its status=="unmatched" rows). GBIF calls are
cached (resumable). REPORT-FIRST by default; removal of the confirmed non-plants is opt-in.

    --remove-confirmed-nonplants   drop GBIF-confirmed non-plants from plants_index.json (+.bak)

It does NOT rewrite plant names to their accepted form (that changes IDs/labels and is a
separate curation decision) — it records the suggested accepted name so you can decide.

USAGE
  python3 scripts/reclassify_unmatched.py
  python3 scripts/reclassify_unmatched.py --remove-confirmed-nonplants
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GBIF_BASE = "https://api.gbif.org/v1"
PLANT_KINGDOMS = {"plantae", "viridiplantae"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class GBIFMatcher:
    def __init__(self, cache_path: Path, sleep=0.05, timeout=30):
        self.cache_path = Path(cache_path)
        self.sleep, self.timeout = sleep, timeout
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text())
            except Exception:
                self.cache = {}
        self._dirty = 0

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "poppy-reclassify/1.0"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                    return json.loads(r.read().decode())
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.5 * (2**attempt))
        return None

    def match(self, name):
        key = _norm(name)
        if key not in self.cache:
            m = (
                self._get(
                    f"{GBIF_BASE}/species/match?"
                    + urllib.parse.urlencode({"name": name, "strict": "false"})
                )
                or {}
            )
            self.cache[key] = {
                "matchType": m.get("matchType", "NONE"),
                "kingdom": m.get("kingdom", ""),
                "rank": m.get("rank", ""),
                "confidence": m.get("confidence", ""),
                "accepted": m.get("scientificName") or m.get("canonicalName") or "",
                "usageKey": m.get("usageKey"),
            }
            self._dirty += 1
            time.sleep(self.sleep)
            if self._dirty >= 200:
                self._flush()
        return self.cache[key]

    def _flush(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache))
        self._dirty = 0

    def close(self):
        if self._dirty:
            self._flush()


def load_unmatched(report_path: Path):
    out = []
    with open(report_path, encoding="utf-8") as fh:
        for row in csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"):
            if row.get("status") == "unmatched":
                out.append((row.get("organism_id", ""), row.get("scientific_name", "")))
    return out


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument(
        "--report-in", default=str(REPO / "data" / "enrichment" / "plant_classification.tsv")
    )
    ap.add_argument(
        "--cache", default=str(REPO / "data" / "enrichment" / "gbif_reclassify_cache.json")
    )
    ap.add_argument(
        "--out", default=str(REPO / "data" / "enrichment" / "unmatched_reclassified.tsv")
    )
    ap.add_argument("--remove-confirmed-nonplants", action="store_true")
    args = ap.parse_args()

    unmatched = load_unmatched(Path(args.report_in))
    print(f"Unmatched records to triage: {len(unmatched):,}")
    gbif = GBIFMatcher(Path(args.cache))
    print(f"[gbif] cache: {len(gbif.cache):,} memoized")

    rows = []
    counts = {"plant": 0, "nonplant": 0, "still_unmatched": 0}
    kingdom_tally: dict[str, int] = {}
    nonplant_ids = set()
    for i, (oid, sci) in enumerate(unmatched):
        m = gbif.match(sci)
        mt = (m.get("matchType") or "NONE").upper()
        kingdom = m.get("kingdom") or ""
        if mt == "NONE" or not m.get("usageKey"):
            status = "still_unmatched"
        elif _norm(kingdom) in PLANT_KINGDOMS:
            status = "plant"
        else:
            status = "nonplant"
            nonplant_ids.add(oid)
            kingdom_tally[kingdom or "unknown"] = kingdom_tally.get(kingdom or "unknown", 0) + 1
        counts[status] += 1
        rows.append(
            {
                "organism_id": oid,
                "scientific_name": sci,
                "new_status": status,
                "gbif_matchType": mt,
                "gbif_confidence": m.get("confidence", ""),
                "gbif_kingdom": kingdom,
                "gbif_accepted_name": m.get("accepted", ""),
            }
        )
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1:,}/{len(unmatched):,}")
    gbif.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "new_status",
        "gbif_matchType",
        "gbif_confidence",
        "gbif_kingdom",
        "gbif_accepted_name",
    ]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("# GBIF fuzzy reclassification of NCBI-unmatched records\n")
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(unmatched) or 1
    print("\n=== RECLASSIFICATION ===")
    for k in ("plant", "nonplant", "still_unmatched"):
        print(f"  {k:16s}: {counts[k]:,} ({100*counts[k]/total:.1f}%)")
    if kingdom_tally:
        print("  reclassified non-plant by kingdom:")
        for kg, n in sorted(kingdom_tally.items(), key=lambda x: -x[1]):
            print(f"      {kg:16s} {n:,}")
    print(f"  report: {out}")

    if not args.remove_confirmed_nonplants:
        print(
            "\n[report only] plants_index.json NOT modified. "
            "Rerun with --remove-confirmed-nonplants to prune the GBIF-confirmed non-plants."
        )
        return 0

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    keep = [rec for rec in records if rec.get("id", "") not in nonplant_ids]
    removed = len(records) - len(keep)
    backup = plants_path.with_suffix(plants_path.suffix + ".bak")
    shutil.copy2(plants_path, backup)
    plants_path.write_text(json.dumps(keep, ensure_ascii=False, separators=sep))
    print(
        f"\nRemoved {removed:,} GBIF-confirmed non-plants; kept {len(keep):,}. Backup at {backup}."
    )
    print(
        "Plants GBIF rescued keep their ORIGINAL names; see gbif_accepted_name in the report "
        "if you want to correct them later."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
