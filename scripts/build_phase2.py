#!/usr/bin/env python3
"""
build_phase2.py — rebuild the plant–compound, clinical-trial and compound–target layers from source
files, with provenance, on top of the Phase-1 N-Triples.

  index  : python3 build_phase2.py index  phase1.nt idx.pkl --taxdump data/raw/taxdump/nodes.dmp
  build  : python3 build_phase2.py build  idx.pkl add.nt --cmaup-dir ~/Downloads --website poppy/website/data
                                          --duke poppy/data/raw --classification data/enrichment/plant_classification.tsv
  filter : python3 build_phase2.py filter phase1.nt idx.pkl base.nt
  then   : sort -u base.nt add.nt > phase2.nt ; finalize_nt.py

Sources -> edges
  CMAUP v2.0 Plant_Ingredient_Associations_allIngredients  -> hasCompound + hasCompoundPerCMAUP
  POPPy v1 website build (COCONUT DB + COCONUT 2.0 SDF)    -> hasCompound + hasCompoundPerCOCONUT
  Dr. Duke's FARMACY + FARMACY_NEW (actual occurrences)    -> hasCompound + hasCompoundPerDrDuke
  CMAUP Plant_Clinical_Trials_Associations                 -> plant-associated rows: plant hasClinicalStudy;
                                                              compound-associated rows: compound hasClinicalStudy
  CMAUP Ingredient_Target_Associations_ActivityValues      -> compoundTargetsGene + BioactivityMeasurement nodes
Removed from Phase 1: every hasCompound (incl. the activity-joined Dr. Duke links), hasClinicalStudy,
hasIngredientClinicalStudy, targetsGene (plant->gene, unexplained), compoundTargetsGene, old ClinicalTrial nodes.
plant->gene is now an owl:propertyChainAxiom (hasCompound o compoundTargetsGene).
"""

import os
import re
import csv
import json
import glob
import pickle
import hashlib
import argparse
import collections
import time

csv.field_size_limit(10**9)
PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
CX = "http://jdr.bio/ontologies/comptox.owl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
IDO = "http://identifiers.org/"
I = lambda u: "<" + u + ">"
P = lambda l: I(PH + l)
TYPE = I(RDF + "type")
LABEL = I(RDFS + "label")
IKRE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def lit(v, dt=None):
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return f'"{v}"^^<{dt}>' if dt else f'"{v}"'


def safe(x):
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.\-]", "_", x)).strip("_")


def nb(x):
    w = re.sub(r"[^a-z\- ]", " ", (x or "").lower()).split()
    return " ".join(w[:2]) if len(w) >= 2 else ""


def nname(x):
    return re.sub(r"[^A-Z0-9]", "", (x or "").upper())


def cik(ik):
    return P("Chemical_ik_" + ik.replace("-", "_"))


NA = {"", "n.a.", "na", "nan", "none", "null"}


def isna(v):
    return v is None or str(v).strip().lower() in NA


