#!/usr/bin/env python
"""
ingest_diseases_doid.py — add Disease individuals (DOID) + gene→disease edges to POPPy.

The ComptoxAI populated export has NO diseases, so the disease layer comes from:

  * DISEASES (Jensen Lab, https://diseases.jensenlab.org) — gene↔disease associations that are
    natively keyed by BOTH gene symbol AND Disease Ontology ID (DOID). Because it uses gene
    symbols, it joins directly onto POPPy's genes (imported from ComptoxAI as ``#<symbol>`` with
    the ``gene_`` prefix stripped) — no identifier crosswalk needed.
  * Disease Ontology (doid.obo) — canonical DOID labels + the is-a hierarchy.

Only diseases linked to a gene that actually exists in POPPy are emitted (gated by the gene
symbols found in ``comptox_populated.rdf``), so every disease has a target path. Output is an
additive Turtle module you merge into the enriched ontology, in the SAME comptox base namespace
as your genes/pathways.

Emitted (base = the gene-stripped ComptoxAI base, matching your genes):
    <base#DOID_0050686> a owl:NamedIndividual , <base#Disease> ;
        rdfs:label "..." ; <base#xrefDiseaseOntology> "DOID:0050686" .
    <base#DOID_child> <base#diseaseSubtypeOf> <base#DOID_parent> .        # DO is-a hierarchy
    <base#GENESYM> <base#geneAssociatedWithDisease> <base#DOID_0050686> . # DISEASES association

USAGE (needs network for the two downloads; run in your build env)
  python3 scripts/ingest_diseases_doid.py \
      --comptox /path/to/comptox_populated.rdf \
      --out data/enrichment/poppy_diseases.ttl \
      --min-confidence 2.0
"""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

DEFAULT_BASE = "http://jdr.bio/ontologies/comptox.owl#"
# DISEASES channels: knowledge (manually curated, highest quality), experiments, textmining
# (automated, noisier), integrated (all combined). Curated 'knowledge' is best for a citable
# resource. URL pattern: https://download.jensenlab.org/human_disease_<channel>_full.tsv
DISEASES_URL_TMPL = "https://download.jensenlab.org/human_disease_{channel}_full.tsv"
DOID_OBO_URL = "https://purl.obolibrary.org/obo/doid.obo"

RE_DOID = re.compile(r"DOID:(\d+)")
RE_GENE_URI = re.compile(r'<Gene rdf:about="#gene_([^"]+)"')


