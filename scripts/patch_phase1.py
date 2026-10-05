#!/usr/bin/env python3
"""
patch_phase1.py — Phase-1 correctness patch for the POPPy molecular ontology (N-Triples in/out).

Input : N-Triples produced by rdfxml2nt.py (materialized inverse edges already dropped).
Output: patched N-Triples + old->new IRI map + stats JSON. Two passes, low RAM.

  python3 patch_phase1.py collect all.nt state.pkl --taxdump data/raw/taxdump/nodes.dmp \
          --classification data/enrichment/plant_classification.tsv --junk data/enrichment/unmatched_junk_tags.tsv
  python3 patch_phase1.py apply   all.nt state.pkl out.nt --map iri_map.tsv --stats stats.json

Fixes (see claude/ontology-agent-readiness-audit.md):
  F1  drop compound->ClinicalTrial edges (ingredient trials propagated to every compound); keep plant->trial
  F2  compounds lose Plant/PlantConcept types; plants lose ChemicalConcept + chemical subclasses
  F3  heuristic classify_smiles classes -> literal phyto:heuristicPhytochemicalClass (rdf:type removed)
  F4  drop phyto:hasMolecularWeight (10.6% inconsistent with formula); keep RDKit phyto:mw
  F5  NA-like literals removed; InChIKeys removed from hasCommonName (moved to hasInChIKey if missing);
      one rdfs:label per compound = common name > IUPAC > InChIKey > SMILES; gene label '-' -> symbol
  F6  compound IRIs re-minted from InChIKey: Chemical_ik_<KEY> (same scheme as notebook Stage 16)
  F7  drop cmptx:none (INOH pathways with no id collapsed into one node)
  F8  remove non-plant organisms (NCBI lineage not under Viridiplantae 33090) and junk-tier names;
      flag unverifiable ones with phyto:taxonomyStatus
  F9  hasTaxon -> also skos:exactMatch obo:NCBITaxon_<id>
  F10 DrugCentral/ChEMBL action types: TherapeuticEffect_X -> MechanismOfAction_X via phyto:hasMechanismOfAction
  F11 legacy name-only targets: TargetedPathway_X (typed Pathway) -> phyto:ProteinTarget via phyto:targetsProtein
  F12 schema: single-class or owl:unionOf domains/ranges, declarations + labels for every predicate used,
      cmptx classes declared, deprecated heuristic classes, version info
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
XSD = "http://www.w3.org/2001/XMLSchema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
OBO = "http://purl.obolibrary.org/obo/"


def I(u):
    return "<" + u + ">"


TYPE = I(RDF + "type")
LABEL = I(RDFS + "label")
P = lambda l: I(PH + l)
HEUR = {
    "Carotenoid",
    "DietaryFiber",
    "Isoprenoid",
    "Phytosterol",
    "Polyphenol",
    "Polysaccharide",
    "Saponin",
    "Unknown",
}
CHEMTYPES = {P(x) for x in HEUR | {"ChemicalConcept"}}
PLANTTYPES = {P("Plant"), P("PlantConcept")}
NA = {"nan", "none", "null", "na", "n/a", "n.a.", "", "not available"}
IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
CHEM_PFX = "<" + PH + "Chemical_"
PLANT_PFX = ("<" + PH + "Plant_", "<" + PH + "Organism_")
NONE_PW = I(CX + "none")


def split(line):
    s, p, rest = line.split(" ", 2)
    return s, p, rest[:-3] if rest.endswith(" .\n") else rest.rstrip()[:-2].rstrip()


def litval(o):
    if not o.startswith('"'):
        return None
    return o[1 : o.rfind('"')]


def lit(v, dt=None):
    v = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{v}"^^<{dt}>' if dt else f'"{v}"'


def collect(a):
    t0 = time.time()
    chem_types = collections.defaultdict(set)
    ikey = {}
    cname = collections.defaultdict(list)
    iupac = {}
    smiles = {}
    trial_src = collections.defaultdict(set)
    plant_label = {}
    taxon = {}
    gene_symbol = {}
    declared = set()
    used = set()
    moa = set()
    tpath = set()
    for line in open(a.nt):
        s, p, o = split(line)
        used.add(p)
        if s.startswith(CHEM_PFX):
            if p == TYPE:
                chem_types[s].add(o)
            elif p == P("hasInChIKey"):
                ikey[s] = litval(o)
            elif p == P("hasCommonName"):
                cname[s].append(litval(o))
            elif p == P("hasIUPACName"):
                iupac[s] = litval(o)
            elif p == P("hasSMILES"):
                smiles.setdefault(s, litval(o))
        elif s.startswith(PLANT_PFX):
            if p == LABEL:
                plant_label[s] = litval(o)
            elif p == TYPE and o == P("Plant"):
                plant_label.setdefault(s, None)
            elif p == P("hasTaxon"):
                taxon[s] = litval(o)
        elif s.startswith("<" + CX) and p == I(CX + "geneSymbol"):
            gene_symbol[s] = litval(o)
        elif p == P("sourceColumn"):
            trial_src[s].add(litval(o))
        if p == TYPE and o in (
            I(OWL + "ObjectProperty"),
            I(OWL + "DatatypeProperty"),
            I(OWL + "AnnotationProperty"),
        ):
            declared.add(s)
        if p == P("hasTherapeuticEffect"):
            moa.add(o)
        if p == P("targetsPathway"):
            tpath.add(o)
    print(
        f"pass1 read {time.time()-t0:.0f}s chems={len(chem_types)} plants={len(plant_label)}",
        flush=True,
    )
    # --- IRI map for compounds
    iri_map = {}
    for s, k in ikey.items():
        if k and IK.match(k):
            iri_map[s] = P("Chemical_ik_" + k.replace("-", "_"))
    for s, names in cname.items():  # InChIKey stored only in hasCommonName
        if s in iri_map:
            continue
        for n in names:
            if n and IK.match(n):
                iri_map[s] = P("Chemical_ik_" + n.replace("-", "_"))
                ikey[s] = n
                break
    # --- best label per compound
    chem_label = {}
    for s in set(chem_types) | set(cname):
        good = [n for n in cname.get(s, []) if n and n.lower() not in NA and not IK.match(n)]
        iu = iupac.get(s)
        if good:
            chem_label[s] = min(good, key=len)
        elif iu and iu.lower() not in NA:
            chem_label[s] = iu
        elif ikey.get(s):
            chem_label[s] = ikey[s]
        elif smiles.get(s):
            chem_label[s] = smiles[s]
        else:
            chem_label[s] = s.rsplit("#", 1)[1][:-1].replace("Chemical_", "").replace("_", " ")
    # --- plant taxonomy
    parent = {}
    with open(a.taxdump) as f:
        for line in f:
            x = line.split("\t|\t", 2)
            parent[int(x[0])] = int(x[1])

    def is_plant(t):
        seen = 0
        while t in parent and seen < 100:
            if t == 33090:
                return True
            if t == 1:
                return False
            t = parent[t]
            seen += 1
        return None

    memo = {}

    def plant_memo(t):
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
        v = memo[t]
        for x in path:
            memo[x] = v
        return v

    plant_names = set()
    with open(a.taxdump.replace("nodes.dmp", "names.dmp")) as f:
        for line in f:
            x = line.split("\t|\t")
            if x[3].startswith("scientific name") or x[3].startswith("synonym"):
                if plant_memo(int(x[0])):
                    plant_names.add(" ".join(x[1].lower().split()[:2]))
    plant_genera = {n.split(" ")[0] for n in plant_names}
    print("NCBI plant names", len(plant_names), "genera", len(plant_genera), flush=True)

    def binom(lab):
        return " ".join((lab or "").replace("_", " ").lower().split()[:2])

    cls = {}
    for r in csv.DictReader(
        (l for l in open(a.classification) if not l.startswith("#")), delimiter="\t"
    ):
        cls[r["organism_id"]] = r["status"]
    junk = {
        r["organism_id"]
        for r in csv.DictReader((l for l in open(a.junk) if not l.startswith("#")), delimiter="\t")
        if r["tier"] == "junk"
    }
    remove = set()
    status = {}
    why = collections.Counter()
    added_labels = {}
    for s, lab in list(plant_label.items()):
        local = s.rsplit("#", 1)[1][:-1]
        tx = taxon.get(s)
        if not lab:
            lab = re.sub(r"^(Plant|Organism)_", "", local).replace("_", " ")
            plant_label[s] = lab
            added_labels[s] = lab
        bad = re.search(r"strain|engineered|unidentified|unknown|\[|\+", lab, re.I)
        if binom(lab) in plant_names and not bad:
            status[s] = "ncbi_plant_name"
            continue
        if (
            binom(lab).split(" ")[0] in plant_genera
            and len(binom(lab).split(" ")) == 2
            and local not in junk
            and not bad
        ):
            status[s] = "ncbi_plant_genus"
            continue
        v = is_plant(int(tx)) if tx and tx.isdigit() else None
        if v is True:
            status[s] = "ncbi_viridiplantae"
            continue
        if v is False:
            remove.add(s)
            why["ncbi_lineage_not_viridiplantae"] += 1
            continue
        if (
            bad
            or local in junk
            or re.search(r"\bunknown\b|\bsp\.\s*[A-Z0-9]|strain|\[|\d{3,}", lab or "", re.I)
        ):
            remove.add(s)
            why["junk_name"] += 1
            continue
        c = cls.get(local)
        if c == "nonplant":
            remove.add(s)
            why["classification_nonplant"] += 1
        elif c == "plant":
            status[s] = "ncbi_viridiplantae_by_name"
        else:
            status[s] = "unverified"
            why["unverified_kept"] += 1
    state = dict(
        iri_map=iri_map,
        chem_label=chem_label,
        ikey=ikey,
        remove=remove,
        status=status,
        taxon=taxon,
        trial_src=dict(trial_src),
        gene_symbol=gene_symbol,
        added_labels=added_labels,
        declared=declared,
        used=used,
        moa=moa,
        tpath=tpath,
        why=why,
    )
    pickle.dump(state, open(a.state, "wb"))
    print(
        f"compounds re-minted {len(iri_map)} (distinct {len(set(iri_map.values()))}); organisms removed {len(remove)} {dict(why)}; {time.time()-t0:.0f}s"
    )


# ---------------- schema (F12) ----------------
def schema_triples(used):
    T = []
    add = lambda s, p, o: T.append(f"{s} {p} {o} .\n")
    union_n = [0]

    def union(*classes):
        union_n[0] += 1
        b = f"_:u{union_n[0]}"
        add(b, TYPE, I(OWL + "Class"))
        nodes = [f"_:u{union_n[0]}l{i}" for i in range(len(classes))]
        add(b, I(OWL + "unionOf"), nodes[0])
        for i, c in enumerate(classes):
            add(nodes[i], I(RDF + "first"), c)
            add(nodes[i], I(RDF + "rest"), nodes[i + 1] if i + 1 < len(nodes) else I(RDF + "nil"))
        return b

    PLANT, CHEM = P("Plant"), P("ChemicalConcept")
    PorC = lambda: union(PLANT, CHEM)
    GENE, PW, DIS = I(CX + "Gene"), I(CX + "Pathway"), I(CX + "Disease")
    X = lambda t: I(XSD + t)
    OBJ = {  # prop: (domain, range, label, comment)
        "hasCompound": (
            PLANT,
            CHEM,
            "has compound",
            "Plant contains this natural-product compound (occurrence).",
        ),
        "hasClinicalStudy": (
            PLANT,
            P("ClinicalTrial"),
            "has clinical study",
            "Plant is studied in this clinical trial (CMAUP).",
        ),
        "hasPaper": (
            "PorC",
            P("ScientificPaper"),
            "has paper",
            "Literature reference for the plant or compound.",
        ),
        "targetsGene": (
            PLANT,
            GENE,
            "plant targets gene",
            "At least one compound of the plant targets this gene (CMAUP); mediating compound not recorded.",
        ),
        "hasIngredientClinicalStudy": (
            PLANT,
            P("ClinicalTrial"),
            "has ingredient clinical study",
            "A clinical trial of one of this plant's ingredients (CMAUP 'Association_by_Clinical_Trials_of_Plant_Ingredients'); NOT evidence for the plant itself, and the ingredient is not recorded.",
        ),
        "compoundTargetsGene": (
            CHEM,
            GENE,
            "compound targets gene",
            "Compound has a measured target association with this gene (CMAUP).",
        ),
        "targetsProtein": (
            CHEM,
            P("ProteinTarget"),
            "targets protein",
            "Compound targets this protein, named as in DrugCentral/ChEMBL; not yet mapped to a gene.",
        ),
        "hasMechanismOfAction": (
            CHEM,
            P("MechanismOfAction"),
            "has mechanism of action",
            "DrugCentral/ChEMBL action type.",
        ),
        "treatsDisease": (
            "PorC",
            DIS,
            "treats disease",
            "Asserted therapeutic use (not yet populated).",
        ),
        "hasAdverseEffect": (
            "PorC",
            P("AdverseEffect"),
            "has adverse effect",
            "Not yet populated.",
        ),
    }
    INV = {
        "hasCompound": "isDerivedFrom",
        "hasClinicalStudy": "isClinicalStudyFor",
        "hasPaper": "isPaperFor",
        "targetsGene": "geneTargetedBy",
        "treatsDisease": "diseaseTreatedBy",
        "hasAdverseEffect": "isAdverseEffectFor",
    }
    DAT = {
        "hasSMILES": (CHEM, X("string"), "SMILES"),
        "hasCanonicalSMILES": (CHEM, X("string"), "canonical SMILES (RDKit)"),
        "hasInChIKey": (CHEM, X("string"), "InChIKey"),
        "hasMolecularFormula": (CHEM, X("string"), "molecular formula"),
        "hasIUPACName": (CHEM, X("string"), "IUPAC name"),
        "hasCommonName": ("PorC", X("string"), "common name"),
        "commonName": (PLANT, X("string"), "vernacular name (plant)"),
        "hasMACCs": (CHEM, X("string"), "MACCS key bit string"),
        "hasATC": (CHEM, X("string"), "ATC code"),
        "hasDOI": (P("ScientificPaper"), X("string"), "DOI"),
        "hasNCTId": (P("ClinicalTrial"), X("string"), "ClinicalTrials.gov identifier"),
        "hasEvidenceText": (P("ClinicalTrial"), X("string"), "evidence text"),
        "sourceColumn": (P("ClinicalTrial"), X("string"), "CMAUP source column"),
        "hasGenus": (PLANT, X("string"), "genus"),
        "hasSpecies": (PLANT, X("string"), "specific epithet"),
        "hasTaxon": (PLANT, X("string"), "NCBI Taxonomy ID"),
        "scientificSynonym": (PLANT, X("string"), "scientific synonym"),
        "taxonomyStatus": (PLANT, X("string"), "taxonomy validation status"),
        "heuristicPhytochemicalClass": (
            CHEM,
            X("string"),
            "heuristic phytochemical class (unvalidated)",
        ),
        "hasValue": (None, X("string"), "value"),
        "hasDosage": (CHEM, None, "dosage"),
        "hasSource": (None, None, "source"),
        "hasTherapeuticClass": (CHEM, X("string"), "therapeutic class"),
    }
    for d in ["mw", "exact_mw", "logp", "tpsa", "qed", "fraction_csp3"]:
        DAT[d] = (CHEM, X("double"), d + " (RDKit)")
    for d in [
        "hbd",
        "hba",
        "rotatable_bonds",
        "aromatic_rings",
        "ring_count",
        "heavy_atoms",
        "heteroatoms",
        "formal_charge",
        "ro5_violations",
    ]:
        DAT[d] = (CHEM, X("double"), d.replace("_", " ") + " (RDKit)")
    for k, (dom, rng, lab, com) in OBJ.items():
        s = P(k)
        add(s, TYPE, I(OWL + "ObjectProperty"))
        add(s, LABEL, lit(lab))
        add(s, I(RDFS + "comment"), lit(com))
        add(s, I(RDFS + "domain"), PorC() if dom == "PorC" else dom)
        add(s, I(RDFS + "range"), rng)
        if k in INV:
            add(P(INV[k]), TYPE, I(OWL + "ObjectProperty"))
            add(P(INV[k]), I(OWL + "inverseOf"), s)
    for k, (dom, rng, lab) in DAT.items():
        s = P(k)
        add(s, TYPE, I(OWL + "DatatypeProperty"))
        add(s, LABEL, lit(lab))
        if dom:
            add(s, I(RDFS + "domain"), PorC() if dom == "PorC" else dom)
        if rng:
            add(s, I(RDFS + "range"), rng)
    for p, lab, dom, rng in [
        ("geneInPathway", "gene in pathway", GENE, PW),
        ("geneInteractsWithGene", "gene interacts with gene", GENE, GENE),
        ("geneAssociatedWithDisease", "gene associated with disease", GENE, DIS),
        ("diseaseSubtypeOf", "disease subtype of", DIS, DIS),
    ]:
        s = I(CX + p)
        add(s, TYPE, I(OWL + "ObjectProperty"))
        add(s, LABEL, lit(lab))
        add(s, I(RDFS + "domain"), dom)
        add(s, I(RDFS + "range"), rng)
    for p in [
        "geneSymbol",
        "typeOfGene",
        "commonName",
        "xrefNcbiGene",
        "xrefHGNC",
        "xrefEnsembl",
        "xrefOMIM",
        "pathwayId",
        "sourceDatabase",
        "xrefDiseaseOntology",
    ]:
        s = I(CX + p)
        add(s, TYPE, I(OWL + "DatatypeProperty"))
        add(s, LABEL, lit(p))
    for c, lab, sup in [
        (GENE, "Gene (ComptoxAI)", P("HumanConcept")),
        (PW, "Pathway (ComptoxAI)", P("HumanConcept")),
        (DIS, "Disease (Disease Ontology via DISEASES)", P("DiseaseConcept")),
        (P("MechanismOfAction"), "Mechanism of action", P("TherapeuticConcept")),
        (P("ProteinTarget"), "Protein target (name only)", P("HumanConcept")),
    ]:
        add(c, TYPE, I(OWL + "Class"))
        add(c, LABEL, lit(lab))
        add(c, I(RDFS + "subClassOf"), sup)
    add(P("Gene"), I(OWL + "equivalentClass"), GENE)
    add(P("Gene"), I(OWL + "deprecated"), lit("true", XSD + "boolean"))
    for h in HEUR:
        add(P(h), I(OWL + "deprecated"), lit("true", XSD + "boolean"))
        add(
            P(h),
            I(RDFS + "comment"),
            lit(
                "Deprecated: assigned by an unvalidated SMILES heuristic; see phyto:heuristicPhytochemicalClass."
            ),
        )
    ont = I(PH[:-1])
    add(ont, TYPE, I(OWL + "Ontology"))
    add(ont, I(OWL + "versionInfo"), lit("2026-10-01 phase-1 patch"))
    return T


SCHEMA_PREDS = {I(RDFS + "domain"), I(RDFS + "range"), I(OWL + "inverseOf")}


def apply(a):
    t0 = time.time()
    st = pickle.load(open(a.state, "rb"))
    tsrc = st["trial_src"]
    dash = set()
    M = st["iri_map"]
    rm = st["remove"]
    moa = st["moa"]
    tpath = st["tpath"]
    status = st["status"]
    out = open(a.out, "w", buffering=1 << 22)
    W = out.write
    c = collections.Counter()
    MOA_MAP = {
        o: P("MechanismOfAction_" + o.rsplit("#", 1)[1][len("TherapeuticEffect_") : -1])
        for o in moa
    }
    TP_MAP = {
        o: P("ProteinTarget_" + o.rsplit("#", 1)[1].replace("TargetedPathway_", "")[:-1])
        for o in tpath
    }
    REN = {**M, **MOA_MAP, **TP_MAP}
    phy_props_redeclared = {
        P(x)
        for x in [
            "hasCompound",
            "hasClinicalStudy",
            "hasPaper",
            "targetsGene",
            "compoundTargetsGene",
            "treatsDisease",
            "hasAdverseEffect",
            "targetsPathway",
            "hasTherapeuticEffect",
            "hasCommonName",
            "hasMolecularWeight",
            "isDerivedFrom",
            "isClinicalStudyFor",
            "isPaperFor",
            "geneTargetedBy",
            "diseaseTreatedBy",
            "isAdverseEffectFor",
            "pathwayTargetedBy",
            "therapeuticDueTo",
        ]
    }
    for line in open(a.nt):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        # drops
        if s == NONE_PW or o == NONE_PW:
            c["F7_none_pathway"] += 1
            continue
        if s in rm or o in rm:
            c["F8_nonplant_triples"] += 1
            continue
        if p in SCHEMA_PREDS and s in phy_props_redeclared:
            c["F12_old_domain_range"] += 1
            continue
        if p == P("hasMolecularWeight"):
            c["F4_hasMolecularWeight"] += 1
            continue
        if p == P("hasClinicalStudy") and s.startswith(CHEM_PFX):
            c["F1_compound_trial"] += 1
            continue
        if p == P("hasClinicalStudy") and "Association_by_Clinical_Trials_of_Plant" not in tsrc.get(
            o, ()
        ):
            p = P("hasIngredientClinicalStudy")
            c["F1_plant_trial_to_ingredient_trial"] += 1
        isch = s.startswith(CHEM_PFX)
        ispl = s.startswith(PLANT_PFX)
        if o.startswith('"'):
            v = litval(o)
            if v.strip().lower() in NA:
                c["F5_na_literal"] += 1
                continue
            if v == "-" and s.startswith("<" + CX):
                c["F5_dash_literal"] += 1
                if p == LABEL:
                    dash.add(s)
                continue
            if p == P("hasCommonName") and IK.match(v):
                c["F5_inchikey_in_commonname"] += 1
                continue
            if isch and p == LABEL:
                c["F5_old_compound_label"] += 1
                continue
        if p == TYPE:
            if isch and o in PLANTTYPES:
                c["F2_compound_plant_type"] += 1
                continue
            if isch and o in CHEMTYPES and o != P("ChemicalConcept"):
                W(
                    f"{REN.get(s,s)} {P('heuristicPhytochemicalClass')} {lit(o.rsplit('#',1)[1][:-1])} .\n"
                )
                c["F3_heuristic_type"] += 1
                continue
            if ispl and o in CHEMTYPES:
                c["F2_plant_chem_type"] += 1
                continue
            if s in MOA_MAP:
                o = P("MechanismOfAction")
                c["F10_moa_retyped"] += 1
            if s in TP_MAP and o == P("Pathway"):
                o = P("ProteinTarget")
                c["F11_target_retyped"] += 1
        if p == P("hasTherapeuticEffect") and o in MOA_MAP:
            p = P("hasMechanismOfAction")
        if p == P("targetsPathway"):
            p = P("targetsProtein")
        s2 = REN.get(s, s)
        o2 = REN.get(o, o)
        if s2 != s or o2 != o:
            c["F6_renamed_triples"] += 1
        W(f"{s2} {p} {o2} .\n")
        c["kept"] += 1
    # additions
    seen_lab = set()
    for s, lab in st["chem_label"].items():
        if s in rm or REN.get(s, s) in seen_lab:
            continue
        seen_lab.add(REN.get(s, s))
        W(f"{REN.get(s,s)} {LABEL} {lit(lab)} .\n")
        W(f"{REN.get(s,s)} {TYPE} {P('ChemicalConcept')} .\n")
        c["F5_compound_label_added"] += 1
    for s, k in st["ikey"].items():
        if k and IK.match(k):
            W(f"{REN.get(s,s)} {P('hasInChIKey')} {lit(k)} .\n")
    for s, sym in st["gene_symbol"].items():
        W(f"{s} {I(SKOS+'altLabel')} {lit(sym)} .\n")
        if s in dash:
            W(f"{s} {LABEL} {lit(sym)} .\n")
            c["F5_gene_label_from_symbol"] += 1
    for s, tx in st["taxon"].items():
        if s not in rm and tx and tx.isdigit():
            W(f"{s} {I(SKOS+'exactMatch')} {I(OBO+'NCBITaxon_'+tx)} .\n")
            c["F9_ncbitaxon_iri"] += 1
    for s, lab in st.get("added_labels", {}).items():
        if s not in rm:
            W(f"{s} {LABEL} {lit(lab)} .\n")
            c["plant_label_added"] += 1
    for s, v in status.items():
        if s not in rm:
            W(f"{s} {P('taxonomyStatus')} {lit(v)} .\n")
            W(f"{s} {TYPE} {P('Plant')} .\n")
    for t in schema_triples(st["used"]):
        W(t)
    out.close()
    with open(a.map, "w") as f:
        f.write("old_iri\tnew_iri\n")
        for k, v in REN.items():
            f.write(f"{k[1:-1]}\t{v[1:-1]}\n")
        for k in rm:
            f.write(f"{k[1:-1]}\tREMOVED_NONPLANT_OR_JUNK\n")
    c["organisms_removed"] = len(rm)
    c["why_removed"] = dict(st["why"])
    json.dump(c, open(a.stats, "w"), indent=1)
    print(json.dumps(c, indent=1))
    print(f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd")
    x = sp.add_parser("collect")
    x.add_argument("nt")
    x.add_argument("state")
    x.add_argument("--taxdump")
    x.add_argument("--classification")
    x.add_argument("--junk")
    y = sp.add_parser("apply")
    y.add_argument("nt")
    y.add_argument("state")
    y.add_argument("out")
    y.add_argument("--map")
    y.add_argument("--stats")
    a = ap.parse_args()
    collect(a) if a.cmd == "collect" else apply(a)
