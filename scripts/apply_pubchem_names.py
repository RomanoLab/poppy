#!/usr/bin/env python3
"""apply_pubchem_names.py — apply pubchem_fill.tsv to a POPPy N-Triples build.
New label = PubChem Title (unless it is just an InChIKey/CID), else IUPAC name. Replaces placeholder / InChIKey
labels, removes labelIsPlaceholder, adds hasIUPACName / hasSMILES if missing and a PubChem CID xref.
usage: apply_pubchem_names.py in.nt pubchem_fill.tsv out.nt"""

import sys
import csv
import re
import collections

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
EM = "<http://www.w3.org/2004/02/skos/core#exactMatch>"
IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def lit(v):
    v = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{v}"'


inp, fill, outp = sys.argv[1:4]
fx = {}
for r in csv.DictReader(open(fill), delimiter="\t"):
    t = (r["title"] or "").strip()
    iu = (r["iupac_name"] or "").strip()
    name = t if t and not IK.match(t) and not re.fullmatch(r"(CID)?\s*\d+", t) else iu
    if name or r["smiles"]:
        fx["<" + r["compound_iri"] + ">"] = (name, iu, r["smiles"], r["cid"])
has = collections.defaultdict(set)
for l in open(inp):
    s, p, o = l.split(" ", 2)
    if s in fx and p in (PH + "hasIUPACName>", PH + "hasSMILES>"):
        has[s].add(p)
c = collections.Counter()
with open(outp, "w", buffering=1 << 22) as f:
    for l in open(inp):
        s, p, o = l.split(" ", 2)
        if s in fx and fx[s][0] and p in (L, PH + "labelIsPlaceholder>"):
            continue
        f.write(l)
    for s, (name, iu, smi, cid) in fx.items():
        if name:
            f.write(f"{s} {L} {lit(name)} .\n")
            c["labels"] += 1
        if iu and PH + "hasIUPACName>" not in has[s]:
            f.write(f"{s} {PH}hasIUPACName> {lit(iu)} .\n")
            c["iupac"] += 1
        if smi and PH + "hasSMILES>" not in has[s]:
            f.write(f"{s} {PH}hasSMILES> {lit(smi)} .\n")
            c["smiles"] += 1
        if cid:
            f.write(f"{s} {EM} <http://identifiers.org/pubchem.compound/{cid}> .\n")
print(dict(c), "of", len(fx), "compounds with PubChem data")
