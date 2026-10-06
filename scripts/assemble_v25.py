"""assemble_v25.py - assemble the POPPy v2.5 core: v2.4.1 + plant dedup + licence split + UniChem xrefs.

Streams the deduplicated, split core; sets the v2.5 ontology header; appends the new UniChem cross-references
that are not already present.
With --replace fix.nt, every descriptor and hasCanonicalSMILES triple of the subjects in fix.nt is replaced by
the triples in fix.nt (used for 7 compounds that had two tautomeric SMILES and therefore two descriptor values).
usage: assemble_v25.py core_in.nt new_xrefs.nt core_out.nt [--replace fix.nt]"""

import sys

ONT = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies>"
OWL = "<http://www.w3.org/2002/07/owl#"
RDFS = "<http://www.w3.org/2000/01/rdf-schema#"
DCT = "<http://purl.org/dc/terms/"
L = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
VERSION = "POPPy v2.5 (2026-10-06)"
HEADER = [
    f"{ONT} {OWL}versionInfo> {L(VERSION)} .\n",
    f"{ONT} {RDFS}comment> {L('v2.5: plant nodes with the same species name merged (map in data/patches/v25_plant_merge_map.tsv.gz); DrugCentral/ChEMBL-derived protein targets, mechanisms of action and ATC codes moved to the separately licensed module poppy_v2.5_drugcentral_chembl (CC BY-SA 4.0); UniChem cross-references added for compounds that had none.')} .\n",
    f"{ONT} {DCT}relation> <http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies/module/drugcentral-chembl> .\n",
    f"{DCT}relation> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> {OWL}AnnotationProperty> .\n",
]


P = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
REPLACED = {
    P + x + ">"
    for x in (
        "hasCanonicalSMILES mw exact_mw logp tpsa hbd hba rotatable_bonds aromatic_rings ring_count "
        "fraction_csp3 heavy_atoms heteroatoms formal_charge qed ro5_violations"
    ).split()
}


def main(core, xrefs, out, fix=None):
    fixes = [line for line in open(fix, encoding="utf-8")] if fix else []
    fix_subj = {line.split(" ", 1)[0] for line in fixes}
    new = [line for line in open(xrefs, encoding="utf-8")]
    subj = {line.split(" ", 1)[0] for line in new}
    existing = set()
    for line in open(core, encoding="utf-8"):
        if line.split(" ", 1)[0] in subj and "#exactMatch>" in line:
            existing.add(line)
    n_core = n_hdr = n_rep = 0
    with open(out, "w", encoding="utf-8", buffering=1 << 22) as fo:
        fo.writelines(HEADER)
        for line in open(core, encoding="utf-8"):
            if line.startswith(ONT + " ") and (
                f"{OWL}versionInfo>" in line or f"{RDFS}comment>" in line
            ):
                n_hdr += 1
                continue
            if fix_subj and line.split(" ", 1)[0] in fix_subj and line.split(" ", 2)[1] in REPLACED:
                n_rep += 1
                continue
            fo.write(line)
            n_core += 1
        fo.writelines(fixes)
        added = 0
        for line in dict.fromkeys(new):
            if line not in existing:
                fo.write(line)
                added += 1
    print(
        f"core {n_core} (+{len(HEADER)} header, replaced {n_hdr}); descriptor triples replaced {n_rep} -> "
        f"{len(fixes)}; new xrefs added {added} of {len(new)}"
    )


main(*sys.argv[1:4], sys.argv[sys.argv.index("--replace") + 1] if "--replace" in sys.argv else None)
