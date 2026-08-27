#!/usr/bin/env python
"""
ingest_targets_cmaup.py — build POPPy plant -> gene (targetsGene) edges from CMAUP.

This is the connective tissue that ties your plants/compounds to the ComptoxAI gene layer so
the chain plant -> gene -> pathway/disease resolves end to end.

JOIN (all CMAUP v2.0 files, tab-separated)
  Plant_Ingredient_Associations   Plant_ID  -> Ingredient_ID           (no header)
  Ingredient_Target_Associations  Ingredient_ID -> Target_ID           (header)
  Targets                         Target_ID -> Gene_Symbol             (header)
  Plants                          Plant_ID  -> Plant_Name (sci. name)  (header)
=> Plant (scientific name) -> Gene_Symbol.

Then anchored to your graph:
  * plant  : scientific name -> plants_index id -> <phytotherapies#<id>>  (POPPy plant URI)
  * gene   : Gene_Symbol -> <jdr.bio#<symbol lowercase>>  (ComptoxAI gene URI), GATED to genes
             that actually exist in comptox_populated.rdf so every edge lands on a real node.

Emits: <phytotherapies#PLANT> <phytotherapies#targetsGene> <jdr.bio#gene> .
(``targetsGene`` is POPPy's existing Plant->Gene schema property.)

USAGE (no network; all inputs local)
  python3 scripts/ingest_targets_cmaup.py \
      --cmaup-dir ~/Downloads \
      --comptox ~/Downloads/comptox_populated.rdf \
      --plants-index website/data/plants_index.json \
      --out data/enrichment/poppy_targets.ttl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CMPTX = "http://jdr.bio/ontologies/comptox.owl#"
PHYTO = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
RE_GENE_URI = re.compile(r'<Gene rdf:about="#gene_([^"]+)"')


def norm_name(s: str) -> str:
    toks = re.sub(r"[^a-z ]", " ", (s or "").lower()).split()
    return " ".join(toks[:2]) if len(toks) >= 2 else " ".join(toks)


def load_comptox_genes(path: Path) -> set[str]:
    genes = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "<Gene " not in line:
                continue
            m = RE_GENE_URI.search(line)
            if m:
                genes.add(m.group(1).lower())
    return genes


def col_index(header: str, name: str) -> int:
    cols = header.rstrip("\n").split("\t")
    return cols.index(name)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--cmaup-dir", required=True, help="Dir with CMAUPv2.0_download_*.txt files.")
    ap.add_argument("--comptox", required=True, help="comptox_populated.rdf (gene gate).")
    ap.add_argument("--plants-index", default="website/data/plants_index.json")
    ap.add_argument("--out", default="data/enrichment/poppy_targets.ttl")
    args = ap.parse_args()

    d = Path(args.cmaup_dir)

    def f(name):
        return d / name

    print("[1/6] ComptoxAI gene set")
    genes = load_comptox_genes(Path(args.comptox))
    print(f"      {len(genes):,} gene symbols")

    print("[2/6] Targets: Target_ID -> gene symbol")
    tgt2sym: dict[str, str] = {}
    p = f("CMAUPv2.0_download_Targets.txt")
    with open(p, encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        ti, gi = col_index(hdr, "Target_ID"), col_index(hdr, "Gene_Symbol")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(ti, gi):
                sym = c[gi].strip().lower()
                if sym and sym in genes:
                    tgt2sym[c[ti].strip()] = sym
    print(f"      {len(tgt2sym):,} targets map to a POPPy gene")

    print("[3/6] Ingredient_Target: Ingredient_ID -> gene symbols")
    ing2syms: dict[str, set[str]] = {}
    p = f("CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt")
    with open(p, encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        ii, ti = col_index(hdr, "Ingredient_ID"), col_index(hdr, "Target_ID")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(ii, ti):
                sym = tgt2sym.get(c[ti].strip())
                if sym:
                    ing2syms.setdefault(c[ii].strip(), set()).add(sym)
    print(f"      {len(ing2syms):,} ingredients hit >=1 gene")

    print("[4/6] Plant_Ingredient: Plant_ID -> gene symbols")
    plant2syms: dict[str, set[str]] = {}
    p = f("CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt")
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 2:
                syms = ing2syms.get(c[1].strip())
                if syms:
                    plant2syms.setdefault(c[0].strip(), set()).update(syms)
    print(f"      {len(plant2syms):,} plants hit >=1 gene")

    print("[5/6] map CMAUP Plant_ID -> POPPy plant id (by scientific name)")
    name2id: dict[str, str] = {}
    for rec in json.loads(Path(args.plants_index).read_text()):
        nm = norm_name(rec.get("name", ""))
        if nm:
            name2id.setdefault(nm, rec.get("id", ""))
    pid2poppy: dict[str, str] = {}
    p = f("CMAUPv2.0_download_Plants.txt")
    with open(p, encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline()
        pi, ni = col_index(hdr, "Plant_ID"), col_index(hdr, "Plant_Name")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(pi, ni):
                poppy = name2id.get(norm_name(c[ni]))
                if poppy:
                    pid2poppy[c[pi].strip()] = poppy
    print(f"      {len(pid2poppy):,} CMAUP plants match a POPPy plant")

    print("[6/6] write TTL")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_edges = 0
    n_plants = 0
    with open(out, "w", encoding="utf-8") as w:
        w.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        w.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
        w.write(f"<{PHYTO}targetsGene> rdf:type owl:ObjectProperty .\n\n")
        for pid, syms in plant2syms.items():
            poppy = pid2poppy.get(pid)
            if not poppy:
                continue
            n_plants += 1
            for sym in sorted(syms):
                w.write(f"<{PHYTO}{poppy}> <{PHYTO}targetsGene> <{CMPTX}{sym}> .\n")
                n_edges += 1

    print("\n=== CMAUP PLANT->GENE TARGETS ===")
    print(f"  plant->gene edges:  {n_edges:,}")
    print(f"  POPPy plants linked:{n_plants:,}")
    print(f"  wrote:              {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