def index(a):
    t0 = time.time()
    T = TYPE
    L = LABEL
    plant_lab = {}
    chem = {}
    chem_label = {}
    chem_has = collections.defaultdict(set)
    genes = set()
    ptarget = {}
    for line in open(a.nt):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if p == T:
            if o == P("Plant"):
                plant_lab.setdefault(s, None)
            elif o == P("ChemicalConcept"):
                chem[s] = 1
            elif o == I(CX + "Gene"):
                genes.add(s)
            elif o == P("ProteinTarget"):
                ptarget.setdefault(s, None)
        elif p == L:
            v = o[1 : o.rfind('"')]
            if s.startswith(P("Plant_")[:-1]) or s.startswith(P("Organism_")[:-1]):
                plant_lab[s] = v
            elif s.startswith(P("Chemical_")[:-1]):
                chem_label[s] = v
            elif s.startswith(P("ProteinTarget_")[:-1]):
                ptarget[s] = v
        elif s.startswith(P("Chemical_")[:-1]) and p in (
            P("hasSMILES"),
            P("hasMolecularFormula"),
            P("hasInChIKey"),
        ):
            chem_has[s].add(p)
    parent = {}
    for line in open(a.taxdump):
        x = line.split("\t|\t", 2)
        parent[int(x[0])] = int(x[1])
    memo = {}

    def isp(t):
        path = []
        while t not in memo:
            if t == 33090:
                memo[t] = True
                break
            if t == 1 or t not in parent:
                memo[t] = False
                break
            path.append(t)
            t = parent[t]
        for x in path:
            memo[x] = memo[t]
        return memo[t]

    plant_names = {}
    for line in open(a.taxdump.replace("nodes.dmp", "names.dmp")):
        x = line.split("\t|\t")
        if (x[3].startswith("scientific name") or x[3].startswith("synonym")) and isp(int(x[0])):
            k = nb(x[1])
            if k:
                plant_names.setdefault(k, int(x[0]))
    pickle.dump(
        dict(
            plant_lab=plant_lab,
            chem=set(chem),
            chem_label=chem_label,
            chem_has=dict(chem_has),
            genes=genes,
            ptarget=ptarget,
            plant_names=plant_names,
        ),
        open(a.idx, "wb"),
    )
    print(
        f"index: plants {len(plant_lab)} chems {len(chem)} genes {len(genes)} ncbi plant binomials {len(plant_names)} {time.time()-t0:.0f}s"
    )


