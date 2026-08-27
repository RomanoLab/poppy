#!/usr/bin/env python
"""
ingest_compound_targets_cmaup.py — granular compound -> gene edges, joined by InChIKey.

More mechanistic than the plant->gene layer: this says WHICH compound targets a gene. It
joins CMAUP's ingredient->target data to your ontology's compounds on InChIKey.

  * your compounds carry an InChIKey in ``ns1:hasCommonName`` (e.g. OAUAVKGFNHNNGR-HXUWFJFHSA-N),
    URI ``phytotherapies#Chemical_<...>``  -> extracted by streaming the ontology.
  * CMAUP Ingredients_All: Ingredient_ID (np_id) -> InChIKey  (column ``InChIKey``).
  * CMAUP Ingredient_Target x Targets: Ingredient_ID -> Gene_Symbol (gated to ComptoxAI genes).
  join on InChIKey => <phytotherapies#Chemical_X> <phytotherapies#compoundTargetsGene> <jdr.bio#gene> .

USAGE (no network; all inputs local)
  python3 scripts/ingest_compound_targets_cmaup.py \
      --ontology ~/Downloads/poppyontology.rdf \
      --cmaup-dir ~/Downloads \
      --comptox ~/Downloads/comptox_populated.rdf \
      --out data/enrichment/poppy_compound_targets.ttl
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CMPTX = "http://jdr.bio/ontologies/comptox.owl#"
PHYTO = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"

RE_GENE_URI = re.compile(r'<Gene rdf:about="#gene_([^"]+)"')
RE_CHEM_URI = re.compile(r'rdf:about="[^"]*#(Chemical_[^"]+)"')
RE_INCHIKEY = re.compile(r">([A-Z]{14}-[A-Z]{7,12}-[A-Z]+)<")


def load_comptox_genes(path: Path) -> set[str]:
    genes = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "<Gene " in line:
                m = RE_GENE_URI.search(line)
                if m:
                    genes.add(m.group(1).lower())
    return genes


def load_compound_inchikeys(path: Path) -> dict[str, list[str]]:
    """Stream the ontology -> {InChIKey: [compound_local_uri, ...]}."""
    ik2chem: dict[str, list[str]] = {}
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "Chemical_" in line:
                m = RE_CHEM_URI.search(line)
                if m:
                    cur = m.group(1)
            if cur and "hasCommonName>" in line:
                m = RE_INCHIKEY.search(line)
                if m:
                    ik2chem.setdefault(m.group(1), []).append(cur)
                    cur = None
    return ik2chem


def col_index(header: str, name: str) -> int:
    return header.rstrip("\n").split("\t").index(name)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ontology", required=True, help="poppyontology.rdf (compound InChIKeys).")
    ap.add_argument("--cmaup-dir", required=True)
    ap.add_argument("--comptox", required=True, help="comptox_populated.rdf (gene gate).")
    ap.add_argument("--out", default="data/enrichment/poppy_compound_targets.ttl")
    args = ap.parse_args()
    d = Path(args.cmaup_dir)

    print("[1/5] ComptoxAI gene set")
    genes = load_comptox_genes(Path(args.comptox))
    print(f"      {len(genes):,} genes")

    print("[2/5] compound InChIKeys from ontology")
    ik2chem = load_compound_inchikeys(Path(args.ontology))
    print(f"      {len(ik2chem):,} distinct InChIKeys on compounds")

    print("[3/5] Targets: Target_ID -> gene symbol")
    tgt2sym: dict[str, str] = {}
    with open(d / "CMAUPv2.0_download_Targets.txt", encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        ti, gi = col_index(hdr, "Target_ID"), col_index(hdr, "Gene_Symbol")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(ti, gi):
                sym = c[gi].strip().lower()
                if sym in genes:
                    tgt2sym[c[ti].strip()] = sym

    print("[4/5] Ingredient -> InChIKey and Ingredient -> gene symbols")
    ing2ik: dict[str, str] = {}
    fn = "CMAUPv2.0_download_Ingredients_All.txt"
    with open(d / fn, encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        ii, ki = col_index(hdr, "np_id"), col_index(hdr, "InChIKey")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(ii, ki) and c[ki].strip():
                ing2ik[c[ii].strip()] = c[ki].strip()
    ing2syms: dict[str, set[str]] = {}
    fn = "CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt"
    with open(d / fn, encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        ii, ti = col_index(hdr, "Ingredient_ID"), col_index(hdr, "Target_ID")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(ii, ti):
                sym = tgt2sym.get(c[ti].strip())
                if sym:
                    ing2syms.setdefault(c[ii].strip(), set()).add(sym)

    print("[5/5] join on InChIKey and write TTL")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    edges = set()
    for ing, syms in ing2syms.items():
        ik = ing2ik.get(ing)
        if not ik:
            continue
        chems = ik2chem.get(ik)
        if not chems:
            continue
        for chem in chems:
            for sym in syms:
                edges.add((chem, sym))
    with open(out, "w", encoding="utf-8") as w:
        w.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        w.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
        w.write(f"<{PHYTO}compoundTargetsGene> rdf:type owl:ObjectProperty .\n\n")
        for chem, sym in sorted(edges):
            w.write(f"<{PHYTO}{chem}> <{PHYTO}compoundTargetsGene> <{CMPTX}{sym}> .\n")

    print("\n=== CMAUP COMPOUND->GENE TARGETS ===")
    print(f"  compound->gene edges: {len(edges):,}")
    print(f"  distinct compounds:   {len({c for c, _ in edges}):,}")
    print(f"  distinct genes:       {len({s for _, s in edges}):,}")
    print(f"  wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
