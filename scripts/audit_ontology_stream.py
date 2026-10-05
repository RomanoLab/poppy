import re
import sys
import json
import time
import collections
import itertools
import xml.etree.ElementTree as ET

F = sys.argv[1]
OUT = sys.argv[2]
RDFNS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
NSMAP = {
    "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#": "phyto:",
    "http://jdr.bio/ontologies/comptox.owl#": "cmptx:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    RDFNS: "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://purl.obolibrary.org/obo/": "obo:",
    "http://identifiers.org/": "idorg:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}


def short(u):
    for k, v in NSMAP.items():
        if u.startswith(k):
            return v + u[len(k) :]
    return u


def tagq(t):  # '{ns}local' -> short
    if t[0] == "{":
        ns, l = t[1:].split("}", 1)
        return short(ns + l)
    return t


A_ABOUT = "{%s}about" % RDFNS
A_NODE = "{%s}nodeID" % RDFNS
A_RES = "{%s}resource" % RDFNS
A_DT = "{%s}datatype" % RDFNS
A_PT = "{%s}parseType" % RDFNS
A_ID = "{%s}ID" % RDFNS
IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
types = collections.defaultdict(set)
predsets = {}
intern_fs = {}
open_preds = {}
pred_triples = collections.Counter()
lit_stats = collections.defaultdict(collections.Counter)
dt_counter = collections.defaultdict(collections.Counter)
obj_sample = collections.defaultdict(list)
tracked = collections.defaultdict(lambda: collections.defaultdict(int))
mw = {}
mwconf = set()
formula = {}
fconf = set()
plabel = {}
ikey = {}
ikconf = set()
labels_any = collections.Counter()
schema = collections.defaultdict(list)
desc_blocks = collections.Counter()
SCHEMA_P = {
    "rdfs:domain",
    "rdfs:range",
    "rdfs:subClassOf",
    "owl:inverseOf",
    "rdfs:subPropertyOf",
    "owl:equivalentClass",
}
bn = itertools.count()


def addp(s, p):
    open_preds.setdefault(s, set()).add(p)


def obj(s, p, o):
    pred_triples[p] += 1
    addp(s, p)
    if p == "rdf:type":
        types[s].add(o)
        return
    if len(obj_sample[p]) < 50000:
        obj_sample[p].append(o)
    if not (
        p.startswith("skos:")
        or p.startswith("owl:")
        or p.startswith("rdfs:")
        or p.startswith("rdf:")
    ):
        tracked[p][s] += 1
    if p in SCHEMA_P:
        schema[(s, p)].append(o)


def lit(s, p, t, dt):
    pred_triples[p] += 1
    addp(s, p)
    t = (t or "").strip()
    st = lit_stats[p]
    if t.lower() in ("nan", "none", "null", "na", "n/a", "", "-"):
        st["na_or_empty_or_dash"] += 1
    if IK.match(t):
        st["inchikey_like"] += 1
    dt_counter[p][short(dt) if dt else "plain"] += 1
    if p == "phyto:hasMolecularWeight":
        try:
            v = float(t)
            if s in mw and abs(mw[s] - v) > 0.01:
                mwconf.add(s)
            else:
                mw.setdefault(s, v)
        except ValueError:
            st["unparseable"] += 1
    elif p == "phyto:hasMolecularFormula":
        if s in formula and formula[s] != t:
            fconf.add(s)
        else:
            formula.setdefault(s, t)
    elif p == "phyto:hasInChIKey":
        if s in ikey and ikey[s] != t:
            ikconf.add(s)
        else:
            ikey.setdefault(s, t)
    elif p == "rdfs:label" and (s.startswith("phyto:Organism_") or s.startswith("phyto:Plant_")):
        plabel.setdefault(s, t)
    if p == "rdfs:label":
        labels_any[t[:60]] += 0  # placeholder no-op


def close_subj(s):
    ps = open_preds.pop(s, None)
    if ps is None and s in predsets:
        return
    old = predsets.get(s)
    fs = frozenset((ps or set()) | (old or set()))
    predsets[s] = intern_fs.setdefault(fs, fs)


stack = []  # entries: ("node",subj) or ("prop",subj,pred,elem,objset)
t0 = time.time()
n = 0
root = None
for ev, el in ET.iterparse(F, events=("start", "end")):
    if ev == "start":
        n += 1
        if n % 2_000_000 == 0:
            print(f"{n/1e6:.0f}M elems {time.time()-t0:.0f}s subj={len(predsets)}", flush=True)
        if root is None:
            root = el
            continue
        parent = stack[-1] if stack else None
        if parent is None or parent[0] == "prop":  # node element
            a = el.attrib
            if A_ABOUT in a:
                s = short(a[A_ABOUT])
            elif A_ID in a:
                s = "#" + a[A_ID]
            elif A_NODE in a:
                s = "_:" + a[A_NODE]
            else:
                s = "_:g%d" % next(bn)
            t = tagq(el.tag)
            desc_blocks[(parent is None)] += 1
            if t != "rdf:Description":
                obj(s, "rdf:type", t)
            if parent is not None:
                parent[4].append(s)
            stack.append(("node", s))
        else:  # property element
            stack.append(("prop", parent[1], tagq(el.tag), el, []))
    else:
        if el is root:
            break
        top = stack.pop()
        if top[0] == "node":
            close_subj(top[1])
        else:
            _, s, p, e, objs = top
            a = e.attrib
            if objs:
                for o in objs:
                    obj(s, p, o)
            elif A_RES in a:
                obj(s, p, short(a[A_RES]))
            elif A_NODE in a:
                obj(s, p, "_:" + a[A_NODE])
            else:
                lit(s, p, e.text, a.get(A_DT))
        if len(stack) == 0 or (len(stack) == 1 and stack[0][0] == "node" and top[0] == "node"):
            pass
        if not stack:
            el.clear()
            root.clear()
print("parsed", n, "elements", time.time() - t0, "s", flush=True)


def tkey(s):
    t = types.get(s)
    return (
        "|".join(sorted(x for x in t if x != "owl:NamedIndividual"))
        if t
        else "(untyped/undeclared)"
    )


type_counts = collections.Counter()
for s, t in types.items():
    for x in t:
        type_counts[x] += 1
combo = collections.Counter(tkey(s) for s in predsets)
stbp = collections.defaultdict(collections.Counter)
for s, fs in predsets.items():
    k = tkey(s)
    for p in fs:
        stbp[p][k] += 1
otbp = {p: collections.Counter(tkey(o) for o in v).most_common(6) for p, v in obj_sample.items()}
undeclared_examples = {p: [o for o in v if o not in types][:5] for p, v in obj_sample.items()}
M = {
    "C": 12.011,
    "H": 1.008,
    "N": 14.007,
    "O": 15.999,
    "S": 32.06,
    "P": 30.974,
    "Cl": 35.45,
    "Br": 79.904,
    "F": 18.998,
    "I": 126.904,
    "Na": 22.99,
    "K": 39.098,
    "Si": 28.085,
    "B": 10.81,
    "Se": 78.971,
    "Mg": 24.305,
    "Ca": 40.078,
    "Fe": 55.845,
    "Zn": 65.38,
    "Cu": 63.546,
    "Co": 58.933,
    "As": 74.922,
    "Hg": 200.59,
    "Al": 26.982,
    "Li": 6.94,
    "Mn": 54.938,
    "Sn": 118.71,
    "Pt": 195.08,
    "Ge": 72.63,
    "Te": 127.6,
    "Bi": 208.98,
    "Ba": 137.33,
    "Sr": 87.62,
}


def fmw(f):
    if not re.fullmatch(r"([A-Z][a-z]?\d*)+", f or ""):
        return None
    s = 0
    for e, k in re.findall(r"([A-Z][a-z]?)(\d*)", f):
        if e not in M:
            return None
        s += M[e] * (int(k) if k else 1)
    return s


chk = bad = 0
ex = []
for s, v in mw.items():
    c = fmw(formula.get(s))
    if c is None:
        continue
    chk += 1
    if abs(v - c) > 2:
        bad += 1
        if len(ex) < 8:
            ex.append((s, formula[s], v, round(c, 2)))
trk = {
    p: {
        "subjects": len(d),
        "triples": sum(d.values()),
        "max": max(d.values()),
        "top": [(s, c, plabel.get(s)) for s, c in sorted(d.items(), key=lambda x: -x[1])[:6]],
    }
    for p, d in tracked.items()
}
lbl = collections.Counter(v.strip().lower() for v in plabel.values())
res = {
    "elements": n,
    "subjects": len(predsets),
    "node_elems_toplevel_vs_nested": {str(k): v for k, v in desc_blocks.items()},
    "type_counts": type_counts.most_common(80),
    "type_combos": combo.most_common(40),
    "pred_triples": pred_triples.most_common(),
    "lit_stats": {p: dict(c) for p, c in lit_stats.items()},
    "datatypes": {p: dict(c) for p, c in dt_counter.items()},
    "subj_types_by_pred": {p: c.most_common(5) for p, c in stbp.items()},
    "obj_types_by_pred_sample50k": otbp,
    "undeclared_obj_examples": undeclared_examples,
    "tracked": trk,
    "mw": {
        "subjects_with_mw": len(mw),
        "conflicting_mw": len(mwconf),
        "formula_subjects": len(formula),
        "conflicting_formula": len(fconf),
        "checked": chk,
        "mw_vs_formula_gt2Da": bad,
        "examples": ex,
    },
    "inchikey": {
        "subjects": len(ikey),
        "conflicting": len(ikconf),
        "distinct_values": len(set(ikey.values())),
    },
    "plant_label_dups": sum(c - 1 for c in lbl.values() if c > 1),
    "plant_like_subjects": len(plabel),
    "schema": {f"{s} {p}": v for (s, p), v in schema.items()},
}
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("done", time.time() - t0, flush=True)