def build(a):
    t0 = time.time()
    X = pickle.load(open(a.idx, "rb"))
    out = open(a.out, "w", buffering=1 << 22)
    c = collections.Counter()

    def W(s, p, o):
        out.write(f"{s} {p} {o} .\n")

    # ---------- plants
    bin2p = {}
    for s, lab in X["plant_lab"].items():
        if lab:
            bin2p.setdefault(nb(lab), s)
    new_plants = {}

    def plant(name, taxid=None, pid=None):
        if pid and pid in X["plant_lab"]:
            return pid
        k = nb(name)
        if not k:
            return None
        if k in bin2p:
            return bin2p[k]
        if k not in X["plant_names"]:
            c["plant_unresolved_not_ncbi_plant"] += 1
            return None
        g, sp = k.split(" ")
        s = P("Plant_" + safe(g.capitalize() + "_" + sp))
        lab = g.capitalize() + " " + sp
        bin2p[k] = s
        new_plants[s] = (lab, taxid or X["plant_names"][k])
        return s

    # ---------- compounds
    known = set(X["chem"])
    new_chem = {}
    label_override = {}

    def compound(ik, name=None, smiles=None, formula=None, iupac=None, xrefs=()):
        if not ik or not IKRE.match(ik):
            return None
        s = cik(ik)
        has = X["chem_has"].setdefault(s, set())
        if s not in known and s not in new_chem:
            new_chem[s] = dict(ik=ik)
            c["compound_new"] += 1
        d = new_chem.get(s)
        good = name if (not isna(name) and not IKRE.match(name) and name != formula) else None
        if d is not None:
            if good and "name" not in d:
                d["name"] = good
            if smiles and "smiles" not in d:
                d["smiles"] = smiles
            if formula and "formula" not in d:
                d["formula"] = formula
            if not isna(iupac) and "iupac" not in d:
                d["iupac"] = iupac
            d.setdefault("xrefs", set()).update(xrefs)
        else:
            old = X["chem_label"].get(s, "")
            if good and (not old or IKRE.match(old)) and s not in label_override:
                label_override[s] = good
            if smiles and P("hasSMILES") not in has:
                W(s, P("hasSMILES"), lit(smiles))
                has.add(P("hasSMILES"))
            if formula and P("hasMolecularFormula") not in has:
                W(s, P("hasMolecularFormula"), lit(formula))
                has.add(P("hasMolecularFormula"))
            for x in xrefs:
                W(s, I(SKOS + "exactMatch"), I(x))
        return s

    # CMAUP ingredients
    D = a.cmaup_dir.rstrip("/") + "/"
    ing = {}
    for r in csv.DictReader(
        open(D + "CMAUPv2.0_download_Ingredients_All.txt", encoding="utf-8", errors="replace"),
        delimiter="\t",
    ):
        x = []
        if not isna(r["pubchem_cid"]):
            x.append(IDO + "pubchem.compound/" + r["pubchem_cid"])
        if not isna(r["chembl_id"]):
            x.append(IDO + "chembl.compound/" + r["chembl_id"])
        ing[r["np_id"]] = compound(
            r["InChIKey"], r["pref_name"], r["SMILES"] or None, None, r["iupac_name"], x
        )
    print("cmaup ingredients", len(ing), f"{time.time()-t0:.0f}s", flush=True)
    # website (POPPy v1 build) compounds
    W_ = a.website.rstrip("/") + "/"
    wc = {}
    for f in glob.glob(W_ + "compounds/*.json"):
        for k, v in json.load(open(f)).items():
            wc[k] = compound(v.get("inchikey"), v.get("name"), None, v.get("formula") or None)
    print("website compounds", len(wc), f"{time.time()-t0:.0f}s", flush=True)
    # name index for Dr. Duke mapping (unique normalized name -> compound)
    name_ix = collections.defaultdict(set)
    for r in csv.DictReader(
        open(D + "CMAUPv2.0_download_Ingredients_All.txt", encoding="utf-8", errors="replace"),
        delimiter="\t",
    ):
        if not isna(r["pref_name"]) and ing.get(r["np_id"]):
            name_ix[nname(r["pref_name"])].add(ing[r["np_id"]])
    for s, lab in list(X["chem_label"].items()) + list(label_override.items()):
        if "Chemical_ik_" in s and lab and not IKRE.match(lab):
            name_ix[nname(lab)].add(s)
    for s, d in new_chem.items():
        if d.get("name"):
            name_ix[nname(d["name"])].add(s)
    # ---------- occurrences
    occ = collections.defaultdict(set)  # (plant, compound) -> sources
    assoc = (
        open(D + "CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients (2).txt")
        if os.path.exists(
            D + "CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients (2).txt"
        )
        else open(
            glob.glob(D + "CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients*.txt")[0]
        )
    )
    cpl = {
        r["Plant_ID"]: r
        for r in csv.DictReader(
            open(D + "CMAUPv2.0_download_Plants.txt", encoding="utf-8", errors="replace"),
            delimiter="\t",
        )
    }
    npo2p = {
        k: plant(
            r["Species_Name"] if not isna(r["Species_Name"]) else r["Plant_Name"],
            int(r["Species_Tax_ID"]) if r["Species_Tax_ID"].isdigit() else None,
        )
        for k, r in cpl.items()
    }
    for line in assoc:
        x = line.rstrip("\n").split("\t")
        if len(x) < 2:
            continue
        pl, cm = npo2p.get(x[0]), ing.get(x[1])
        if pl and cm:
            occ[(pl, cm)].add("CMAUP")
        else:
            c["cmaup_assoc_unresolved"] += 1
    print("cmaup occurrences", len(occ), f"{time.time()-t0:.0f}s", flush=True)
    cls = {}
    for r in csv.DictReader(
        (l for l in open(a.classification) if not l.startswith("#")), delimiter="\t"
    ):
        cls[r["organism_id"]] = r["status"]
    wp = {x["id"]: x["name"] for x in json.load(open(W_ + "plants_index.json"))}
    wmap = {}
    for pid, name in wp.items():
        s = plant(name, None, P(pid))
        if s is None and cls.get(pid) == "plant":
            s = plant(name)
        wmap[pid] = s
    for f in glob.glob(W_ + "plant_edges/*.json"):
        for pid, cids in json.load(open(f)).items():
            pl = wmap.get(pid)
            if not pl:
                c["website_plant_unresolved"] += len(cids)
                continue
            for cid in cids:
                cm = wc.get(cid)
                if cm:
                    occ[(pl, cm)].add("COCONUT")
    print("after website occurrences", len(occ), f"{time.time()-t0:.0f}s", flush=True)
    R = a.duke.rstrip("/") + "/"
    tax = {r["FNFNUM"]: r for r in csv.DictReader(open(R + "FNFTAX.csv", encoding="latin-1"))}
    chemid = {
        r["CHEM"]: r["CHEMID"]
        for r in csv.DictReader(open(R + "CHEMICALS.csv", encoding="latin-1"))
    }
    duke_new = {}

    def duke_compound(chem, cid):
        cid = cid or chemid.get(chem) or nname(chem)
        hits = name_ix.get(nname(chem)) or name_ix.get(nname(cid))
        if hits and len(hits) == 1:
            c["duke_name_mapped_to_structure"] += 1
            return next(iter(hits)), cid
        s = P("Chemical_" + safe(cid))
        if s not in known and s not in duke_new:
            duke_new[s] = chem
        return s, cid

    duke_map = {}
    for fn in ["FARMACY.csv", "FARMACY_NEW.csv"]:
        for r in csv.DictReader(open(R + fn, encoding="latin-1")):
            t = tax.get(r["FNFNUM"])
            if not t:
                continue
            pl = plant(t["TAXON"] or (t["GENUS"] + " " + t["SPECIES"]))
            if not pl:
                c["duke_plant_unresolved"] += 1
                continue
            cm, cid = duke_compound(r["CHEM"], r.get("CHEMID"))
            duke_map[P("Chemical_" + safe(cid))] = cm
            occ[(pl, cm)].add("DrDuke")
    print("after Duke", len(occ), f"{time.time()-t0:.0f}s", flush=True)
    src_prop = {
        "CMAUP": P("hasCompoundPerCMAUP"),
        "COCONUT": P("hasCompoundPerCOCONUT"),
        "DrDuke": P("hasCompoundPerDrDuke"),
    }
    for (pl, cm), srcs in occ.items():
        W(pl, P("hasCompound"), cm)
        for s_ in srcs:
            W(pl, src_prop[s_], cm)
            c["occ_" + s_] += 1
        c["occ_n_sources_%d" % len(srcs)] += 1
    c["occurrences"] = len(occ)
    # ---------- clinical trials
    tseen = set()
    tpairs = set()
    for r in csv.DictReader(
        open(
            glob.glob(D + "CMAUPv2.0_download_Plant_Clinical_Trials_Associations*.txt")[0],
            encoding="utf-8",
            errors="replace",
        ),
        delimiter="\t",
    ):
        nct = r["NCT_ID"].strip()
        if not re.match(r"^NCT\d{8}$", nct):
            continue
        t = P("ClinicalTrial_CT_" + nct)
        if nct not in tseen:
            tseen.add(nct)
            W(t, TYPE, P("ClinicalTrial"))
            W(t, TYPE, I(OWL + "NamedIndividual"))
            W(t, P("hasNCTId"), lit(nct))
            W(t, LABEL, lit(r["Title"] or nct))
            W(t, I(SKOS + "exactMatch"), I("https://clinicaltrials.gov/study/" + nct))
            if not isna(r["Phase"]):
                W(t, P("trialPhase"), lit(r["Phase"]))
        if not isna(r["Disease/Condition"]) and (nct, "cond", r["Disease/Condition"]) not in tpairs:
            tpairs.add((nct, "cond", r["Disease/Condition"]))
            W(t, P("trialCondition"), lit(r["Disease/Condition"]))
        if r["Associated_by plant_or_compound"] == "compound":
            m = re.search(r"\((NPC\d+)\)", r["Form_in_Clinical_Use"])
            cm = ing.get(m.group(1)) if m else None
            if cm and (cm, t) not in tpairs:
                tpairs.add((cm, t))
                W(cm, P("hasClinicalStudy"), t)
                c["trial_compound_edges"] += 1
            elif not cm:
                c["trial_compound_unresolved"] += 1
        else:
            pl = npo2p.get(r["Plant_ID"])
            if pl and (pl, t) not in tpairs:
                tpairs.add((pl, t))
                W(pl, P("hasClinicalStudy"), t)
                c["trial_plant_edges"] += 1
            if not isna(r["Form_in_Clinical_Use"]):
                W(t, P("interventionDescription"), lit(r["Form_in_Clinical_Use"]))
    c["trials"] = len(tseen)
    # ---------- targets + bioactivity
    tg = {
        r["Target_ID"]: r
        for r in csv.DictReader(
            open(D + "CMAUPv2.0_download_Targets.txt", encoding="utf-8", errors="replace"),
            delimiter="\t",
        )
    }
    tgene = {}
    pname2gene = {}
    for k, r in tg.items():
        g = I(CX + r["Gene_Symbol"].lower())
        if g in X["genes"]:
            tgene[k] = g
            pname2gene[nname(r["Protein_Name"])] = g
            if not isna(r["Uniprot_ID"]):
                W(g, I(SKOS + "exactMatch"), I(IDO + "uniprot/" + r["Uniprot_ID"]))
            if not isna(r["ChEMBL_ID"]):
                W(g, I(SKOS + "exactMatch"), I(IDO + "chembl.target/" + r["ChEMBL_ID"]))
            W(g, P("targetClass"), lit(r["Target_Class_Level1"]))
    ctg = set()
    for r in csv.DictReader(
        open(
            D + "CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt",
            encoding="utf-8",
            errors="replace",
        ),
        delimiter="\t",
    ):
        cm = ing.get(r["Ingredient_ID"])
        g = tgene.get(r["Target_ID"])
        if not (cm and g):
            c["activity_unresolved"] += 1
            continue
        if (cm, g) not in ctg:
            ctg.add((cm, g))
            W(cm, P("compoundTargetsGene"), g)
        h = hashlib.sha1("|".join(r[k] for k in r).encode()).hexdigest()[:16]
        act = P("Bioactivity_" + h)
        W(act, TYPE, P("BioactivityMeasurement"))
        W(act, P("activityCompound"), cm)
        W(act, P("activityTarget"), g)
        W(act, P("activityType"), lit(r["Activity_Type"]))
        if not isna(r["Activity_Relationship"]):
            W(act, P("activityRelation"), lit(r["Activity_Relationship"]))
        try:
            W(act, P("activityValue"), lit(float(r["Activity_Value"]), XSD + "double"))
        except ValueError:
            if not isna(r["Activity_Value"]):
                W(act, P("activityValueText"), lit(r["Activity_Value"]))
        if not isna(r["Activity_Unit"]):
            W(act, P("activityUnit"), lit(r["Activity_Unit"]))
        W(act, P("assertedBy"), lit("CMAUP v2.0"))
        # CMAUP labels many ChEMBL assay IDs as "PMID" (values < 5M, one per measurement);
        # only treat >= 5,000,000 as PubMed IDs
        if (
            r["Reference_ID_Type"] == "PMID"
            and r["Reference_ID"].isdigit()
            and int(r["Reference_ID"]) >= 5_000_000
        ):
            W(act, P("hasReference"), I(IDO + "pubmed/" + r["Reference_ID"]))
        elif not isna(r["Reference_ID"]):
            W(act, P("hasReferenceText"), lit(r["Reference_ID_Type"] + ":" + r["Reference_ID"]))
        c["bioactivities"] += 1
    c["compound_gene_pairs"] = len(ctg)
    for s, lab in X["ptarget"].items():
        g = pname2gene.get(nname(lab or s.rsplit("#", 1)[1].replace("ProteinTarget_", "")[:-1]))
        if g:
            W(s, I(SKOS + "exactMatch"), g)
            c["protein_target_mapped_to_gene"] += 1
    # ---------- emit new entities
    for s, (lab, tx) in new_plants.items():
        W(s, TYPE, P("Plant"))
        W(s, TYPE, I(OWL + "NamedIndividual"))
        W(s, LABEL, lit(lab))
        W(s, P("taxonomyStatus"), lit("ncbi_plant_name"))
        if tx:
            W(s, P("hasTaxon"), lit(tx))
            W(s, I(SKOS + "exactMatch"), I("http://purl.obolibrary.org/obo/NCBITaxon_" + str(tx)))
    c["plants_new"] = len(new_plants)
    for s, d in new_chem.items():
        W(s, TYPE, P("ChemicalConcept"))
        W(s, TYPE, I(OWL + "NamedIndividual"))
        W(s, P("hasInChIKey"), lit(d["ik"]))
        W(s, LABEL, lit(d.get("name") or d.get("iupac") or d["ik"]))
        if d.get("smiles"):
            W(s, P("hasSMILES"), lit(d["smiles"]))
        if d.get("formula"):
            W(s, P("hasMolecularFormula"), lit(d["formula"]))
        if d.get("iupac"):
            W(s, P("hasIUPACName"), lit(d["iupac"]))
        for x in d.get("xrefs", ()):
            W(s, I(SKOS + "exactMatch"), I(x))
    for s, chem in duke_new.items():
        W(s, TYPE, P("ChemicalConcept"))
        W(s, TYPE, I(OWL + "NamedIndividual"))
        W(s, LABEL, lit(chem.title()))
        W(s, P("hasCommonName"), lit(chem))
    c["duke_name_only_new"] = len(duke_new)
    for s, lab in label_override.items():
        W(s, LABEL, lit(lab))
    c["labels_improved"] = len(label_override)
    # ---------- schema additions
    for k, lab, com in [
        (
            "hasCompoundPerCMAUP",
            "has compound (CMAUP v2.0)",
            "Occurrence reported by CMAUP v2.0 Plant_Ingredient_Associations_allIngredients.",
        ),
        (
            "hasCompoundPerCOCONUT",
            "has compound (COCONUT)",
            "Occurrence from the POPPy v1 build: COCONUT database + COCONUT 2.0 SDF organism links (may include a small number of v1 CMAUP links).",
        ),
        (
            "hasCompoundPerDrDuke",
            "has compound (Dr. Duke's)",
            "Occurrence reported in Dr. Duke's Phytochemical and Ethnobotanical Databases FARMACY tables.",
        ),
    ]:
        s = P(k)
        W(s, TYPE, I(OWL + "ObjectProperty"))
        W(s, I(RDFS + "subPropertyOf"), P("hasCompound"))
        W(s, LABEL, lit(lab))
        W(s, I(RDFS + "comment"), lit(com))
        W(s, I(RDFS + "domain"), P("Plant"))
        W(s, I(RDFS + "range"), P("ChemicalConcept"))
    s = P("hasClinicalStudy")
    W(s, I(RDFS + "domain"), "_:hcsU")
    W("_:hcsU", TYPE, I(OWL + "Class"))
    W("_:hcsU", I(OWL + "unionOf"), "_:hcs1")
    W("_:hcs1", I(RDF + "first"), P("Plant"))
    W("_:hcs1", I(RDF + "rest"), "_:hcs2")
    W("_:hcs2", I(RDF + "first"), P("ChemicalConcept"))
    W("_:hcs2", I(RDF + "rest"), I(RDF + "nil"))
    W(
        s,
        I(RDFS + "comment"),
        lit(
            "Plant: CMAUP trial associated with the plant itself. Compound: the compound is the trial intervention (CMAUP 'compound' association). A plant is NOT linked to trials of its constituent compounds; follow hasCompound/hasClinicalStudy for that."
        ),
    )
    W(P("targetsGene"), I(OWL + "propertyChainAxiom"), "_:tg1")
    W("_:tg1", I(RDF + "first"), P("hasCompound"))
    W("_:tg1", I(RDF + "rest"), "_:tg2")
    W("_:tg2", I(RDF + "first"), P("compoundTargetsGene"))
    W("_:tg2", I(RDF + "rest"), I(RDF + "nil"))
    W(
        P("targetsGene"),
        I(RDFS + "comment"),
        lit("Inferred only: plant hasCompound C and C compoundTargetsGene G. Not materialized."),
    )
    W(P("BioactivityMeasurement"), TYPE, I(OWL + "Class"))
    W(P("BioactivityMeasurement"), LABEL, lit("Bioactivity measurement"))
    W(P("BioactivityMeasurement"), I(RDFS + "subClassOf"), P("ResearchConcept"))
    for k, rng in [
        ("activityCompound", P("ChemicalConcept")),
        ("activityTarget", I(CX + "Gene")),
        ("hasReference", None),
    ]:
        W(P(k), TYPE, I(OWL + "ObjectProperty"))
        W(P(k), I(RDFS + "domain"), P("BioactivityMeasurement"))
        W(P(k), LABEL, lit(k))
        if rng:
            W(P(k), I(RDFS + "range"), rng)
    for k, dt in [
        ("activityType", "string"),
        ("activityRelation", "string"),
        ("activityValue", "double"),
        ("activityValueText", "string"),
        ("activityUnit", "string"),
        ("assertedBy", "string"),
        ("hasReferenceText", "string"),
        ("trialPhase", "string"),
        ("trialCondition", "string"),
        ("interventionDescription", "string"),
        ("targetClass", "string"),
    ]:
        W(P(k), TYPE, I(OWL + "DatatypeProperty"))
        W(P(k), LABEL, lit(k))
        W(P(k), I(RDFS + "range"), I(XSD + dt))
    out.close()
    pickle.dump(
        dict(
            label_override=set(label_override),
            duke_map={k: v for k, v in duke_map.items() if k != v},
        ),
        open(a.out + ".drop.pkl", "wb"),
    )
    print(json.dumps(c, indent=1))
    print(f"{time.time()-t0:.0f}s")


