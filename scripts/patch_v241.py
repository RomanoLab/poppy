"""patch_v241.py - schema-only fixes from ROBOT/HermiT validation of v2.4 -> v2.4.1.
usage: patch_v241.py in.nt out.nt"""

import gzip
import re
import sys

OPEN = lambda f: (
    gzip.open(f, "rt", encoding="utf-8") if f.endswith(".gz") else open(f, encoding="utf-8")
)
P = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
C = "http://jdr.bio/ontologies/comptox.owl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
XSD = "http://www.w3.org/2001/XMLSchema#"
IAO_REPL = "http://purl.obolibrary.org/obo/IAO_0100001"
ONT = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies>"
I = lambda u: f"<{u}>"
L = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
T = lambda s, p, o: f"{s} {p} {o} .\n"
TYPE, LABEL, COMMENT = I(RDF + "type"), I(RDFS + "label"), I(RDFS + "comment")

# 1) whole subjects to drop: unused properties with contradictory domain/range; orphan OWL1 DataRange lists
DROP_S = {I(P + "interactsWith"), I(P + "hasInteractionsWith")} | {
    "_:N5bc5f320437d40f39a473532ff5064c4",
    "_:N8a61b5c57d3446c3b287d6b4c22ad3a7",
    "_:Nfbc9b90265464fa8aeb91d22a5dce9ac",
    "_:Nc3705f88736342c2950e7434e1da9188",
    "_:Nd124f305dc514c429ae1cc1af91f0a6d",
    "_:N79478442c5e04b11aa2e5b0ffaaa7e2e",
}
# 2) exact triples to drop
DROP_T = {
    T(
        I(P + "commonName"), TYPE, I(OWL + "AnnotationProperty")
    ),  # illegal punning (data + annotation)
    T(I(P + "scientificSynonym"), TYPE, I(OWL + "AnnotationProperty")),
    T("_:u4l1", I(RDF + "rest"), I(RDF + "nil")),  # extend hasCommonName domain
    T(ONT, I(OWL + "versionInfo"), L("POPPy v2.4 (2026-10-05)")),
    T(
        I(P + "TherapeuticEffect"), LABEL, "_:N8852e73740e14518b16014cdf6b063be"
    ),  # empty blank-node label
    T(
        I(P + "commonName"), I(RDFS + "range"), I(XSD + "string")
    ),  # 19,930 values are language-tagged
}
INT_PROPS = "aromatic_rings formal_charge hba hbd heavy_atoms heteroatoms ring_count ro5_violations rotatable_bonds".split()
for (
    x
) in (
    INT_PROPS
):  # values are xsd:integer; OWL 2 integer and double value spaces are disjoint -> inconsistency
    DROP_T.add(T(I(P + x), I(RDFS + "range"), I(XSD + "double")))
DEPRECATED = {
    I(P + x)
    for x in "Carotenoid DietaryFiber Gene Isoprenoid Phytosterol Polyphenol Polysaccharide Saponin Unknown".split()
}
DEP_AXIOMS = {I(RDFS + "subClassOf"), I(OWL + "equivalentClass")}
HPC = I(P + "heuristicPhytochemicalClass")
NCC = I(P + "NonCompoundConstituent")

add = []
A = lambda s, p, o: add.append(T(s, p, o))
# header
A(ONT, I(OWL + "versionInfo"), L("POPPy v2.4.1 (2026-10-05)"))
A(ONT, I(DCT + "title"), L("POPPy — Phyto-Ontology Platform for Pharmacology"))
A(
    ONT,
    I(DCT + "description"),
    L(
        "OWL ontology and knowledge graph linking medicinal plants to their chemical constituents, gene and protein "
        "targets, pathways, diseases, clinical trials, bioactivity measurements and literature, integrated from CMAUP 2.0, "
        "COCONUT 2.0, Dr. Duke's Phytochemical and Ethnobotanical Databases, ComptoxAI, the DISEASES resource (Disease "
        "Ontology), NCBI Taxonomy and ClinicalTrials.gov. Plant-disease links are associations, not treatment claims."
    ),
)
A(ONT, I(DCT + "license"), I("https://creativecommons.org/licenses/by-nc/4.0/"))
A(
    ONT,
    COMMENT,
    L(
        "v2.4.1: schema-only fixes from ROBOT validate-profile/report and HermiT; data unchanged except "
        'removal of 46 heuristicPhytochemicalClass "Unknown" values on non-compound constituents.'
    ),
)
# annotation property declarations
for ap, lab in [
    (DCT + "title", "title"),
    (DCT + "description", "description"),
    (DCT + "license", "license"),
    (SKOS + "altLabel", "alternative label"),
    (SKOS + "exactMatch", "exact match"),
    (SKOS + "closeMatch", "close match"),
    (IAO_REPL, "term replaced by"),
]:
    A(I(ap), TYPE, I(OWL + "AnnotationProperty"))
    A(I(ap), LABEL, L(lab))
