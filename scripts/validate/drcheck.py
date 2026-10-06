"""drcheck.py - full-file disjointness + domain/range check (OWL RL-style) of POPPy N-Triples.
usage: drcheck.py poppy.nt schema_tbox.nt   (prints VIOLATION lines; none = pass)"""

import sys
import collections


def lines(spec, **kw):
    """Yield lines from one file or several comma-separated files (e.g. core,module)."""
    for path in spec.split(","):
        yield from open(path, **kw)


P = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
C = "<http://jdr.bio/ontologies/comptox.owl#"
RT = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
RS = "<http://www.w3.org/2000/01/rdf-schema#"
G = {
    P + "Plant>": ("Plant", None),
    P + "PlantConcept>": ("Plant", None),
    P + "ChemicalConcept>": ("Chem", None),
    P + "NonCompoundConstituent>": ("NonCompound", None),
    C + "Gene>": ("Human", "Gene"),
    C + "Pathway>": ("Human", "Pathway"),
    P + "ProteinTarget>": ("Human", "Target"),
    P + "DiseaseConcept>": ("Human", "Disease"),
    C + "Disease>": ("Human", "Disease"),
    P + "ClinicalTrial>": ("Research", "Trial"),
    P + "ScientificPaper>": ("Research", "Paper"),
    P + "BioactivityMeasurement>": ("Research", "Bioact"),
    P + "TherapeuticEffect>": ("Therapeutic", None),
    P + "MechanismOfAction>": ("Therapeutic", None),
    P + "AdverseEffect>": ("Therapeutic", None),
    P + "TherapeuticConcept>": ("Therapeutic", None),
    P + "HumanConcept>": ("Human", None),
    P + "ResearchConcept>": ("Research", None),
    P + "Plant>": ("Plant", None),
}
tb = [l.split(" ", 2) for l in open(sys.argv[2])]
lst = {s: o[:-3] for s, p, o in tb if p.endswith("#first>")}
rest = {s: o[:-3] for s, p, o in tb if p.endswith("#rest>")}
uni = {s: o[:-3] for s, p, o in tb if p.endswith("#unionOf>")}


def members(b):
    out = []
    while b in lst:
        out.append(lst[b])
        b = rest.get(b)
    return out


def cls(o):
    return [tuple(members(uni[o]))] if o in uni else [(o,)]


dom = collections.defaultdict(list)
rng = collections.defaultdict(list)
for s, p, o in tb:
    o = o[:-3]
    if p == RS + "domain>":
        dom[s] += cls(o)
    if (
        p == RS + "range>"
        and "XMLSchema" not in o
        and o not in ("<http://www.w3.org/2000/01/rdf-schema#Literal>",)
    ):
        rng[s] += cls(o)
F = sys.argv[1]
T = collections.defaultdict(set)
for line in lines(F):
    s, p, o = line.split(" ", 2)
    if p == RT:
        o = o[:-3]
        if o in G:
            T[s].add(G[o])


def ok(groups, alts):
    # alts: tuple of classes (union). individual compatible if some alt compatible with all its group tags
    for c in alts:
        g = G.get(c)
        if g is None:
            return True
        if all(t[0] == g[0] and (g[1] is None or t[1] is None or t[1] == g[1]) for t in groups):
            return True
    return False


bad = collections.Counter()
ex = {}
untyped = collections.Counter()
checked = collections.Counter()
for line in lines(F):
    s, p, o = line.split(" ", 2)
    if p in dom or p in rng:
        o = o[:-3]
        for side, node, ax in (("domain", s, dom.get(p, [])), ("range", o, rng.get(p, []))):
            for alts in ax:
                checked[p, side] += 1
                gs = T.get(node)
                if not gs:
                    if node.startswith("<") or node.startswith("_:"):
                        untyped[p, side] += 1
                    continue
                if not ok(gs, alts):
                    k = (p, side, str(sorted(gs)), str(alts))
                    bad[k] += 1
                    ex.setdefault(k, node)
print("checked", sum(checked.values()))
for k, v in bad.most_common():
    print("VIOLATION", v, k, ex[k])
for k, v in untyped.most_common(20):
    print("UNTYPED", v, k)
