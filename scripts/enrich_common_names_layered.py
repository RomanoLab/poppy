#!/usr/bin/env python
"""
enrich_common_names_layered.py — attach common names to POPPy plant taxa from LAYERED sources.

Coverage beats NCBI alone by combining sources in priority order and keeping per-name
provenance. Default priority: GBIF (broad, multilingual, open API) -> NCBI (taxdump fallback).
Dr. Duke's ethnobotanical common names can be layered in FIRST when you supply its CSV.

For each plant scientific name it:
  1. (GBIF) matches the name to a GBIF usageKey (this also yields the ACCEPTED name), then
     pulls that taxon's vernacular names, filtered to your target language(s);
  2. falls back to NCBI taxdump common names for taxa GBIF didn't cover;
  3. (optional) prefers Dr. Duke's common name when present;
  4. writes a ``common`` field into website/data/plants_index.json (drives the Explore page), and
  5. emits data/enrichment/common_names_layered.tsv — one row per plant with the CHOSEN source,
     GBIF accepted name, taxid/usageKey, language, and every common name found across sources.

SELF-CONTAINED: stdlib only. GBIF uses the public REST API with an on-disk cache so the run is
RESUMABLE (interrupt/rerun is cheap; ~45k names is a one-time cost). NCBI uses the taxdump the
build already downloads. Nothing here needs the poppy package, so it runs on any repo version.

USAGE (run from repo root; GBIF/NCBI need network on first run)
  # GBIF + NCBI, English display names, dry run (coverage + TSV, no JSON edit):
  python3 scripts/enrich_common_names_layered.py --dry-run
  # For real:
  python3 scripts/enrich_common_names_layered.py
  # Add Dr. Duke's on top (download Cleaned_COMMON_NAMES.csv from Zenodo first):
  python3 scripts/enrich_common_names_layered.py --duke-csv data/raw/Cleaned_COMMON_NAMES.csv \
      --duke-name-col "TAXON" --duke-common-col "CNAME"
  # NCBI only (no network to GBIF), or GBIF only:
  python3 scripts/enrich_common_names_layered.py --sources ncbi
  python3 scripts/enrich_common_names_layered.py --sources gbif --langs eng,spa

NOTE: the live GBIF path cannot be exercised in an offline sandbox; verify coverage on your run.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdmp.zip"
GBIF_BASE = "https://api.gbif.org/v1"
VIRIDIPLANTAE = 33090
# GBIF match ranks we trust for a species-level vernacular. Anything coarser (GENUS, FAMILY,
# KINGDOM ...) means the matcher fell back up the tree — reject it, or "Unknown sp." gets
# labelled "Plants" from the kingdom Plantae.
GBIF_SPECIES_RANKS = {
    "SPECIES",
    "SUBSPECIES",
    "VARIETY",
    "FORM",
    "INFRASPECIFIC_NAME",
    "INFRASUBSPECIFIC_NAME",
}
GBIF_OK_MATCHTYPES = {"EXACT", "FUZZY"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# ===========================================================================
# Source result contract
# ===========================================================================
class Hit:
    """One source's answer for one input name."""

    def __init__(self, source, display=None, names=None, extra=None, match_level=None):
        self.source = source  # "gbif" | "ncbi" | "duke"
        self.display = display  # chosen display common name (str|None)
        self.names = names or []  # list[(name, language, source)]
        self.extra = extra or {}  # source-specific fields for provenance
        self.match_level = match_level  # full|genus_species|genus|match|None


# ===========================================================================
# NCBI taxdump source
# ===========================================================================
_NCBI_NAME_CLASSES = {
    "scientific name",
    "synonym",
    "equivalent name",
    "genbank synonym",
    "common name",
    "genbank common name",
    "includes",
}
_NCBI_VERNACULAR = ("genbank common name", "common name")