for x in INT_PROPS:
    A(I(P + x), I(RDFS + "range"), I(XSD + "integer"))
A(I(P + "commonName"), I(RDFS + "range"), I(RDFS + "Literal"))
# undeclared data property
lip = I(P + "labelIsPlaceholder")
A(lip, TYPE, I(OWL + "DatatypeProperty"))
A(lip, LABEL, L("label is placeholder"))
A(lip, I(RDFS + "range"), I(XSD + "boolean"))
A(
    lip,
    COMMENT,
    L(
        "true when the compound's rdfs:label is a generated placeholder (no trade, common or IUPAC name found)."
    ),
)
# hasCommonName domain: Plant or ChemicalConcept or NonCompoundConstituent
A("_:u4l1", I(RDF + "rest"), "_:u4l2")
A("_:u4l2", I(RDF + "first"), NCC)
A("_:u4l2", I(RDF + "rest"), I(RDF + "nil"))
# hasReportedConstituent domain/range (verified against data by drcheck.py)
hrc = I(P + "hasReportedConstituent")
A(hrc, I(RDFS + "domain"), I(P + "Plant"))
A(hrc, I(RDFS + "range"), NCC)
# deprecated class replacement
A(I(P + "Gene"), I(IAO_REPL), I(C + "Gene"))
# missing labels
for t, lab in [
    ("AdverseEffect", "adverse effect"),
    ("ClinicalTrial", "clinical trial"),
    ("DiseaseConcept", "disease concept"),
    ("DrugDrugInteractions", "drug-drug interactions"),
    ("Pathway", "pathway"),
    ("Plant", "plant"),
    ("ScientificPaper", "scientific paper"),
    ("TherapeuticEffect", "therapeutic effect"),
    ("hasBeenContributedTo", "has been contributed to"),
    ("hasMolecularWeight", "has molecular weight"),
    ("isAssociatedWith", "is associated with"),
    ("isDerivedFrom", "is derived from"),
    ("targetsPathway", "targets pathway"),
]:
    A(I(P + t), LABEL, L(lab))
# disjointness (checked over all individuals and all domain/range uses)
groups = [
    [
        P + "PlantConcept",
        P + "ChemicalConcept",
        P + "NonCompoundConstituent",
        P + "HumanConcept",
        P + "ResearchConcept",
        P + "TherapeuticConcept",
    ],
    [C + "Gene", C + "Pathway", P + "ProteinTarget", P + "DiseaseConcept"],
    [P + "ClinicalTrial", P + "ScientificPaper", P + "BioactivityMeasurement"],
]
for gi, g in enumerate(groups):
    n = f"_:dj{gi}"
    A(n, TYPE, I(OWL + "AllDisjointClasses"))
    A(n, I(OWL + "members"), f"_:dj{gi}l0")
    for k, c in enumerate(g):
        A(f"_:dj{gi}l{k}", I(RDF + "first"), I(c))
        A(f"_:dj{gi}l{k}", I(RDF + "rest"), f"_:dj{gi}l{k+1}" if k + 1 < len(g) else I(RDF + "nil"))

inp, out = sys.argv[1], sys.argv[2]
nc = set()
src = OPEN(inp)
for line in src:
    s, p, o = line.split(" ", 2)
    if p == TYPE and o.startswith(NCC):
        nc.add(s)
src.close()
fo = open(out, "w", buffering=1 << 22)
fo.writelines(add)

# RFC 3987 ipath: allow iunreserved, sub-delims, ":", "@", "/" and valid %XX; encode everything else
# (SICI DOIs contain < > [ ] ; DOIs containing ? or # must be encoded so they stay part of the path)
BAD = re.compile(
    r"%(?![0-9A-Fa-f]{2})|[^A-Za-z0-9\-._~!$&'()*+,;=:@/%\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF\U00010000-\U000EFFFD]"
)
EXM = I(SKOS + "exactMatch")


def enc(iri):  # percent-encode characters not allowed in an IRI path
    head, path = iri[:16], iri[16:]  # "https://doi.org/"
    return head + BAD.sub(lambda m: "".join("%%%02X" % b for b in m.group().encode("utf-8")), path)


n_in = n_drop = n_enc = 0
for line in OPEN(inp):
    n_in += 1
    s, p, o = line.split(" ", 2)
    if (
        s in DROP_S
        or line in DROP_T
        or (s in DEPRECATED and p in DEP_AXIOMS)
        or (p == HPC and s in nc)
    ):
        n_drop += 1
        continue
    if p == EXM and o.startswith("<https://doi.org/"):
        iri = o[1 : o.rstrip().rfind(">")]
        if BAD.search(iri[16:]):
            line = f"{s} {p} <{enc(iri)}> .\n"
            n_enc += 1
    fo.write(line)
fo.close()
print("DOI IRIs percent-encoded", n_enc)
print(
    "in",
    n_in,
    "dropped",
    n_drop,
    "added",
    len(add),
    "out",
    n_in - n_drop + len(add),
    "noncompound",
    len(nc),
)
