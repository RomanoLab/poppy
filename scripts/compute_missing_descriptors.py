#!/usr/bin/env python3
"""compute_missing_descriptors.py — RDKit descriptors for compounds that have SMILES but no phyto:mw.

Uses the same descriptor definitions as compute_compound_descriptors.py (ChEMBL-style
molecule_properties) and writes them straight to N-Triples with the same datatypes.

usage: compute_missing_descriptors.py input.tsv out.nt [--procs 2]
input.tsv: <compound IRI>\t<SMILES> per line (compounds lacking phyto:mw).
"""

import multiprocessing as mp
import sys

from rdkit import Chem, RDLogger
from rdkit.Chem import QED, Crippen, Descriptors, rdMolDescriptors

RDLogger.DisableLog("rdApp.*")
PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
XSD = {
    "mw": "double",
    "exact_mw": "double",
    "logp": "double",
    "tpsa": "double",
    "hbd": "integer",
    "hba": "integer",
    "rotatable_bonds": "integer",
    "aromatic_rings": "integer",
    "ring_count": "integer",
    "fraction_csp3": "double",
    "heavy_atoms": "integer",
    "heteroatoms": "integer",
    "formal_charge": "integer",
    "qed": "double",
    "ro5_violations": "integer",
}


def descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    try:
        q = round(QED.qed(mol), 4)
    except Exception:  # noqa: BLE001 - QED fails on some exotic valences
        q = ""
    return {
        "mw": round(mw, 3),
        "exact_mw": round(Descriptors.ExactMolWt(mol), 4),
        "logp": round(logp, 3),
        "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 2),
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "ring_count": rdMolDescriptors.CalcNumRings(mol),
        "fraction_csp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 4),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "heteroatoms": rdMolDescriptors.CalcNumHeteroatoms(mol),
        "formal_charge": Chem.GetFormalCharge(mol),
        "qed": q,
        "ro5_violations": sum([mw > 500, logp > 5, hbd > 5, hba > 10]),
    }


def work(line):
    iri, smi = line.rstrip("\n").split("\t", 1)
    try:
        d = descriptors(smi)
    except Exception:  # noqa: BLE001
        d = None
    if d is None:
        return iri, None
    return iri, "".join(
        f'<{iri}> <{PH}{k}> "{v}"^^<http://www.w3.org/2001/XMLSchema#{XSD[k]}> .\n'
        for k, v in d.items()
        if v != ""
    )


def main():
    inp, out = sys.argv[1], sys.argv[2]
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 2
    with open(inp) as f:
        lines = f.readlines()
    ok = bad = 0
    with mp.Pool(procs) as pool, open(out, "w") as o:
        for _iri, nt in pool.imap(work, lines, chunksize=500):
            if nt:
                o.write(nt)
                ok += 1
            else:
                bad += 1
    print(f"descriptors for {ok} compounds; {bad} SMILES not parseable")


if __name__ == "__main__":
    main()