class NCBISource:
    def __init__(self, taxdump_dir: Path):
        d = Path(taxdump_dir)
        d.mkdir(parents=True, exist_ok=True)
        names, nodes = d / "names.dmp", d / "nodes.dmp"
        if not names.exists() or not nodes.exists():
            zpath = d / "taxdmp.zip"
            if not zpath.exists():
                print(f"[ncbi] downloading taxdump -> {zpath} (~75 MB)...")
                with urlopen(TAXDUMP_URL) as r, open(zpath, "wb") as f:  # noqa: S310
                    f.write(r.read())
            with zipfile.ZipFile(zpath) as z:
                for m in ("names.dmp", "nodes.dmp"):
                    z.extract(m, d)
        self.name2taxid: dict[str, int] = {}
        self.rank: dict[int, str] = {}
        self.common: dict[int, list[str]] = {}
        with open(nodes, encoding="utf-8") as fh:
            for line in fh:
                p = line.split("\t|\t")
                if len(p) >= 3:
                    self.rank[int(p[0])] = p[2]
        with open(names, encoding="utf-8") as fh:
            for line in fh:
                p = line.split("\t|\t")
                if len(p) < 4:
                    continue
                nclass = p[3].rstrip("\t|").rstrip("\t|\n").strip()
                if nclass not in _NCBI_NAME_CLASSES:
                    continue
                tid, name, key = int(p[0]), p[1].strip(), _norm(p[1])
                if key and not (key in self.name2taxid and nclass != "scientific name"):
                    self.name2taxid[key] = tid
                if nclass in _NCBI_VERNACULAR and name:
                    self.common.setdefault(tid, [])
                    if name not in self.common[tid]:
                        self.common[tid].append(name)

    def _resolve(self, name):
        n = _norm(name)
        toks = n.split()
        cands = [(n, "full")]
        if len(toks) >= 2:
            cands.append((f"{toks[0]} {toks[1]}", "genus_species"))
        if toks:
            cands.append((toks[0], "genus"))
        seen = set()
        for key, level in cands:
            if key and key not in seen:
                seen.add(key)
                if key in self.name2taxid:
                    return self.name2taxid[key], level
        return None, None

    def lookup(self, name, allow_genus=False) -> Hit:
        taxid, level = self._resolve(name)
        if taxid is None:
            return Hit("ncbi", match_level="unmatched")
        commons = self.common.get(taxid, [])
        names = [(c, "", "ncbi") for c in commons]
        display = None
        if commons and (level in ("full", "genus_species") or allow_genus):
            display = commons[0]
        return Hit(
            "ncbi",
            display=display,
            names=names,
            extra={"ncbi_taxid": taxid, "rank": self.rank.get(taxid, "")},
            match_level=level,
        )


