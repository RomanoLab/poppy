#!/usr/bin/env python3
"""Quick line-based audit of a POPPy N-Triples file. usage: audit_nt.py file.nt [out.json]"""

import sys
import re
import json
import collections

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
sh = (
    lambda u: u.replace(PH, "phyto:")
    .replace("<http://jdr.bio/ontologies/comptox.owl#", "cmptx:")
    .rstrip(">")
    .lstrip("<")
)
pred = collections.Counter()
types = collections.defaultdict(set)
per = collections.defaultdict(collections.Counter)
labels = collections.Counter()
TRACK = {
    PH + x + ">"
    for x in [
        "hasClinicalStudy",
        "hasCompound",
        "targetsGene",
        "compoundTargetsGene",
        "hasPaper",
        "targetsProtein",
    ]
}
objcount = collections.defaultdict(collections.Counter)
for line in open(sys.argv[1]):
    s, p, o = line.split(" ", 2)
    o = o[:-3]
    pred[p] += 1
    if p == T:
        types[s].add(o)
    elif p in TRACK:
        per[p][s] += 1
        objcount[p][o] += 1
    elif p == L:
        labels[s] += 1
tc = collections.Counter()
combo = collections.Counter()
for s, t in types.items():
    for x in t:
        tc[sh(x)] += 1
    combo["|".join(sorted(sh(x) for x in t if "NamedIndividual" not in x))] += 1


def kind(s):
    return re.sub(r"[_0-9].*", "", s.split("#")[-1]) if "#" in s else s[:30]


res = {
    "triples": sum(pred.values()),
    "predicates": {sh(k): v for k, v in pred.most_common()},
    "types": tc.most_common(40),
    "type_combos": combo.most_common(20),
    "subjects_with_multiple_labels": sum(1 for v in labels.values() if v > 1),
    "tracked": {
        sh(p): {
            "subjects": len(d),
            "triples": sum(d.values()),
            "max_per_subject": max(d.values()),
            "top_subjects": [(sh(s), n) for s, n in d.most_common(5)],
            "top_objects": [(sh(o), n) for o, n in objcount[p].most_common(5)],
            "subject_kinds": collections.Counter(kind(s) for s in d).most_common(4),
        }
        for p, d in per.items()
    },
}
out = json.dumps(res, indent=1)
(open(sys.argv[2], "w").write(out) if len(sys.argv) > 2 else print(out))
