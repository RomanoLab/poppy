#!/usr/bin/env python3
"""
enrich_v21.py — v2.1 additions on top of poppy_phase2.nt (writes an N-Triples ADD file).

  python3 enrich_v21.py phase2.nt idx2.pkl add_v21.nt --taxdump data/raw/taxdump/nodes.dmp \
      --phda "~/Downloads/CMAUPv2.0_download_Plant_Human_Disease_Associations (1).txt" \
      --cmaup-plants ~/Downloads/CMAUPv2.0_download_Plants.txt --report data/patches/v21_report.json

A) Occurrence plausibility. A plant->compound link is ALSO asserted as phyto:hasCompoundFamilyUnreplicated
   (it stays in hasCompound) when all hold:
     - its only source is COCONUT;
     - the compound occurs in >= 3 plants outside the plant's NCBI family;
     - no other plant of the same NCBI family is reported with the compound (any source).
   Every resolvable plant gets phyto:taxonomicFamily / taxonomicGenus (NCBI).
B) CMAUP plant–human disease associations -> phyto:associatedWithDisease + four evidence-specific
   sub-properties; disease nodes keyed by ICD-11 code, skos:closeMatch to DOID (cmptx:Disease) on exact name.
"""

import re
import csv
import json
import pickle
import argparse
import collections
import time

PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
CX = "http://jdr.bio/ontologies/comptox.owl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"
I = lambda u: "<" + u + ">"
P = lambda l: I(PH + l)
TYPE = I(RDF + "type")
LABEL = I(RDFS + "label")


def lit(v, dt=None):
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{v}"^^<{dt}>' if dt else f'"{v}"'


def nb(x):
    w = re.sub(r"[^a-z\- ]", " ", (x or "").lower()).split()
    return " ".join(w[:2]) if len(w) >= 2 else ""


def safe(x):
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.\-]", "_", x)).strip("_")


def isna(v):
    return v is None or str(v).strip().lower() in {"", "n.a.", "na", "nan", "none"}


ap = argparse.ArgumentParser()
ap.add_argument("nt")
ap.add_argument("idx")
ap.add_argument("out")
ap.add_argument("--taxdump")
ap.add_argument("--phda")
ap.add_argument("--cmaup-plants")
ap.add_argument("--report")
a = ap.parse_args()
t0 = time.time()
rep = collections.Counter()
SRC = {
    P("hasCompoundPerCMAUP"): "CMAUP",
    P("hasCompoundPerCOCONUT"): "COCONUT",
    P("hasCompoundPerDrDuke"): "DrDuke",
}
occ = collections.defaultdict(set)
taxid = {}
plab = {}
dis_lab = {}
clab = {}
for line in open(a.nt):
    s, p, o = line.split(" ", 2)
    o = o[:-3]
    if p in SRC:
        occ[(s, o)].add(SRC[p])
    elif p == P("hasTaxon"):
        v = o[1 : o.rfind('"')]
        if v.isdigit():
            taxid[s] = int(v)
    elif p == LABEL:
        if s.startswith(P("Plant_")[:-1]) or s.startswith(P("Organism_")[:-1]):
            plab[s] = o[1 : o.rfind('"')]
        elif s.startswith("<" + CX + "DOID_"):
            dis_lab[o[1 : o.rfind('"')].lower()] = s
        elif s.startswith(P("Chemical_")[:-1]):
            clab[s] = o[1 : o.rfind('"')]
print("read", len(occ), "occurrences", f"{time.time()-t0:.0f}s", flush=True)
X = pickle.load(open(a.idx, "rb"))
pn = X["plant_names"]
del X
parent = {}
rank = {}
for line in open(a.taxdump):
    x = line.split("\t|\t", 3)
    t = int(x[0])
    parent[t] = int(x[1])
    if x[2] in ("family", "genus"):
        rank[t] = x[2]
names = {}
for line in open(a.taxdump.replace("nodes.dmp", "names.dmp")):
    x = line.split("\t|\t")
    if x[3].startswith("scientific name"):
        t = int(x[0])
        if t in rank:
            names[t] = x[1]