# ===========================================================================
# GBIF source (REST API + on-disk cache)
# ===========================================================================
class GBIFSource:
    def __init__(self, cache_path: Path, langs, sleep=0.05, timeout=30):
        self.cache_path = Path(cache_path)
        self.langs = [lang.strip().lower() for lang in langs]
        self.sleep = sleep
        self.timeout = timeout
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text())
            except Exception:
                self.cache = {}
        self._dirty = 0

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "poppy-enrich/1.0"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                    return json.loads(r.read().decode())
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.5 * (2**attempt))
        return None

    def _fetch(self, name):
        """Return raw {usageKey, acceptedName, matchType, vernaculars:[{name,language,source,preferred}]}."""
        m = self._get(
            f"{GBIF_BASE}/species/match?"
            + urllib.parse.urlencode({"name": name, "kingdom": "Plantae", "strict": "false"})
        )
        if not m or m.get("matchType") in (None, "NONE") or not m.get("usageKey"):
            return {
                "usageKey": None,
                "matchType": (m or {}).get("matchType", "NONE"),
                "rank": (m or {}).get("rank", ""),
                "vernaculars": [],
            }
        key = m["usageKey"]
        verns, offset = [], 0
        while True:
            page = self._get(
                f"{GBIF_BASE}/species/{key}/vernacularNames?"
                + urllib.parse.urlencode({"limit": 100, "offset": offset})
            )
            for v in (page or {}).get("results", []):
                vn = (v.get("vernacularName") or "").strip()
                if vn:
                    verns.append(
                        {
                            "name": vn,
                            "language": (v.get("language") or "").lower(),
                            "source": v.get("source") or "",
                            "preferred": bool(v.get("preferred")),
                        }
                    )
            if not page or page.get("endOfRecords", True):
                break
            offset += 100
        return {
            "usageKey": key,
            "acceptedName": m.get("scientificName") or m.get("canonicalName"),
            "matchType": m.get("matchType"),
            "rank": m.get("rank"),
            "status": m.get("status"),
            "confidence": m.get("confidence"),
            "vernaculars": verns,
        }

    def _flush(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache))
        self._dirty = 0

    def lookup(self, name, allow_coarse=False) -> Hit:
        key = _norm(name)
        if key not in self.cache:
            self.cache[key] = self._fetch(name)
            self._dirty += 1
            time.sleep(self.sleep)
            if self._dirty >= 200:
                self._flush()
        rec = self.cache[key]
        rank = (rec.get("rank") or "").upper()
        mtype = (rec.get("matchType") or "").upper()
        # Reject coarse matches: a species input that only resolves to genus/family/kingdom
        # returns matchType HIGHERRANK (or a non-species rank). Those vernaculars are noise.
        species_ok = rank in GBIF_SPECIES_RANKS and mtype in GBIF_OK_MATCHTYPES
        extra = {
            "gbif_usageKey": rec.get("usageKey"),
            "gbif_accepted_name": rec.get("acceptedName", ""),
            "gbif_rank": rank,
            "gbif_matchType": mtype,
        }
        if not (species_ok or allow_coarse):
            return Hit(
                "gbif",
                display=None,
                names=[],
                extra=extra,
                match_level="rejected_coarse" if rec.get("usageKey") else "unmatched",
            )
        verns = rec.get("vernaculars", [])
        in_lang = [v for v in verns if v["language"] in self.langs] if self.langs else verns
        names = [(v["name"], v["language"], "gbif") for v in in_lang]
        display = None
        pref = [v for v in in_lang if v.get("preferred")]
        if pref:
            display = pref[0]["name"]
        elif in_lang:
            display = in_lang[0]["name"]
        return Hit(
            "gbif", display=display, names=names, extra=extra, match_level=mtype.lower() or "match"
        )

    def close(self):
        if self._dirty:
            self._flush()


