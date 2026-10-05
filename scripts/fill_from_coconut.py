#!/usr/bin/env python3
"""fill_from_coconut.py — fill SMILES / names / IUPAC and add real chemical classes from the COCONUT 2.0 SDF.
Streams the zipped SDF; joins on InChIKey; writes an N-Triples ADD file plus a list of subjects whose
InChIKey-only label is replaced.
  python3 fill_from_coconut.py poppy_phase2.nt ~/Downloads/coconut_sdf_2d-10-2026.zip add_coconut.nt label_replace.txt
Added per matched compound: hasSMILES (if missing), rdfs:label (if label was an InChIKey), hasIUPACName (if missing),
npClassifierPathway/Superclass/Class, classyfireSuperclass/Class/Subclass, coconutId + skos:exactMatch to COCONUT.
"""

import sys
import re
import zipfile
import io
import collections
import time

PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
I = lambda u: "<" + u + ">"
P = lambda l: I(PH + l)
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
SKOS = "http://www.w3.org/2004/02/skos/core#"
IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def lit(v):
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{v}"'


def na(v):
    return v is None or v.strip().lower() in ("", "nan", "none", "null", "n.a.")


nt, zp, out, lr = sys.argv[1:5]
t0 = time.time()
ik2s = {}
has = collections.defaultdict(set)
lab = {}
for line in open(nt):
    s, p, o = line.split(" ", 2)
    o = o[:-3]
    if p == P("hasInChIKey"):
        ik2s[o[1:-1]] = s
    elif p in (P("hasSMILES"), P("hasIUPACName")):
        has[s].add(p)
    elif p == LABEL and s.startswith(P("Chemical_")[:-1]):
        lab[s] = o[1 : o.rfind('"')]
print("compounds with InChIKey", len(ik2s), f"{time.time()-t0:.0f}s", flush=True)
WANT = {
    "identifier",
    "canonical_smiles",
    "standard_inchi_key",
    "name",
    "iupac_name",
    "np_classifier_pathway",
    "np_classifier_superclass",
    "np_classifier_class",
    "chemical_super_class",
    "chemical_class",
    "chemical_sub_class",
    "molecular_formula",
}
z = zipfile.ZipFile(zp)
f = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace")
fo = open(out, "w", buffering=1 << 22)
W = lambda s, p, o: fo.write(f"{s} {p} {o} .\n")
rec = {}
tag = None
n = 0
hit = 0
c = collections.Counter()
relabeled = set()
seen = set()
for line in f:
    if line.startswith(">"):
        m = re.match(r">\s*<([^>]+)>", line)
        tag = m.group(1) if m and m.group(1) in WANT else None
        continue
    if line.startswith("$$$$"):
        n += 1
        ik = rec.get("standard_inchi_key")
        s = ik2s.get(ik)
        if s and s not in seen:
            seen.add(s)
            hit += 1
            if not na(rec.get("canonical_smiles")) and P("hasSMILES") not in has[s]:
                W(s, P("hasSMILES"), lit(rec["canonical_smiles"]))
                c["smiles_filled"] += 1
            if not na(rec.get("iupac_name")) and P("hasIUPACName") not in has[s]:
                W(s, P("hasIUPACName"), lit(rec["iupac_name"]))
                c["iupac_filled"] += 1
            old = lab.get(s, "")
            if IK.match(old) or not old:
                new = (
                    rec.get("name")
                    if not na(rec.get("name")) and not IK.match(rec.get("name", ""))
                    else rec.get("iupac_name")
                )
                if not na(new):
                    W(s, LABEL, lit(new))
                    relabeled.add(s)
                    c["label_replaced"] += 1
                else:
                    cid = rec.get("identifier", "").split(".")[0]
                    fm = rec.get("molecular_formula", "")
                    if cid.startswith("CNP"):
                        W(s, LABEL, lit(f"{fm} ({cid})" if not na(fm) else cid))
                        relabeled.add(s)
                        c["label_fallback_formula_coconut_id"] += 1
                        W(
                            s,
                            P("labelIsPlaceholder"),
                            '"true"^^<http://www.w3.org/2001/XMLSchema#boolean>',
                        )
            for k, pr in [
                ("np_classifier_pathway", "npClassifierPathway"),
                ("np_classifier_superclass", "npClassifierSuperclass"),
                ("np_classifier_class", "npClassifierClass"),
                ("chemical_super_class", "classyfireSuperclass"),
                ("chemical_class", "classyfireClass"),
                ("chemical_sub_class", "classyfireSubclass"),
            ]:
                v = rec.get(k)
                if not na(v):
                    for x in v.split("|"):
                        if x.strip():
                            W(s, P(pr), lit(x.strip()))
                    c[pr] += 1
            cid = rec.get("identifier", "").split(".")[0]
            if cid.startswith("CNP"):
                W(s, P("coconutId"), lit(cid))
                W(
                    s,
                    I(SKOS + "exactMatch"),
                    I("https://coconut.naturalproducts.net/compounds/" + cid),
                )
        rec = {}
        tag = None
        if n % 200000 == 0:
            print(n, "records", hit, "hits", f"{time.time()-t0:.0f}s", flush=True)
        continue
    if tag and tag not in rec:
        v = line.rstrip("\n")
        if v:
            rec[tag] = v
    elif tag and line.strip() == "":
        tag = None
DP = "<http://www.w3.org/2002/07/owl#DatatypeProperty>"
for k, lab_ in [
    ("npClassifierPathway", "NPClassifier pathway (COCONUT 2.0)"),
    ("npClassifierSuperclass", "NPClassifier superclass (COCONUT 2.0)"),
    ("npClassifierClass", "NPClassifier class (COCONUT 2.0)"),
    ("classyfireSuperclass", "ClassyFire superclass (COCONUT 2.0)"),
    ("classyfireClass", "ClassyFire class (COCONUT 2.0)"),
    ("classyfireSubclass", "ClassyFire subclass (COCONUT 2.0)"),
    ("coconutId", "COCONUT identifier"),
]:
    W(P(k), TYPE, DP)
    W(P(k), LABEL, lit(lab_))
    W(P(k), "<http://www.w3.org/2000/01/rdf-schema#domain>", P("ChemicalConcept"))
fo.close()
open(lr, "w").write("".join(x + "\n" for x in relabeled))
print(f"SDF records {n}, matched {hit} of {len(ik2s)}; {dict(c)}; {time.time()-t0:.0f}s")
