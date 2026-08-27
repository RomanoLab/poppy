#!/usr/bin/env python
"""
merge_modules.py — memory-safe merge of small RDF modules into a large RDF/XML ontology.

POPPy's enriched ontology is multi-GB RDF/XML. Loading it into rdflib to add a few hundred
thousand triples needs tens of GB of RAM. This avoids that: it parses only the SMALL addition
modules (Turtle) with rdflib, serialises them to an RDF/XML fragment, and STREAMS the big
target through, injecting the fragment just before the closing </rdf:RDF>. The target is never
fully parsed — only copied byte-for-byte with the additions spliced in.

Use it to fold the pathway and disease layers (and, if needed, the ComptoxAI gene layer) into
the ontology. All modules must use the SAME URIs as the ontology's genes (the gene-stripped
ComptoxAI base, http://jdr.bio/ontologies/comptox.owl#<symbol>) so the new edges land on real
gene nodes.

USAGE
  python3 scripts/merge_modules.py \
      --target /path/to/poppyontology.rdf \
      --add data/enrichment/poppy_pathways.ttl data/enrichment/poppy_diseases.ttl \
      --out /path/to/poppyontology_with_pathways_diseases.rdf

Needs rdflib (only for the small modules). The target may be any size.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

# Prefixes for the injected fragment. Standard ones already exist in POPPy's root (same URIs,
# so harmless to re-declare); 'cmptx' (the ComptoxAI base) is the one the target lacks.
CMPTX = "http://jdr.bio/ontologies/comptox.owl#"
PHYTO = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
INJECT_NS = {"rdf": str(RDF), "rdfs": str(RDFS), "owl": str(OWL), "cmptx": CMPTX, "phyto": PHYTO}


def build_fragment(add_paths: list[str]) -> tuple[str, int]:
    """Parse the small TTL modules and return (rdfxml_body, triple_count).

    body = the RDF/XML statements only (between <rdf:RDF ...> and </rdf:RDF>), using the
    fixed INJECT_NS prefixes so it can be spliced into the target.
    """
    g = Graph()
    for p in add_paths:
        g.parse(p, format="turtle")
    for pfx, uri in INJECT_NS.items():
        g.namespace_manager.bind(pfx, uri, override=True, replace=True)
    xml = g.serialize(format="pretty-xml")
    # strip the XML declaration and the opening/closing <rdf:RDF> wrapper
    xml = re.sub(r"^<\?xml[^>]*\?>\s*", "", xml)
    m = re.search(r"<rdf:RDF\b[^>]*>(.*)</rdf:RDF>\s*$", xml, flags=re.DOTALL)
    body = m.group(1) if m else xml
    return body, len(g)


def merge_stream(target: Path, body: str, out: Path) -> None:
    """Stream target -> out, adding xmlns:cmptx to the root and injecting body at the end."""
    with (
        open(target, encoding="utf-8", errors="replace") as fin,
        open(out, "w", encoding="utf-8", errors="replace") as fout,
    ):
        # 1) read up to and including the opening <rdf:RDF ...> tag (it's near the top)
        head = ""
        while (
            "<rdf:RDF" not in head
            or head.rstrip().endswith("<rdf:RDF")
            or ">" not in head.split("<rdf:RDF", 1)[1]
        ):
            chunk = fin.read(65536)
            if not chunk:
                break
            head += chunk
        pre, rest = head.split("<rdf:RDF", 1)
        gt = rest.index(">")
        root_attrs, after_root = rest[:gt], rest[gt + 1 :]
        # ensure every prefix used by the injected fragment is declared on the root
        for pfx, uri in INJECT_NS.items():
            if f"xmlns:{pfx}=" not in root_attrs:
                root_attrs += f' xmlns:{pfx}="{uri}"'
        fout.write(pre + "<rdf:RDF" + root_attrs + ">")
        # 2) stream the remainder, holding back a small tail so we can inject before </rdf:RDF>
        CLOSE = "</rdf:RDF>"
        buf = after_root
        while True:
            chunk = fin.read(1 << 20)
            if not chunk:
                break
            buf += chunk
            if len(buf) > (1 << 21):
                keep = len(CLOSE) + 64
                fout.write(buf[:-keep])
                buf = buf[-keep:]
        idx = buf.rfind(CLOSE)
        if idx == -1:
            raise SystemExit("[merge] could not find closing </rdf:RDF> in target")
        fout.write(buf[:idx])
        fout.write("\n<!-- BEGIN merged modules (POPPy pathways/diseases) -->\n")
        fout.write(body)
        fout.write("\n<!-- END merged modules -->\n")
        fout.write(buf[idx:])


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--target", required=True, help="Large RDF/XML ontology to extend.")
    ap.add_argument("--add", nargs="+", required=True, help="Small .ttl module(s) to inject.")
    ap.add_argument("--out", required=True, help="Merged output path.")
    args = ap.parse_args()

    print(f"[1/2] parsing {len(args.add)} module(s)")
    body, n = build_fragment(args.add)
    print(f"      {n:,} triples to inject")

    print(f"[2/2] streaming {args.target} -> {args.out}")
    merge_stream(Path(args.target), body, Path(args.out))
    print(f"\nDone. Merged ontology: {args.out}")
    print("Verify by loading in Protégé or a triplestore; the injected block is delimited by")
    print("'<!-- BEGIN merged modules ...-->' near the end of the file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