DROP_P = {
    P(x)
    for x in [
        "hasCompound",
        "hasClinicalStudy",
        "hasIngredientClinicalStudy",
        "targetsGene",
        "compoundTargetsGene",
    ]
}


def filt(a):
    d = pickle.load(open(a.add + ".drop.pkl", "rb"))
    lo = d["label_override"]
    dm = d["duke_map"]
    out = open(a.out, "w", buffering=1 << 22)
    c = collections.Counter()
    CT = P("ClinicalTrial_")[:-1]
    HCS = P("hasClinicalStudy")
    HICS = P("hasIngredientClinicalStudy")
    for line in open(a.nt):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if p in DROP_P:
            c["dropped_edge " + p.rsplit("#", 1)[1][:-1]] += 1
            continue
        if s.startswith(CT):
            c["dropped_old_trial_triple"] += 1
            continue
        if (s == HCS and p in (I(RDFS + "domain"), I(RDFS + "comment"))) or s == HICS:
            c["dropped_schema"] += 1
            continue
        if p == LABEL and s in lo:
            c["label_replaced"] += 1
            continue
        s2 = dm.get(s, s)
        o2 = dm.get(o, o)
        if s2 != s and p in (LABEL, TYPE, I(OWL + "NamedIndividual"), P("hasCommonName")):
            c["duke_node_merged_triple"] += 1
            continue
        if s2 != s or o2 != o:
            c["duke_renamed"] += 1
        out.write(f"{s2} {p} {o2} .\n")
    out.close()
    print(json.dumps(c, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd")
    x = sp.add_parser("index")
    x.add_argument("nt")
    x.add_argument("idx")
    x.add_argument("--taxdump")
    y = sp.add_parser("build")
    y.add_argument("idx")
    y.add_argument("out")
    y.add_argument("--cmaup-dir")
    y.add_argument("--website")
    y.add_argument("--duke")
    y.add_argument("--classification")
    z = sp.add_parser("filter")
    z.add_argument("nt")
    z.add_argument("add")
    z.add_argument("out")
    a = ap.parse_args()
    {"index": index, "build": build, "filter": filt}[a.cmd](a)
