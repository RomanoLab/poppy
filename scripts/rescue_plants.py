#!/usr/bin/env python3
"""rescue_plants.py — re-admit plants that v2.2 dropped but that are real taxa.

Candidates: plants in the previous website index (pre-v2.2) absent from v2.2 by id and binomial.
Rescued when the binomial is an NCBI Viridiplantae species, the genus is an NCBI plant genus (epithet sane),
or a one-letter genus typo resolves to exactly one NCBI plant species (e.g. Grataegus -> Crataegus).
Rejected: pharmacognosy drug names, family names, sp./spp./cf., non-binomials, genera not in NCBI plants.
Their compound occurrences are restored from the previous website build (COCONUT/v1 occurrences) by InChIKey.

usage: rescue_plants.py v22.nt dropped_classified.json up_web_dir idx2.pkl nodes.dmp add.nt new_compounds.nt decisions.tsv
"""

import sys
import re
import json
import pickle
import collections

PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
NI = "<http://www.w3.org/2002/07/owl#NamedIndividual>"


def P(x):
    return "<" + PH + x + ">"


def lit(v):
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{v}"'


def nb(n):
    w = re.sub(r"[^a-z\- ]", " ", (n or "").lower()).split()
    return " ".join(w[:2]) if len(w) >= 2 else ""


def djb2(s):
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return h & 255


def safe(x):
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.\-]", "_", x)).strip("_")


nt, dj, upd, idxp, nodes, out_add, out_new, out_dec = sys.argv[1:9]
plant_by_b = {}
chem = set()
for line in open(nt):
    s, p, o = line.split(" ", 2)
    if p == L and (s.startswith(P("Plant_")[:-1]) or s.startswith(P("Organism_")[:-1])):
        plant_by_b.setdefault(nb(o[1 : o.rfind('"')]), s)
    elif p == T and o.startswith(P("ChemicalConcept")):
        chem.add(s)
pn = pickle.load(open(idxp, "rb"))["plant_names"]
parent, rank = {}, {}
for line in open(nodes):
    x = line.split("\t|\t", 3)
    t = int(x[0])
    parent[t] = int(x[1])
    if x[2] in ("family", "genus"):
        rank[t] = x[2]
gname, names = {}, {}
for line in open(nodes.replace("nodes.dmp", "names.dmp")):
    x = line.split("\t|\t")
    if x[3].startswith("scientific name"):
        t = int(x[0])
        if t in rank:
            names[t] = x[1]
            if rank[t] == "genus":
                gname.setdefault(x[1].lower(), t)


def lineage(t):
    fam = gen = None
    n = 0
    while t in parent and n < 60:
        r = rank.get(t)
        if r == "genus" and gen is None:
            gen = t
        if r == "family":
            return t, gen
        if t == 1:
            break
        t = parent[t]
        n += 1
    return fam, gen


drop = json.load(open(dj))
shard_e, shard_c = {}, {}


def edges(pid):
    b = djb2(pid)
    if b not in shard_e:
        shard_e[b] = json.load(open(f"{upd}/e{b}.json"))
    return shard_e[b].get(pid, [])


def crec(cid):
    b = djb2(cid)
    if b not in shard_c:
        shard_c[b] = json.load(open(f"{upd}/c{b}.json"))
    return shard_c[b].get(cid)


IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
add = open(out_add, "w")
new = open(out_new, "w")
dec = open(out_dec, "w")
dec.write("previous_id\tname\tdecision\tcorrected_name\tontology_iri\tcompounds_restored\n")
c = collections.Counter()
newc = set()
for x in drop:
    k = x["_k"]
    if not k.startswith("rescue"):
        dec.write(f"{x['id']}\t{x['name']}\t{k}\t\t\t0\n")
        c[k] += 1
        continue
    name = x["_fix"] or " ".join(x["name"].split()[:2])
    b = nb(name)
    s = plant_by_b.get(b)
    merged = s is not None
    if not merged:
        s = P(safe(x["id"]))
        status = {
            "rescue_ncbi_species": "ncbi_plant_name",
            "rescue_ncbi_genus": "ncbi_plant_genus_only",
            "rescue_typo_corrected": "typo_corrected_to_ncbi_name",
        }[k]
        for tr in (
            (s, T, P("Plant")),
            (s, T, NI),
            (s, L, lit(name)),
            (s, P("taxonomyStatus"), lit(status)),
            (s, P("rescuedInVersion"), lit("2.3")),
        ):
            add.write(" ".join(tr) + " .\n")
        if x["_fix"] or name != x["name"]:
            add.write(f"{s} <{SKOS}altLabel> {lit(x['name'])} .\n")
        for cm in re.split(r"\s*;\s*", x.get("common") or ""):
            if cm:
                add.write(f"{s} {P('commonName')} {lit(cm)} .\n")
        tx = pn.get(b)
        if tx:
            add.write(f"{s} {P('hasTaxon')} {lit(tx)} .\n")
            add.write(f"{s} <{SKOS}exactMatch> <http://purl.obolibrary.org/obo/NCBITaxon_{tx}> .\n")
        gt = gname.get(b.split(" ")[0])
        f, g = lineage(tx or gt) if (tx or gt) else (None, None)
        if f:
            add.write(f"{s} {P('taxonomicFamily')} {lit(names.get(f, f))} .\n")
        if g or gt:
            add.write(
                f"{s} {P('taxonomicGenus')} {lit(names.get(g or gt, b.split(' ')[0].capitalize()))} .\n"
            )
    n = 0
    for cid in edges(x["id"]):
        r = crec(cid)
        ik = (r or {}).get("inchikey", "")
        if not IK.match(ik):
            continue
        ci = P("Chemical_ik_" + ik.replace("-", "_"))
        if ci not in chem and ci not in newc:
            newc.add(ci)
            new.write(
                f"{ci} {T} {P('ChemicalConcept')} .\n{ci} {T} {NI} .\n{ci} {P('hasInChIKey')} {lit(ik)} .\n"
            )
            nm = r.get("name", "")
            new.write(f"{ci} {L} {lit(nm if nm and not IK.match(nm) else ik)} .\n")
            if r.get("formula"):
                new.write(f"{ci} {P('hasMolecularFormula')} {lit(r['formula'])} .\n")
        add.write(f"{s} {P('hasCompound')} {ci} .\n{s} {P('hasCompoundPerCOCONUT')} {ci} .\n")
        n += 1
    c[k + ("_merged_into_existing" if merged else "")] += 1
    c["compound_links_restored"] += n
    dec.write(f"{x['id']}\t{x['name']}\t{k}\t{x['_fix'] or ''}\t{s[1:-1]}\t{n}\n")
d = P("rescuedInVersion")
add.write(
    f"{d} {T} <http://www.w3.org/2002/07/owl#DatatypeProperty> .\n{d} {L} {lit('rescued in POPPy version')} .\n"
)
c["new_compounds"] = len(newc)
print(json.dumps(c, indent=1))