def fetch(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [cache] {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url} -> {dest} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "poppy-disease-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:  # noqa: S310
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    return dest


def load_poppy_genes(comptox_path: Path) -> set[str]:
    """Gene symbols present in POPPy = the ComptoxAI genes (lowercase, gene_ stripped)."""
    genes: set[str] = set()
    with open(comptox_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "<Gene " not in line:
                continue
            m = RE_GENE_URI.search(line)
            if m:
                genes.add(m.group(1).lower())
    return genes


def parse_doid_obo(path: Path):
    """Return {doid_curie: {'name':str, 'parents':[doid_curie]}} from doid.obo."""
    terms: dict[str, dict] = {}
    cur: dict | None = None
    cur_id: str | None = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line == "[Term]":
                cur = {"name": "", "parents": []}
                cur_id = None
            elif cur is not None:
                if line.startswith("id: DOID:"):
                    cur_id = line[4:].strip()
                    terms[cur_id] = cur
                elif line.startswith("name:"):
                    cur["name"] = line[5:].strip()
                elif line.startswith("is_a:"):
                    m = RE_DOID.search(line)
                    if m:
                        cur["parents"].append(f"DOID:{m.group(1)}")
                elif line.startswith("is_obsolete: true") and cur_id:
                    terms.pop(cur_id, None)
    return terms


def parse_diseases_tsv(path: Path, min_conf: float):
    """Yield (gene_symbol_lower, doid_curie, disease_name, confidence)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            doid = None
            for p in parts:
                m = re.fullmatch(r"DOID:\d+", p.strip())
                if m:
                    doid = p.strip()
                    break
            if not doid:
                continue
            # DISEASES integrated layout: gene_id, symbol, DOID, name, z, confidence
            symbol = parts[1].strip().lower()
            try:
                di = parts.index(doid)
                name = parts[di + 1].strip() if di + 1 < len(parts) else ""
            except ValueError:
                name = ""
            conf = 0.0
            for p in reversed(parts):
                try:
                    conf = float(p)
                    break
                except ValueError:
                    continue
            if symbol and conf >= min_conf:
                yield symbol, doid, name, conf


def uri_doid(curie: str) -> str:
    return curie.replace(":", "_")  # DOID:123 -> DOID_123


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--comptox", required=True, help="comptox_populated.rdf (for the gene gate).")
    ap.add_argument("--out", default="data/enrichment/poppy_diseases.ttl")
    ap.add_argument("--cache-dir", default="data/raw/diseases")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument(
        "--channel",
        default="knowledge",
        choices=["knowledge", "experiments", "textmining", "integrated"],
        help="DISEASES channel. 'knowledge' = manually curated (default, best for a citable "
        "resource); 'integrated' = all combined; others are automated/noisier.",
    )
    ap.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="DISEASES confidence cutoff (0-5). Default 0.0 — keeps all curated 'knowledge' "
        "associations; raise it for the noisier channels.",
    )
    args = ap.parse_args()

    cache = Path(args.cache_dir)
    print(f"[1/4] POPPy gene set (from ComptoxAI); DISEASES channel: {args.channel}")
    genes = load_poppy_genes(Path(args.comptox))
    print(f"      {len(genes):,} gene symbols")

    print("[2/4] downloads")
    dis_name = f"human_disease_{args.channel}_full.tsv"
    dis_tsv = fetch(DISEASES_URL_TMPL.format(channel=args.channel), cache / dis_name)
    obo = fetch(DOID_OBO_URL, cache / "doid.obo")

    print("[3/4] parse DO + DISEASES")
    do = parse_doid_obo(obo)
    print(f"      DO terms: {len(do):,}")

    edges: set[tuple[str, str]] = set()  # (symbol, doid)
    used_doids: set[str] = set()
    kept = dropped_gene = 0
    for symbol, doid, name, conf in parse_diseases_tsv(dis_tsv, args.min_confidence):
        if symbol not in genes:
            dropped_gene += 1
            continue
        edges.add((symbol, doid))
        used_doids.add(doid)
        kept += 1
    print(
        f"      associations kept: {kept:,} (>= conf {args.min_confidence}); "
        f"dropped (gene not in POPPy): {dropped_gene:,}"
    )

    # include hierarchy ancestors so the is-a tree is connected for used diseases
    def ancestors(d):
        seen, stack = set(), list(do.get(d, {}).get("parents", []))
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            stack.extend(do.get(p, {}).get("parents", []))
        return seen

    all_doids = set(used_doids)
    for d in list(used_doids):
        all_doids |= ancestors(d)

    print("[4/4] write TTL")
    base = args.base
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        fh.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
        fh.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n\n")
        fh.write(f"<{base}geneAssociatedWithDisease> rdf:type owl:ObjectProperty .\n")
        fh.write(f"<{base}diseaseSubtypeOf> rdf:type owl:ObjectProperty .\n\n")
        for d in sorted(all_doids):
            info = do.get(d)
            label = (info or {}).get("name", "") or d
            uri = f"<{base}{uri_doid(d)}>"
            fh.write(f"{uri} rdf:type owl:NamedIndividual , <{base}Disease> ;\n")
            fh.write(f'    rdfs:label "{label.replace(chr(34), chr(39))}" ;\n')
            fh.write(f'    <{base}xrefDiseaseOntology> "{d}" ;\n')
            fh.write('    rdfs:comment "source: Disease Ontology / DISEASES" .\n')
            for p in (info or {}).get("parents", []):
                if p in all_doids:
                    fh.write(f"{uri} <{base}diseaseSubtypeOf> <{base}{uri_doid(p)}> .\n")
        for symbol, doid in sorted(edges):
            fh.write(
                f"<{base}{symbol}> <{base}geneAssociatedWithDisease> <{base}{uri_doid(doid)}> .\n"
            )

    print("\n=== DISEASE / DOID INGEST ===")
    print(f"  gene->disease edges: {len(edges):,}")
    print(f"  diseases (with ancestors): {len(all_doids):,}")
    print(f"  distinct genes linked:     {len({g for g, _ in edges}):,}")
    print(f"  wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
