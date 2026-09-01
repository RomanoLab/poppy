#!/usr/bin/env python3
"""
compute_compound_descriptors.py — physicochemical + druglikeness descriptors for every
POPPy compound, computed locally with RDKit from the SMILES already in the ontology.

Reads Chemical_* individuals straight out of an RDF/XML ontology file (streaming, no rdflib),
pulling each compound's SMILES (ns1:hasSMILES) and InChIKey (ns1:hasCommonName). Emits:

  1. <out>.csv  — the ML feature matrix: one row per compound, keyed by chem_id + inchikey,
     with the descriptor columns below. This is what you feed to sklearn / pandas.
  2. <out>.fragment.xml — an RDF/XML fragment of the same values as ns1:<descriptor> data
     properties per Chemical individual, ready to fold into the ontology with fold_inplace.py.

Descriptors (match ChEMBL's molecule_properties, all RDKit-computed):
  mw, exact_mw, logp, tpsa, hbd, hba, rotatable_bonds, aromatic_rings, ring_count,
  fraction_csp3, heavy_atoms, heteroatoms, formal_charge, qed, ro5_violations

USAGE (in your networked/RDKit Terminal — the base conda env has rdkit since you built ECFPs):
    python3 compute_compound_descriptors.py \
        --rdf ~/Downloads/poppyontology.rdf \
        --out data/enrichment/compound_descriptors

Reads only ns1:hasSMILES / ns1:hasCommonName — safe on the multi-GB file (line-streamed).
"""
from __future__ import annotations
import argparse, csv, re, sys, html

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors, QED
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")   # silence per-molecule parse warnings

PHYTO = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
RE_ABOUT   = re.compile(r'rdf:about="[^"]*#(Chemical_[^"]+)"')
RE_SMILES  = re.compile(r'<ns1:hasSMILES>(.*?)</ns1:hasSMILES>')
RE_INCHIK  = re.compile(r'<ns1:hasCommonName>(.*?)</ns1:hasCommonName>')

COLS = ["chem_id","inchikey","mw","exact_mw","logp","tpsa","hbd","hba","rotatable_bonds",
        "aromatic_rings","ring_count","fraction_csp3","heavy_atoms","heteroatoms",
        "formal_charge","qed","ro5_violations"]

# numeric-only descriptor columns -> xsd type for the RDF fragment
XSD = {"mw":"double","exact_mw":"double","logp":"double","tpsa":"double","hbd":"integer",
       "hba":"integer","rotatable_bonds":"integer","aromatic_rings":"integer",
       "ring_count":"integer","fraction_csp3":"double","heavy_atoms":"integer",
       "heteroatoms":"integer","formal_charge":"integer","qed":"double",
       "ro5_violations":"integer"}

def descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mw   = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    hbd  = rdMolDescriptors.CalcNumHBD(mol)
    hba  = rdMolDescriptors.CalcNumHBA(mol)
    ro5  = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
    try:
        q = QED.qed(mol)
    except Exception:
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
        "qed": (round(q, 4) if q != "" else ""),
        "ro5_violations": ro5,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rdf", required=True, help="poppyontology.rdf (or molecular) — source of SMILES")
    ap.add_argument("--out", default="compound_descriptors", help="output basename (.csv + .fragment.xml)")
    args = ap.parse_args()

    csv_path  = args.out + ".csv"
    frag_path = args.out + ".fragment.xml"

    n_seen = n_ok = n_bad = 0
    cur = smiles = ikey = None

    def esc(s): return html.escape(str(s), quote=True)

    with open(args.rdf, encoding="utf-8", errors="replace") as f, \
         open(csv_path, "w", newline="", encoding="utf-8") as cf, \
         open(frag_path, "w", encoding="utf-8") as ff:

        w = csv.writer(cf); w.writerow(COLS)
        # declare the datatype properties once
        for col in COLS:
            if col in XSD:
                ff.write('  <owl:DatatypeProperty rdf:about="%s%s"/>\n' % (PHYTO, col))

        def flush():
            nonlocal n_seen, n_ok, n_bad
            if not cur:
                return
            n_seen += 1
            if not smiles:
                return
            d = descriptors(html.unescape(smiles))
            if d is None:
                n_bad += 1
                return
            n_ok += 1
            w.writerow([cur, ikey or ""] + [d[c] for c in COLS[2:]])
            ff.write('  <rdf:Description rdf:about="%s%s">\n' % (PHYTO, cur))
            for c in COLS[2:]:
                v = d[c]
                if v == "" or v is None:
                    continue
                ff.write('    <ns1:%s rdf:datatype="http://www.w3.org/2001/XMLSchema#%s">%s</ns1:%s>\n'
                         % (c, XSD[c], v, c))
            ff.write('  </rdf:Description>\n')

        for line in f:
            if "<rdf:Description rdf:about=" in line:
                flush()
                cur = smiles = ikey = None
                m = RE_ABOUT.search(line)
                cur = m.group(1) if m else None
            elif cur:
                if smiles is None:
                    m = RE_SMILES.search(line)
                    if m: smiles = m.group(1)
                if ikey is None:
                    m = RE_INCHIK.search(line)
                    if m: ikey = m.group(1)
        flush()

    print("Chemical individuals seen:      %d" % n_seen, file=sys.stderr)
    print("descriptors computed (OK):      %d" % n_ok, file=sys.stderr)
    print("SMILES present but unparseable: %d" % n_bad, file=sys.stderr)
    print("feature matrix : %s" % csv_path, file=sys.stderr)
    print("RDF fragment   : %s" % frag_path, file=sys.stderr)

if __name__ == "__main__":
    raise SystemExit(main())
