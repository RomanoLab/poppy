#!/usr/bin/env python
"""
ingest_genes_comptox.py — emit the ComptoxAI gene layer as a POPPy module (poppy_genes.ttl).

This regenerates the same ``GeneticEntity`` gene individuals POPPy already imports from
ComptoxAI (``comptox_populated.rdf``), with the ``gene_`` prefix stripped — i.e. gene URIs are
``http://jdr.bio/ontologies/comptox.owl#<symbol>``. It is the DEFINING module for the genes,
so that the pathway (``poppy_pathways.ttl``) and disease (``poppy_diseases.ttl``) edges — which
point at these same gene URIs — land on real nodes.

For each ComptoxAI Gene it emits the individual, an rdfs:label (the gene's common name), and
every ComptoxAI data property it carries (geneSymbol, xrefEnsembl, xrefHGNC, xrefNcbiGene,
typeOfGene, geneSynonyms, commonName, ...). Gene-gene interaction edges are OFF by default
(there are hundreds of thousands); enable with --with-interactions.

Streaming (no rdflib load of the 598 MB file).

USAGE
  python3 scripts/ingest_genes_comptox.py --comptox /path/to/comptox_populated.rdf \
      --out data/enrichment/poppy_genes.ttl
  # add --with-interactions to also emit geneInteractsWithGene edges
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DEFAULT_BASE = "http://jdr.bio/ontologies/comptox.owl#"

RE_GENE_OPEN = re.compile(r'<Gene rdf:about="#gene_([^"]+)"')
RE_GENE_CLOSE = re.compile(r"</Gene>")
RE_DATAPROP = re.compile(r'<([A-Za-z0-9]+) rdf:datatype="[^"]*">(.*?)</\1>')
RE_INTERACTS = re.compile(r'<geneInteractsWithGene rdf:resource="#gene_([^"]+)"')


def ttl_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--comptox", required=True, help="Path to comptox_populated.rdf.")
    ap.add_argument("--out", default="data/enrichment/poppy_genes.ttl")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument(
        "--with-interactions",
        action="store_true",
        help="Also emit geneInteractsWithGene edges (large).",
    )
    ap.add_argument(
        "--interactions-only",
        action="store_true",
        help="Emit ONLY geneInteractsWithGene edges (no gene individuals) — a separate module.",
    )
    args = ap.parse_args()
    if args.interactions_only:
        args.with_interactions = True

    base = args.base
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    n_genes = 0
    n_props = 0
    n_edges = 0
    cur_sym: str | None = None
    cur_props: list[tuple[str, str]] = []
    cur_edges: list[str] = []

    with (
        open(args.comptox, encoding="utf-8", errors="replace") as fh,
        open(out, "w", encoding="utf-8") as w,
    ):
        w.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        w.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
        w.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
        w.write(f"# ComptoxAI gene layer for POPPy — base {base}\n\n")

        def flush():
            nonlocal n_genes, n_props, n_edges
            if cur_sym is None:
                return
            uri = f"<{base}{cur_sym}>"
            if not args.interactions_only:
                w.write(f"{uri} rdf:type owl:NamedIndividual , <{base}Gene> ;\n")
                label = next((v for k, v in cur_props if k == "commonName"), "") or cur_sym
                lines = [f'    rdfs:label "{ttl_escape(label)}"']
                for k, v in cur_props:
                    if v:
                        lines.append(f'    <{base}{k}> "{ttl_escape(v)}"')
                        n_props += 1
                w.write(" ;\n".join(lines) + " .\n")
                n_genes += 1
            for g2 in cur_edges:
                w.write(f"{uri} <{base}geneInteractsWithGene> <{base}{g2}> .\n")
                n_edges += 1

        for line in fh:
            if cur_sym is None and "<Gene " not in line:
                continue
            if cur_sym is None:
                m = RE_GENE_OPEN.search(line)
                if m:
                    cur_sym = m.group(1)
                    cur_props, cur_edges = [], []
                continue
            # inside a gene block
            for dm in RE_DATAPROP.finditer(line):
                cur_props.append((dm.group(1), dm.group(2)))
            if args.with_interactions:
                for im in RE_INTERACTS.finditer(line):
                    cur_edges.append(im.group(1))
            if RE_GENE_CLOSE.search(line):
                flush()
                cur_sym = None
        flush()

    print("=== ComptoxAI GENE LAYER ===")
    print(f"  gene individuals:   {n_genes:,}")
    print(f"  data properties:    {n_props:,}")
    if args.with_interactions:
        print(f"  interaction edges:  {n_edges:,}")
    print(f"  wrote:              {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