def lineage(t):
    fam = gen = None
    n = 0
    while t in parent and n < 60:
        r = rank.get(t)
        if r == "genus" and gen is None:
            gen = t
        if r == "family":
            fam = t
            break
        if t == 1:
            break
        t = parent[t]
        n += 1
    return fam, gen


pfam = {}
pgen = {}
out = open(a.out, "w", buffering=1 << 22)
W = lambda s, p, o: out.write(f"{s} {p} {o} .\n")
for s, lab in plab.items():
    t = taxid.get(s) or pn.get(nb(lab))
    if not t:
        rep["plant_no_taxid"] += 1
        continue
    f, g = lineage(t)
    if f:
        pfam[s] = f
        W(s, P("taxonomicFamily"), lit(names.get(f, str(f))))
        rep["plant_family_resolved"] += 1
    if g:
        pgen[s] = g
        W(s, P("taxonomicGenus"), lit(names.get(g, str(g))))
    if not taxid.get(s):
        W(s, P("hasTaxon"), lit(t))
        W(s, I(SKOS + "exactMatch"), I("http://purl.obolibrary.org/obo/NCBITaxon_" + str(t)))
        rep["plant_taxid_added_by_name"] += 1
print("taxonomy done", f"{time.time()-t0:.0f}s", flush=True)
by_c = collections.defaultdict(list)
for (pl, c), src in occ.items():
    by_c[c].append((pl, src))
flag_ex = collections.Counter()
flagged = 0
for c, lst in by_c.items():
    if len(lst) < 4:
        continue
    fams = collections.Counter(pfam.get(pl) for pl, _ in lst)
    for pl, src in lst:
        if src != {"COCONUT"}:
            continue
        f = pfam.get(pl)
        if f is None or len(lst) - fams[f] < 3:
            continue
        if fams[f] == 1:  # the only plant in its family reported with this compound
            W(pl, P("hasCompoundFamilyUnreplicated"), c)
            flagged += 1
            flag_ex[(clab.get(c, c), names.get(f, "?"))] += 1
rep["occurrences_total"] = len(occ)
rep["coconut_only_occurrences"] = sum(1 for v in occ.values() if v == {"COCONUT"})
rep["occurrences_flagged_low_support"] = flagged
s = P("hasCompoundFamilyUnreplicated")
W(s, TYPE, I(OWL + "ObjectProperty"))
W(s, I(RDFS + "subPropertyOf"), P("hasCompound"))
W(s, LABEL, lit("has compound (unreplicated in family)"))
W(s, I(RDFS + "domain"), P("Plant"))
W(s, I(RDFS + "range"), P("ChemicalConcept"))
W(
    s,
    I(RDFS + "comment"),
    lit(
        "Flag on a COCONUT-only occurrence that no other plant of the same NCBI family shares (any source), while the compound is reported from >=3 plants in other families. Weak heuristic: marks reports that are unreplicated at family level; many are real. Does not catch clustered mis-annotations (e.g. paclitaxel in 3 Garcinia species)."
    ),
)
for k, lab in [("taxonomicFamily", "NCBI family"), ("taxonomicGenus", "NCBI genus")]:
    W(P(k), TYPE, I(OWL + "DatatypeProperty"))
    W(P(k), LABEL, lit(lab))
    W(P(k), I(RDFS + "domain"), P("Plant"))
    W(P(k), I(RDFS + "range"), I(XSD + "string"))
print("plausibility done", flagged, f"{time.time()-t0:.0f}s", flush=True)
bin2p = {}
for s, lab in plab.items():
    bin2p.setdefault(nb(lab), s)
cp = {}
for r in csv.DictReader(open(a.cmaup_plants, encoding="utf-8", errors="replace"), delimiter="\t"):
    nm = r["Species_Name"] if not isna(r["Species_Name"]) else r["Plant_Name"]
    cp[r["Plant_ID"]] = bin2p.get(nb(nm))
