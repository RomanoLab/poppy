#!/usr/bin/env python
"""
enrich_common_names_wikidata.py — fill remaining common-name gaps from Wikidata.

Runs ONLY on plants_index.json records that still have no ``common`` field after the
GBIF/NCBI pass, and tries to fill them from Wikidata:

  1. find the taxon item by exact scientific name  (haswbstatement:P225=<name>)
  2. read its common names, preferring property P1843 "taxon common name" (English),
     then the item's English label, then an English alias — never the scientific name itself.

It does NOT overwrite existing common names; it only adds to records that lack one. Writes a
provenance TSV (organism_id, scientific_name, QID, chosen name, which field it came from) and
reports the coverage lift. Wikidata calls are cached (resumable). Stdlib only; runs on any repo.

USAGE (run after enrich_common_names_layered.py; needs network)
  python3 scripts/enrich_common_names_wikidata.py --dry-run     # coverage lift + TSV, no JSON edit
  python3 scripts/enrich_common_names_wikidata.py               # fill gaps in plants_index.json (+.bak)
  python3 scripts/enrich_common_names_wikidata.py --langs en    # (default en)

Politeness: sends a descriptive User-Agent and sleeps between calls per Wikidata's API etiquette.
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
WD_API = "https://www.wikidata.org/w/api.php"
UA = "poppy-wikidata-enrich/1.0 (https://github.com/RomanoLab/poppy; ontology common-name enrichment)"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class WikidataSource:
    def __init__(self, cache_path: Path, langs, sleep=0.10, timeout=30):
        self.cache_path = Path(cache_path)
        self.langs = [lang.strip().lower() for lang in langs]
        self.sleep, self.timeout = sleep, timeout
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text())
            except Exception:
                self.cache = {}
        self._dirty = 0

    def _get(self, params):
        url = WD_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                    return json.loads(r.read().decode())
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.5 * (2**attempt))
        return None

    def _search_candidates(self, name):
        """wbsearchentities: name -> candidate item QIDs (handles spaces in binomials)."""
        r = self._get(
            {
                "action": "wbsearchentities",
                "search": name,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "limit": 5,
                "format": "json",
            }
        )
        return [h["id"] for h in (r or {}).get("search", []) if h.get("id")]

    def _search_by_statement(self, name):
        """Fallback: exact P225 statement search (quoted so spaces don't split the value)."""
        r = self._get(
            {
                "action": "query",
                "list": "search",
                "format": "json",
                "srlimit": 3,
                "srprop": "",
                "srsearch": f'haswbstatement:P225="{name}"',
            }
        )
        return [h["title"] for h in ((r or {}).get("query", {}).get("search") or [])]

    def _entity(self, qid):
        r = self._get(
            {
                "action": "wbgetentities",
                "ids": qid,
                "format": "json",
                "props": "labels|aliases|claims",
                "languages": "|".join(self.langs),
            }
        )
        return ((r or {}).get("entities", {}) or {}).get(qid, {})

    def _extract(self, qid, ent):
        p1843, labels, aliases = [], [], []
        for lang in self.langs:
            lab = ent.get("labels", {}).get(lang, {}).get("value")
            if lab:
                labels.append(lab)
            for a in ent.get("aliases", {}).get(lang, []) or []:
                if a.get("value"):
                    aliases.append(a["value"])
        for claim in ent.get("claims", {}).get("P1843", []) or []:
            if claim.get("rank") == "deprecated":
                continue
            dv = (claim.get("mainsnak", {}).get("datavalue", {}) or {}).get("value", {})
            if (
                isinstance(dv, dict)
                and dv.get("language", "").lower() in self.langs
                and dv.get("text")
            ):
                p1843.append(dv["text"])
        return {"qid": qid, "p1843": p1843, "labels": labels, "aliases": aliases}

    def _resolve(self, name):
        """Find the TAXON item for a scientific name and pull its names. Verify via P225 claim."""
        cands = self._search_candidates(name)
        if not cands:
            cands = self._search_by_statement(name)
        for qid in cands[:3]:
            ent = self._entity(qid)
            if "P225" in (ent.get("claims", {}) or {}):  # confirm it's a taxon
                return self._extract(qid, ent)
        return {"qid": None, "p1843": [], "labels": [], "aliases": []}

    def lookup(self, name):
        key = _norm(name)
        if key not in self.cache:
            try:
                self.cache[key] = self._resolve(name)
            except Exception:
                self.cache[key] = {"qid": None, "p1843": [], "labels": [], "aliases": []}
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


def choose_common(rec, scientific):
    """Prefer P1843; then a label/alias that isn't just the scientific name. Returns (name, field)."""
    sci = _norm(scientific)
    if rec.get("p1843"):
        return rec["p1843"][0], "P1843"
    for lab in rec.get("labels", []):
        if _norm(lab) != sci:
            return lab, "label"
    for al in rec.get("aliases", []):
        if _norm(al) != sci:
            return al, "alias"
    return None, ""


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--cache", default=str(REPO / "data" / "enrichment" / "wikidata_cache.json"))
    ap.add_argument(
        "--provenance-out", default=str(REPO / "data" / "enrichment" / "wikidata_common_names.tsv")
    )
    ap.add_argument(
        "--langs", default="en", help="Wikidata language codes, comma list (default en)."
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

    wd = WikidataSource(Path(args.cache), args.langs.split(","))
    print(f"[wikidata] cache: {len(wd.cache):,} memoized; langs={args.langs}")

    retrieved = _dt.date.today().isoformat()
    prov, filled = [], 0
    field_tally: dict[str, int] = {}
    for i, rec in enumerate(gaps):
        sci = rec.get("name", "")
        r = wd.lookup(sci)
        name, field = choose_common(r, sci) if r.get("qid") else (None, "")
        if name:
            rec["common"] = name
            filled += 1
            field_tally[field] = field_tally.get(field, 0) + 1
        prov.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "wikidata_qid": r.get("qid") or "",
                "wikidata_common_name": name or "",
                "source_field": field,
                "all_p1843": "; ".join(r.get("p1843", [])),
            }
        )
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1:,}/{len(gaps):,} tried, {filled:,} filled")
    wd.close()

    prov_path = Path(args.provenance_out)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "wikidata_qid",
        "wikidata_common_name",
        "source_field",
        "all_p1843",
    ]
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# source: Wikidata (P1843 taxon common name, then item label/alias); "
            "matched by P225 scientific name\n"
        )
        fh.write(f"# langs: {args.langs}   retrieved: {retrieved}\n")
        fh.write("\t".join(header) + "\n")
        for r in prov:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    new_total = already + filled
    print("\n=== WIKIDATA GAP-FILL ===")
    print(f"  filled this pass:   {filled:,}/{len(gaps):,} gaps")
    if field_tally:
        for f in ("P1843", "label", "alias"):
            if field_tally.get(f):
                print(f"      via {f:6s}: {field_tally[f]:,}")
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
