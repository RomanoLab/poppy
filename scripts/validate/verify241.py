"""verify241.py - confirm the v2.4.1 schema fixes are present (and the v2.4 defects absent) in a release file.
usage: verify241.py poppy_v2.4.1.nt.gz"""

import gzip
import sys
import collections

P = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
C = "<http://jdr.bio/ontologies/comptox.owl#"
RDF = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RS = "<http://www.w3.org/2000/01/rdf-schema#"
OWL = "<http://www.w3.org/2002/07/owl#"
XSD = "<http://www.w3.org/2001/XMLSchema#"
SK = "<http://www.w3.org/2004/02/skos/core#"
DCT = "<http://purl.org/dc/terms/"
ONT = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies>"
T = lambda s, p, o: (s, p, o)
present = {  # must be present
    "versionInfo v2.4.1": T(ONT, OWL + "versionInfo>", '"POPPy v2.4.1 (2026-10-05)"'),
    "license CC BY-NC 4.0": T(
        ONT, DCT + "license>", "<https://creativecommons.org/licenses/by-nc/4.0/>"
    ),
    "skos:altLabel declared": T(SK + "altLabel>", RDF + "type>", OWL + "AnnotationProperty>"),
    "skos:exactMatch declared": T(SK + "exactMatch>", RDF + "type>", OWL + "AnnotationProperty>"),
    "labelIsPlaceholder declared": T(
        P + "labelIsPlaceholder>", RDF + "type>", OWL + "DatatypeProperty>"
    ),
    "aromatic_rings range integer": T(P + "aromatic_rings>", RS + "range>", XSD + "integer>"),
    "rotatable_bonds range integer": T(P + "rotatable_bonds>", RS + "range>", XSD + "integer>"),
    "commonName range rdfs:Literal": T(P + "commonName>", RS + "range>", RS + "Literal>"),
    "hasCommonName domain incl. NonCompound": T(
        "_:u4l2", RDF + "first>", P + "NonCompoundConstituent>"
    ),
    "hasReportedConstituent domain Plant": T(
        P + "hasReportedConstituent>", RS + "domain>", P + "Plant>"
    ),
    "hasReportedConstituent range NonCompound": T(
        P + "hasReportedConstituent>", RS + "range>", P + "NonCompoundConstituent>"
    ),
    "phyto:Gene replaced by cmptx:Gene": T(
        P + "Gene>", "<http://purl.obolibrary.org/obo/IAO_0100001>", C + "Gene>"
    ),
    "label on Plant": T(P + "Plant>", RS + "label>", '"plant"'),
}
absent = {  # must be absent
    "commonName as AnnotationProperty": T(
        P + "commonName>", RDF + "type>", OWL + "AnnotationProperty>"
    ),
    "scientificSynonym as AnnotationProperty": T(
        P + "scientificSynonym>", RDF + "type>", OWL + "AnnotationProperty>"
    ),
    "aromatic_rings range double": T(P + "aromatic_rings>", RS + "range>", XSD + "double>"),
    "commonName range string": T(P + "commonName>", RS + "range>", XSD + "string>"),
    "phyto:Gene equivalentClass": T(P + "Gene>", OWL + "equivalentClass>", C + "Gene>"),
    "old versionInfo v2.4": T(ONT, OWL + "versionInfo>", '"POPPy v2.4 (2026-10-05)"'),
}
found = collections.Counter()
subj = collections.Counter()
dj = 0
dr = 0
hpc_unknown = 0
badiri = 0
n = 0
want = set(present.values()) | set(absent.values())
for line in gzip.open(sys.argv[1], "rt", encoding="utf-8"):
    n += 1
    s, p, o = line.split(" ", 2)
    o = o[:-3]
    if (s, p, o) in want:
        found[(s, p, o)] += 1
    if s in (P + "interactsWith>", P + "hasInteractionsWith>"):
        subj["interactsWith/hasInteractionsWith"] += 1
    if s.startswith("_:N5bc5") or s.startswith("_:Nc370"):
        subj["DataRange"] += 1
    if o == OWL + "AllDisjointClasses>":
        dj += 1
    if p == RS + "label>" and o.startswith("_:"):
        dr += 1
    if (
        p == SK + "exactMatch>"
        and o.startswith("<https://doi.org/")
        and any(c in o[1:-1] for c in "<>[]")
    ):
        badiri += 1
print("triples", n)
for k, t in present.items():
    print("PRESENT" if found[t] else "MISSING", "|", k)
for k, t in absent.items():
    print("GONE   " if not found[t] else "STILL THERE", "|", k)
print(
    "triples with subject interactsWith/hasInteractionsWith:",
    subj["interactsWith/hasInteractionsWith"],
)
print("orphan DataRange triples:", subj["DataRange"])
print("owl:AllDisjointClasses axioms:", dj)
print("blank-node rdfs:label values:", dr)
print("DOI IRIs still containing < > [ ]:", badiri)
