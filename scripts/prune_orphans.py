#!/usr/bin/env python3
"""prune_orphans.py — drop compounds with no plant occurrence AND no paper/target/trial/bioactivity evidence.
usage: prune_orphans.py in.nt out.nt removed.tsv"""

import sys

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
EVID = {
    PH + x + ">"
    for x in [
        "hasPaper",
        "compoundTargetsGene",
        "hasClinicalStudy",
        "targetsProtein",
        "hasMechanismOfAction",
    ]
}
chem = set()
keep = set()
for l in open(sys.argv[1]):
    s, p, o = l.split(" ", 2)
    o = o[:-3]
    if p == T and o == PH + "ChemicalConcept>":
        chem.add(s)
    elif p == PH + "hasCompound>" or p == PH + "activityCompound>":
        keep.add(o)
    elif p in EVID:
        keep.add(s)
rm = chem - keep
n = 0
with open(sys.argv[2], "w", buffering=1 << 22) as f:
    for l in open(sys.argv[1]):
        s, p, o = l.split(" ", 2)
        if s in rm or o[:-3] in rm:
            n += 1
            continue
        f.write(l)
open(sys.argv[3], "w").write("removed_compound_iri\n" + "".join(x[1:-1] + "\n" for x in sorted(rm)))
print("compounds", len(chem), "removed", len(rm), "triples dropped", n)
