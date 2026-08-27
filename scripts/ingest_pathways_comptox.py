#!/usr/bin/env python
"""
ingest_pathways_comptox.py — add Pathway individuals + gene→pathway edges to POPPy.

The ComptoxAI populated ontology (``comptox_populated.rdf``, the 598 MB Box download) is the
SAME source POPPy already uses for its genes (``GeneticEntity`` individuals, imported with the
``gene_`` prefix stripped). That file also contains:

    * ~4,570 Pathway individuals (KEGG + Reactome), each with commonName / pathwayId /
      sourceDatabase,
    * ~179,000 ``geneInPathway`` edges linking genes (``#gene_<symbol>``) to pathways
      (``#pathway_<id>``).

Because POPPy's genes are the very same ComptoxAI genes (keyed by lowercase gene symbol,
``gene_`` stripped), these pathway edges attach to your existing targets with ZERO identifier
harmonization. This script extracts the pathway layer and emits an additive Turtle module you
merge into the enriched ontology.

NOTE: it does NOT contain diseases — that ComptoxAI export has no disease individuals. Use the
companion ``ingest_diseases_doid.py`` (DISEASES + Disease Ontology) for the disease layer.

METHOD (streaming, no rdflib load of the 598 MB file)
  1. Stream ``comptox_populated.rdf`` line by line; capture <Pathway> blocks and, inside each
     <Gene> block, its <geneInPathway> targets.
  2. Emit, in the ComptoxAI base namespace with the SAME ``gene_``/``pathway_`` prefixes
     stripped that POPPy uses for genes:
        <base#PATHWAYID> a <base#Pathway> ; rdfs:label "..." ; <base#pathwayId> "..." ;
                          <base#sourceDatabase> "..." .
        <base#GENESYM> <base#geneInPathway> <base#PATHWAYID> .
  Only genes that actually appear as geneInPathway subjects are referenced, so every edge lands
  on a gene that exists in your ontology.

USAGE
  python3 scripts/ingest_pathways_comptox.py \
      --comptox /path/to/comptox_populated.rdf \
      --out data/enrichment/poppy_pathways.ttl
  # then merge poppy_pathways.ttl into the enriched ontology (rdflib parse + '+=' or riot merge)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# ComptoxAI base namespace — the same one POPPy's imported genes live in (gene_ stripped).
DEFAULT_BASE = "http://jdr.bio/ontologies/comptox.owl#"

RE_PATHWAY_OPEN = re.compile(r'<Pathway rdf:about="#pathway_([^"]+)"')
RE_PATHWAY_CLOSE = re.compile(r"</Pathway>")
RE_GENE_OPEN = re.compile(r'<Gene rdf:about="#gene_([^"]+)"')
RE_GENE_CLOSE = re.compile(r"</Gene>")
RE_GENE_IN_PATHWAY = re.compile(r'<geneInPathway rdf:resource="#pathway_([^"]+)"')
RE_COMMON_NAME = re.compile(r"<commonName[^>]*>(.*?)</commonName>")
RE_PATHWAY_ID = re.compile(r"<pathwayId[^>]*>(.*?)</pathwayId>")
RE_SOURCE_DB = re.compile(r"<sourceDatabase[^>]*>(.*?)</sourceDatabase>")


def ttl_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--comptox", required=True, help="Path to comptox_populated.rdf (598 MB).")
    ap.add_argument("--out", default="data/enrichment/poppy_pathways.ttl")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Gene/pathway URI base (gene_ stripped).")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N pathways (smoke test).")
    args = ap.parse_args()

    pathways: dict[str, dict] = {}  # pathway_id -> {name, pathwayId, sources:set}
    edges: set[tuple[str, str]] = set()  # (gene_symbol, pathway_id)

    cur_pathway: str | None = None
    cur_fields: dict = {}
    cur_gene: str | None = None

    with open(args.comptox, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            # fast path: most lines are chemicals — skip regex work unless relevant
            if cur_pathway is None and cur_gene is None:
                if "athway" not in line and "<Gene " not in line:
                    continue
            # --- Pathway blocks ---
            if cur_pathway is None:
                m = RE_PATHWAY_OPEN.search(line)
                if m:
                    cur_pathway = m.group(1)
                    cur_fields = {"name": "", "pathwayId": cur_pathway, "sources": set()}
                    # a one-line block can also close on the same line
            if cur_pathway is not None:
                cn = RE_COMMON_NAME.search(line)
                if cn:
                    cur_fields["name"] = cn.group(1)
                pid = RE_PATHWAY_ID.search(line)
                if pid:
                    cur_fields["pathwayId"] = pid.group(1)
                sd = RE_SOURCE_DB.search(line)
                if sd:
                    cur_fields["sources"].add(sd.group(1))
                if RE_PATHWAY_CLOSE.search(line):
                    pathways[cur_pathway] = cur_fields
                    cur_pathway = None
                    if args.limit and len(pathways) >= args.limit:
                        break
                continue

            # --- Gene blocks (collect geneInPathway edges) ---
            if cur_gene is None:
                mg = RE_GENE_OPEN.search(line)
                if mg:
                    cur_gene = mg.group(1)
            if cur_gene is not None:
                for gp in RE_GENE_IN_PATHWAY.finditer(line):
                    edges.add((cur_gene, gp.group(1)))
                if RE_GENE_CLOSE.search(line):
                    cur_gene = None

    # keep only edges whose pathway we actually captured
    edges = {(g, p) for (g, p) in edges if p in pathways}

    base = args.base
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        fh.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
        fh.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
        fh.write(f"# ComptoxAI pathway layer for POPPy — base {base}\n")
        fh.write(f"# {len(pathways):,} pathways, {len(edges):,} gene->pathway edges\n\n")
        for pid, f in pathways.items():
            uri = f"<{base}{pid}>"
            fh.write(f"{uri} rdf:type owl:NamedIndividual , <{base}Pathway> ;\n")
            if f["name"]:
                fh.write(f'    rdfs:label "{ttl_escape(f["name"])}" ;\n')
            fh.write(f'    <{base}pathwayId> "{ttl_escape(f["pathwayId"])}" ;\n')
            srcs = sorted(f["sources"]) or [""]
            src_str = " , ".join(f'"{ttl_escape(s)}"' for s in srcs if s)
            if src_str:
                fh.write(f"    <{base}sourceDatabase> {src_str} ;\n")
            fh.write('    rdfs:comment "source: ComptoxAI" .\n')
        for g, p in sorted(edges):
            fh.write(f"<{base}{g}> <{base}geneInPathway> <{base}{p}> .\n")

    print("=== ComptoxAI PATHWAY INGEST ===")
    print(f"  pathways:            {len(pathways):,}")
    print(f"  gene->pathway edges: {len(edges):,}")
    print(f"  distinct genes:      {len({g for g, _ in edges}):,}")
    print(f"  wrote:               {out}")
    print("  merge into the enriched ontology (rdflib parse + '+=' or riot --merge).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
