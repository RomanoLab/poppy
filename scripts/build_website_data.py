#!/usr/bin/env python3
"""build_website_data.py — stream-generate website/data/*.json from a POPPy N-Triples build
(same file layout Explore.js reads). usage: build_website_data.py poppy_v22.nt website/data [--keep-names old_plants_index.json]
--keep-names: carry 'common' and 'syn' over from an existing plants_index.json (matched by id, then by binomial),
so curated common names / synonyms survive a data rebuild. Compound records: name, formula, mw (RDKit), inchikey, trials.
"""

import sys
import os
import json
import collections
import re

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
CX = "<http://jdr.bio/ontologies/comptox.owl#"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
ALT = "<http://www.w3.org/2004/02/skos/core#altLabel>"
EM = "<http://www.w3.org/2004/02/skos/core#exactMatch>"
nt, D = sys.argv[1], sys.argv[2]
KEEP = sys.argv[sys.argv.index("--keep-names") + 1] if "--keep-names" in sys.argv else None


def loc(u):
    return u[1:-1].split("#", 1)[1]


def val(o):
    return o[1 : o.rfind('"')].replace('\\"', '"').replace("\\\\", "\\")


def djb2(s):
    h = 5381
    for c in s:
        h = ((h * 33) ^ ord(c)) & 0xFFFFFFFF
    return h & 255


plants = {}
comp = collections.defaultdict(dict)
edges = collections.defaultdict(list)
ctg = collections.defaultdict(set)
gene = {}
ptgt = {}
ctrial = collections.Counter()
ptrial = collections.Counter()
ppaper = collections.Counter()
common = {}
fam = {}
ischem = set()
isplant = set()
dis = collections.Counter()
lowsup = collections.defaultdict(set)
for line in open(nt):
    s, p, o = line.split(" ", 2)
    o = o[:-3]
    if p == T:
        if o == PH + "ChemicalConcept>":
            ischem.add(s)
        elif o == PH + "Plant>":
            isplant.add(s)
        elif o == CX + "Gene>":
            gene.setdefault(s, {})
        elif o == PH + "ProteinTarget>":
            ptgt.setdefault(s, {})
    elif p == PH + "hasCompound>":
        edges[s].append(o)
    elif p == PH + "hasCompoundFamilyUnreplicated>":
        lowsup[s].add(o)
    elif p == PH + "compoundTargetsGene>" or p == PH + "targetsProtein>":
        ctg[s].add(o)
    elif p == PH + "hasClinicalStudy>":
        (ctrial if "#Chemical_" in s else ptrial)[s] += 1
    elif p == PH + "hasPaper>":
        ppaper[s] += 1
    elif p == PH + "associatedWithDisease>":
        dis[s] += 1
    elif p == PH + "commonName>":
        common.setdefault(s, val(o))
    elif p == PH + "taxonomicFamily>":
        fam[s] = val(o)
    elif p == L:
        if s.startswith(PH + "Chemical_"):
            comp[s]["name"] = val(o)
        elif s.startswith(CX):
            gene.setdefault(s, {})["name"] = val(o)
        elif s.startswith(PH + "ProteinTarget_"):
            ptgt.setdefault(s, {})["name"] = val(o)
        else:
            plants.setdefault(s, {})["name"] = val(o)
    elif s.startswith(PH + "Chemical_"):
        if p == PH + "hasMolecularFormula>":
            comp[s]["formula"] = val(o)
        elif p == PH + "mw>":
            comp[s]["mw"] = val(o)
        elif p == PH + "hasInChIKey>":
            comp[s]["inchikey"] = val(o)
        elif p == PH + "npClassifierPathway>":
            comp[s].setdefault("np", val(o))
    elif s.startswith(CX):
        if p == ALT:
            gene.setdefault(s, {})["gene"] = val(o)
        elif p == EM and "uniprot/" in o:
            gene.setdefault(s, {})["uniprot"] = o.split("uniprot/")[1][:-1]


# old common names by id
def nb(n):
    w = re.sub(r"[^a-z ]", " ", (n or "").lower()).split()
    return " ".join(w[:2])


old = {}
oldb = {}
try:
    for x in json.load(open(KEEP or os.path.join(D, "plants_index.json"))):
        v = {k: x[k] for k in ("common", "syn") if x.get(k)}
        if v:
            old[x["id"]] = v
            oldb.setdefault(nb(x["name"]), v)
except Exception:
    pass
os.makedirs(D + "/plant_edges", exist_ok=True)
os.makedirs(D + "/compounds", exist_ok=True)
idx = []
shards = collections.defaultdict(dict)
used = set()
for s in isplant:
    cids = edges.get(s)
    if not cids:
        continue
    pid = loc(s)
    cl = [loc(c) for c in cids if c in ischem]
    used.update(cids)
    shards[djb2(pid)][pid] = cl
    rec = {
        "id": pid,
        "name": plants.get(s, {}).get("name", pid),
        "trials": ptrial[s],
        "papers": ppaper[s],
        "nc": len(cl),
    }
    keep = old.get(pid) or oldb.get(nb(rec["name"])) or {}
    cm = keep.get("common") or common.get(s)
    if cm:
        rec["common"] = cm
    if keep.get("syn"):
        rec["syn"] = keep["syn"]
    idx.append(rec)
idx.sort(key=lambda x: (-x["nc"], x["name"]))
cshard = collections.defaultdict(dict)
for s in used:
    d = comp.get(s, {})
    cid = loc(s)
    r = {
        "name": d.get("name", cid),
        "formula": d.get("formula", ""),
        "mw": d.get("mw", ""),
        "inchikey": d.get("inchikey", ""),
        "trials": ctrial[s],
    }
    cshard[djb2(cid)][cid] = r
targets = {}
comp_t = {}
for c, ts in ctg.items():
    if c not in used:
        continue
    lst = []
    for t in sorted(ts):
        tid = loc(t) if t.startswith(PH) else "Gene_" + t[len(CX) : -1]
        if t.startswith(CX):
            g = gene.get(t, {})
            targets[tid] = {
                k: v
                for k, v in {
                    "name": g.get("name") or g.get("gene") or tid,
                    "gene": g.get("gene"),
                    "uniprot": g.get("uniprot"),
                }.items()
                if v
            }
        else:
            targets[tid] = {
                "name": ptgt.get(t, {}).get(
                    "name", tid.replace("ProteinTarget_", "").replace("_", " ")
                )
            }
        lst.append(tid)
    comp_t[loc(c)] = lst
J = lambda obj, path: json.dump(obj, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
for b in range(256):
    J(shards.get(b, {}), f"{D}/plant_edges/{b}.json")
    J(cshard.get(b, {}), f"{D}/compounds/{b}.json")
J(idx, D + "/plants_index.json")
if os.path.exists(D + "/targets.json"):
    J(targets, D + "/targets.json")
    J(comp_t, D + "/compound_targets.json")
meta = {
    "version": "POPPy v2.1",
    "plants": len(idx),
    "compounds": len(used),
    "plant_compound_links": sum(x["nc"] for x in idx),
    "targets": len(targets),
    "compounds_with_targets": len(comp_t),
    "shard": "djb2(id)&255",
}
json.dump(meta, open(D + "/meta.json", "w"), indent=1)
print(json.dumps(meta))
