"""Offline NCBI-taxonomy classification from a local taxdump.

Replaces per-name NCBI Entrez / POWO web calls (≈2 HTTP round-trips + a throttle sleep per
organism → ~12 h for the full COCONUT set) with in-memory lookups over `names.dmp` / `nodes.dmp`
(the whole build's organism validation then runs in minutes). Stdlib-only — safe to import
without biopython/rdkit.

Usage:
    tax = LocalTaxonomy.ensure("data/raw/taxdump")     # download+extract taxdmp.zip if needed
    tax.is_plant_name("Panax ginseng")                 # True
    tax.is_plant_taxid(3645)                            # True (uses an ID you already have)
    tax.classify_name("Streptomyces")                  # ("nonplant", 1883)

"plant" == lies under Viridiplantae (NCBI taxid 33090). Name matching tries scientific names,
synonyms, and common names, then falls back to genus+species and genus — so vernacular names
(liquorice, kumquat) that a scientific-name-only pass misses are still rescued.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen

TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdmp.zip"
VIRIDIPLANTAE = 33090

# NCBI name classes worth indexing for matching (skip authorities, type material, etc.)
_NAME_CLASSES = {
    "scientific name",
    "synonym",
    "equivalent name",
    "genbank synonym",
    "common name",
    "genbank common name",
    "includes",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class LocalTaxonomy:
    def __init__(self, names_dmp: Path, nodes_dmp: Path):
        self.parent: dict[int, int] = {}
        self.rank: dict[int, str] = {}
        self.name2taxid: dict[str, int] = {}
        self._plant_cache: dict[int, bool] = {}
        self._name_cache: dict[str, Tuple[str, Optional[int]]] = {}
        self._load_nodes(Path(nodes_dmp))
        self._load_names(Path(names_dmp))

    # ---- loading ----
    def _load_nodes(self, path: Path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split("\t|\t")
                tid = int(parts[0])
                self.parent[tid] = int(parts[1])
                self.rank[tid] = parts[2]

    def _load_names(self, path: Path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split("\t|\t")
                if len(parts) < 4:
                    continue
                nclass = parts[3].rstrip("\t|").rstrip("\t|\n").strip()
                if nclass not in _NAME_CLASSES:
                    continue
                key = _norm(parts[1])
                if not key:
                    continue
                # scientific name wins ties; never let a synonym clobber a scientific name
                if key in self.name2taxid and nclass != "scientific name":
                    continue
                self.name2taxid[key] = int(parts[0])

    # ---- queries ----
    def is_plant_taxid(self, taxid: Optional[int]) -> bool:
        if not taxid:
            return False
        if taxid in self._plant_cache:
            return self._plant_cache[taxid]
        seen, cur, res = set(), taxid, False
        while cur and cur not in seen:
            if cur == VIRIDIPLANTAE:
                res = True
                break
            seen.add(cur)
            nxt = self.parent.get(cur)
            if nxt is None or nxt == cur:
                break
            cur = nxt
        self._plant_cache[taxid] = res
        return res

    def _variants(self, name: str):
        n = _norm(name)
        out = [n]
        toks = n.split()
        if len(toks) >= 2:
            out.append(f"{toks[0]} {toks[1]}")  # genus + species
        if toks:
            out.append(toks[0])  # genus only
        seen, res = set(), []
        for v in out:
            if v and v not in seen:
                seen.add(v)
                res.append(v)
        return res

    def resolve_name(self, name: str) -> Optional[int]:
        for v in self._variants(name):
            tid = self.name2taxid.get(v)
            if tid:
                return tid
        return None

    def is_plant_name(self, name: str) -> bool:
        return self.classify_name(name)[0] == "plant"

    def classify_name(self, name: str) -> Tuple[str, Optional[int]]:
        """Return ('plant'|'nonplant'|'unmatched', taxid_or_None)."""
        key = _norm(name)
        if key in self._name_cache:
            return self._name_cache[key]
        tid = self.resolve_name(name)
        if tid is None:
            out = ("unmatched", None)
        else:
            out = ("plant" if self.is_plant_taxid(tid) else "nonplant", tid)
        self._name_cache[key] = out
        return out

    # ---- construction ----
    @classmethod
    def from_dir(cls, taxdump_dir) -> "LocalTaxonomy":
        d = Path(taxdump_dir)
        return cls(d / "names.dmp", d / "nodes.dmp")

    @classmethod
    def ensure(cls, taxdump_dir, url: str = TAXDUMP_URL) -> "LocalTaxonomy":
        """Load from taxdump_dir; download+extract names.dmp/nodes.dmp first if missing."""
        d = Path(taxdump_dir)
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "names.dmp").exists() or not (d / "nodes.dmp").exists():
            zpath = d / "taxdmp.zip"
            if not zpath.exists():
                with urlopen(url) as r, open(zpath, "wb") as f:  # noqa: S310
                    f.write(r.read())
            with zipfile.ZipFile(zpath) as z:
                for member in ("names.dmp", "nodes.dmp"):
                    z.extract(member, d)
        return cls.from_dir(d)