# ===========================================================================
# Dr. Duke's source (local CSV; column-configurable)
# ===========================================================================
class DukeSource:
    def __init__(self, csv_path: Path, name_col, common_col):
        self.map: dict[str, list[str]] = {}
        with open(csv_path, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            if name_col not in cols or common_col not in cols:
                raise SystemExit(
                    f"[duke] columns not found. Have {cols}; "
                    f"need --duke-name-col and --duke-common-col from that list."
                )
            for row in reader:
                sci, cn = _norm(row.get(name_col, "")), (row.get(common_col, "") or "").strip()
                if sci and cn:
                    self.map.setdefault(sci, [])
                    if cn not in self.map[sci]:
                        self.map[sci].append(cn)

    def lookup(self, name) -> Hit:
        n = _norm(name)
        toks = n.split()
        for key in (n, " ".join(toks[:2]) if len(toks) >= 2 else None):
            if key and key in self.map:
                commons = self.map[key]
                return Hit(
                    "duke",
                    display=commons[0],
                    names=[(c, "", "duke") for c in commons],
                    match_level="full",
                )
        return Hit("duke", match_level="unmatched")


# ===========================================================================
# Orchestration
# ===========================================================================
def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument(
        "--sources",
        default="gbif,ncbi",
        help="Comma list in priority order: gbif,ncbi[,duke]. First with a display wins.",
    )
    ap.add_argument(
        "--langs",
        default="eng",
        help="GBIF language filter, comma list of ISO-639-3 (e.g. eng,spa).",
    )
    ap.add_argument("--taxdump-dir", default=str(REPO / "data" / "raw" / "taxdump"))
    ap.add_argument("--gbif-cache", default=str(REPO / "data" / "enrichment" / "gbif_cache.json"))
    ap.add_argument("--duke-csv", default=None)
    ap.add_argument("--duke-name-col", default="TAXON")
    ap.add_argument("--duke-common-col", default="CNAME")
    ap.add_argument(
        "--provenance-out", default=str(REPO / "data" / "enrichment" / "common_names_layered.tsv")
    )
    ap.add_argument("--allow-genus-fallback", action="store_true")
    ap.add_argument(
        "--limit", type=int, default=0, help="Process only first N records (smoke test)."
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    priority = [s.strip() for s in args.sources.split(",") if s.strip()]
    if "duke" in priority and not args.duke_csv:
        raise SystemExit("[duke] requested in --sources but no --duke-csv given.")

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    if args.limit:
        records = records[: args.limit]
    print(f"Loaded {len(records):,} plant records; source priority: {priority}")

    src = {}
    if "duke" in priority:
        src["duke"] = DukeSource(Path(args.duke_csv), args.duke_name_col, args.duke_common_col)
        print(f"[duke] loaded {len(src['duke'].map):,} taxa with common names")
    if "ncbi" in priority:
        src["ncbi"] = NCBISource(Path(args.taxdump_dir))
        print(f"[ncbi] taxdump ready: {len(src['ncbi'].name2taxid):,} names")
    if "gbif" in priority:
        src["gbif"] = GBIFSource(Path(args.gbif_cache), args.langs.split(","))
        print(f"[gbif] cache: {len(src['gbif'].cache):,} names memoized; langs={args.langs}")

    retrieved = _dt.date.today().isoformat()
    prov, assigned = [], 0
    per_source_assigned = {s: 0 for s in priority}

    for i, rec in enumerate(records):
        sci = rec.get("name", "")
        hits = {}
        for s in priority:
            if s == "ncbi":
                h = src[s].lookup(sci, allow_genus=args.allow_genus_fallback)
            elif s == "gbif":
                h = src[s].lookup(sci, allow_coarse=args.allow_genus_fallback)
            else:
                h = src[s].lookup(sci)
            hits[s] = h
        # choose display by priority
        chosen_source, display = "", None
        for s in priority:
            if hits[s].display:
                chosen_source, display = s, hits[s].display
                break
        if display:
            rec["common"] = display
            assigned += 1
            per_source_assigned[chosen_source] += 1
        else:
            rec.pop("common", None)
        # merge all names for provenance
        all_names = []
        extra = {}
        for s in priority:
            for nm, lang, so in hits[s].names:
                all_names.append(f"{so}:{lang or '-'}:{nm}")
            extra.update(hits[s].extra)
        prov.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "chosen_source": chosen_source or "none",
                "display_common_name": display or "",
                "gbif_accepted_name": extra.get("gbif_accepted_name", ""),
                "gbif_usageKey": extra.get("gbif_usageKey", "") or "",
                "gbif_rank": extra.get("gbif_rank", ""),
                "gbif_matchType": extra.get("gbif_matchType", ""),
                "ncbi_taxid": extra.get("ncbi_taxid", "") or "",
                "all_common_names": "; ".join(all_names),
            }
        )
        if (i + 1) % 2000 == 0:
            print(f"  ...{i+1:,}/{len(records):,} processed, {assigned:,} assigned")

    if "gbif" in src:
        src["gbif"].close()

    prov_path = Path(args.provenance_out)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "chosen_source",
        "display_common_name",
        "gbif_accepted_name",
        "gbif_usageKey",
        "gbif_rank",
        "gbif_matchType",
        "ncbi_taxid",
        "all_common_names",
    ]
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(f"# sources (priority): {','.join(priority)}\n")
        fh.write(f"# gbif: {GBIF_BASE} (species/match + vernacularNames); langs={args.langs}\n")
        fh.write(f"# ncbi: NCBI Taxonomy taxdump ({TAXDUMP_URL})\n")
        if "duke" in priority:
            fh.write(f"# duke: {args.duke_csv}\n")
        fh.write(f"# retrieved: {retrieved}\n")
        fh.write("\t".join(header) + "\n")
        for r in prov:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    print("\n=== COVERAGE ===")
    print(f"  common name assigned:  {assigned:,}/{len(records):,} ({100*assigned/total:.1f}%)")
    for s in priority:
        print(f"    via {s:5s}: {per_source_assigned[s]:,}")
    print(f"  provenance table:      {prov_path}")

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
