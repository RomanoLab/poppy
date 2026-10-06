"""split_licence_module_v25.py - move DrugCentral/ChEMBL-derived data into a separately licensed module.

DrugCentral is CC BY-SA 4.0 and ChEMBL CC BY-SA 3.0; their ShareAlike terms are not compatible with the
CC BY-NC 4.0 core, so their content ships as its own file under CC BY-SA 4.0:
  - every triple about a phyto:ProteinTarget or phyto:MechanismOfAction node,
  - every phyto:targetsProtein, phyto:hasMechanismOfAction and phyto:hasATC triple.
The schema (class/property declarations) stays in the core. The 150 phyto:TherapeuticEffect nodes (legacy
DrugCentral action types with no label and no links) are dropped. Also writes the UniChem worklist: compounds
with an InChIKey but no ChEMBL/ChEBI/HMDB/DrugBank cross-reference.
usage: split_licence_module_v25.py in.nt core.nt module.nt unichem_worklist.tsv"""

import sys

P = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
EXM = "<http://www.w3.org/2004/02/skos/core#exactMatch>"
MOVE_CLASSES = {P + "ProteinTarget>", P + "MechanismOfAction>"}
DROP_CLASSES = {P + "TherapeuticEffect>"}
MOVE_PREDS = {P + "targetsProtein>", P + "hasMechanismOfAction>", P + "hasATC>"}
UNICHEM_XREF = (
    "<http://identifiers.org/chembl.compound/",
    "<http://purl.obolibrary.org/obo/CHEBI_",
    "<http://identifiers.org/hmdb/",
    "<http://identifiers.org/drugbank/",
)
MOD = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies/module/drugcentral-chembl>"
DCT = "<http://purl.org/dc/terms/"
L = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(inp, core, module, worklist):
    move_s, drop_s, has_xref, inchikey = set(), set(), set(), {}
    for line in open(inp, encoding="utf-8"):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if p == TYPE and o in MOVE_CLASSES:
            move_s.add(s)
        elif p == TYPE and o in DROP_CLASSES:
            drop_s.add(s)
        elif p == EXM and o.startswith(UNICHEM_XREF):
            has_xref.add(s)
        elif p == P + "hasInChIKey>":
            inchikey[s] = o[1 : o.rfind('"')]
    header = (
        [
            (MOD, TYPE, "<http://www.w3.org/2002/07/owl#Ontology>"),
            (MOD, DCT + "title>", L("POPPy DrugCentral/ChEMBL module")),
            (
                MOD,
                DCT + "description>",
                L(
                    "Protein targets, mechanisms of action and ATC codes derived from DrugCentral and ChEMBL, "
                    "released separately from the POPPy core because of their ShareAlike licences. Load together "
                    "with the POPPy core file; IRIs are shared."
                ),
            ),
            (MOD, DCT + "license>", "<https://creativecommons.org/licenses/by-sa/4.0/>"),
            (MOD, DCT + "source>", "<https://drugcentral.org/>"),
            (MOD, DCT + "source>", "<https://www.ebi.ac.uk/chembl/>"),
        ]
        + [
            (DCT + p + ">", TYPE, "<http://www.w3.org/2002/07/owl#AnnotationProperty>")
            for p in ("title", "description", "license", "source")
        ]
        + [  # declarations so the module is valid OWL 2 DL on its own
            (P + "targetsProtein>", TYPE, "<http://www.w3.org/2002/07/owl#ObjectProperty>"),
            (P + "hasMechanismOfAction>", TYPE, "<http://www.w3.org/2002/07/owl#ObjectProperty>"),
            (P + "hasATC>", TYPE, "<http://www.w3.org/2002/07/owl#DatatypeProperty>"),
            (P + "hasValue>", TYPE, "<http://www.w3.org/2002/07/owl#DatatypeProperty>"),
            (P + "ProteinTarget>", TYPE, "<http://www.w3.org/2002/07/owl#Class>"),
            (P + "MechanismOfAction>", TYPE, "<http://www.w3.org/2002/07/owl#Class>"),
            (
                "<http://www.w3.org/2004/02/skos/core#exactMatch>",
                TYPE,
                "<http://www.w3.org/2002/07/owl#AnnotationProperty>",
            ),
        ]
    )
    nc = nm = nd = 0
    with (
        open(core, "w", encoding="utf-8", buffering=1 << 22) as fc,
        open(module, "w", encoding="utf-8") as fm,
    ):
        for t in header:
            fm.write(" ".join(t) + " .\n")
        for line in open(inp, encoding="utf-8"):
            s, p, o = line.split(" ", 2)
            oo = o[:-3]
            if s in drop_s or oo in drop_s:
                nd += 1
            elif s in move_s or p in MOVE_PREDS or oo in move_s:
                fm.write(line)
                nm += 1
            else:
                fc.write(line)
                nc += 1
    todo = sorted((ik, s) for s, ik in inchikey.items() if s not in has_xref)
    with open(worklist, "w", encoding="utf-8") as fw:
        fw.write("inchikey\tiri\n")
        for ik, s in todo:
            fw.write(f"{ik}\t{s[1:-1]}\n")
    print(
        f"core {nc} triples; module {nm} + {len(header)} header triples ({len(move_s)} nodes); dropped {nd} "
        f"({len(drop_s)} TherapeuticEffect nodes); UniChem worklist {len(todo)} of {len(inchikey)} InChIKeys"
    )


main(*sys.argv[1:5])