EV = {
    "Association_by_Therapeutic_Target": "associatedWithDiseaseByTarget",
    "Association_by_Disease_Transcriptiome_Reversion": "associatedWithDiseaseByTranscriptomeReversion",
    "Association_by_Clinical_Trials_of_Plant": "associatedWithDiseaseByPlantTrial",
    "Association_by_Clinical_Trials_of_Plant_Ingredients": "associatedWithDiseaseByIngredientTrial",
}
dnodes = {}
pairs = set()
evc = collections.Counter()
onlyweak = collections.Counter()
for r in csv.DictReader(open(a.phda, encoding="utf-8", errors="replace"), delimiter="\t"):
    pl = cp.get(r["Plant_ID"])
    if not pl:
        rep["phda_rows_plant_unresolved"] += 1
        continue
    code = r["ICD-11 Code"].strip()
    name = r["Disease"].strip()
    if not code and not name:
        continue
    d = P("Disease_ICD11_" + safe(code or name))
    if d not in dnodes:
        dnodes[d] = name
        W(d, TYPE, P("DiseaseConcept"))
        W(d, TYPE, I(OWL + "NamedIndividual"))
        W(d, LABEL, lit(name))
        if code:
            W(d, P("icd11Code"), lit(code))
        if not isna(r["Disease_Category"]):
            W(d, P("diseaseCategory"), lit(re.sub(r"^\d+\.", "", r["Disease_Category"]).strip()))
        m = dis_lab.get(name.lower())
        if m:
            W(d, I(SKOS + "closeMatch"), m)
            rep["disease_mapped_to_DOID"] += 1
    evs = [prop for col, prop in EV.items() if not isna(r.get(col, ""))]
    for prop in evs:
        if (pl, prop, d) not in pairs:
            pairs.add((pl, prop, d))
            W(pl, P(prop), d)
            evc[prop] += 1
    if evs and (pl, "any", d) not in pairs:
        pairs.add((pl, "any", d))
        W(pl, P("associatedWithDisease"), d)
        evc["associatedWithDisease"] += 1
        if evs == ["associatedWithDiseaseByIngredientTrial"]:
            onlyweak["only_ingredient_trial"] += 1
rep["disease_nodes"] = len(dnodes)
rep.update({"edges_" + k: v for k, v in evc.items()})
rep.update(onlyweak)
W(P("associatedWithDisease"), TYPE, I(OWL + "ObjectProperty"))
W(P("associatedWithDisease"), LABEL, lit("associated with disease"))
W(P("associatedWithDisease"), I(RDFS + "domain"), P("Plant"))
W(P("associatedWithDisease"), I(RDFS + "range"), P("DiseaseConcept"))
W(
    P("associatedWithDisease"),
    I(RDFS + "comment"),
    lit(
        "CMAUP v2.0 plant–human disease association. An association, NOT a treatment claim; see the evidence sub-properties."
    ),
)
for col, prop in EV.items():
    W(P(prop), TYPE, I(OWL + "ObjectProperty"))
    W(P(prop), I(RDFS + "subPropertyOf"), P("associatedWithDisease"))
    W(P(prop), LABEL, lit(prop))
    W(
        P(prop),
        I(RDFS + "comment"),
        lit(
            "CMAUP column "
            + col
            + (
                "; weak: inherited from trials of constituent compounds"
                if "Ingredient" in col
                else ""
            )
        ),
    )
for k in ["icd11Code", "diseaseCategory"]:
    W(P(k), TYPE, I(OWL + "DatatypeProperty"))
    W(P(k), LABEL, lit(k))
    W(P(k), I(RDFS + "domain"), P("DiseaseConcept"))
out.close()
rep_d = dict(rep)
rep_d["top_flagged_compound_in_family"] = [[c, f, n] for (c, f), n in flag_ex.most_common(25)]
json.dump(rep_d, open(a.report, "w"), indent=1)
print(json.dumps(rep_d, indent=1))
print(f"{time.time()-t0:.0f}s")
