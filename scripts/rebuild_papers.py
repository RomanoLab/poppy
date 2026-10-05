#!/usr/bin/env python3
"""rebuild_papers.py — replace the v1 paper links with traceable literature evidence.

The v1 hasPaper links (from the Dr. Duke's activity-joined merge) cannot be traced and attach single
papers to thousands of compounds, so they are dropped. New links:
  * compound -> paper (DOI) from the COCONUT 2.0 `dois` field      -> hasPaper + hasPaperPerCOCONUT
  * plant / compound -> Dr. Duke's citation, only for FARMACY rows whose plant–compound occurrence is
    in the ontology and whose reference code resolves to a full citation in REFERENCES.csv                                               -> hasPaper + hasPaperPerDrDuke

usage: rebuild_papers.py in.nt coconut_dois.json data/raw drop.pkl base.nt add.nt
  coconut_dois.json: {InChIKey: [doi, ...]} extracted from the COCONUT SDF
  drop.pkl: build_phase2 output (Dr. Duke name -> structure compound map)
"""

import collections
import csv
import json
import pickle
import re
import sys

PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
L = f"<{RDFS}label>"


def P(x):
    return "<" + PH + x + ">"


def lit(v):
    v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{v}"'


def safe(x):
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.\-]", "_", x)).strip("_")


def nb(n):
    w = re.sub(r"[^a-z\- ]", " ", (n or "").lower()).split()
    return " ".join(w[:2]) if len(w) >= 2 else ""


def nname(x):
    return re.sub(r"[^A-Z0-9]", "", (x or "").upper())


NOT_A_CITATION = re.compile(
    r"see species file|personal files|aggregate of all these|^\s*J\.?[A-Za-z .&]*\.?\s*$",
    re.I,
)


def is_citation(text):
    return bool(text.strip()) and not NOT_A_CITATION.search(text)


def main():
    inp, dois_p, raw, drop_p, base_p, add_p = sys.argv[1:7]
    dois = json.load(open(dois_p))
    dm = pickle.load(open(drop_p, "rb"))["duke_map"]
    PAPER, HASP, HASDOI = P("ScientificPaper"), P("hasPaper"), P("hasDOI")
    old_papers = set()
    ik2c, bin2p, occ = {}, {}, set()
    c = collections.Counter()
    with open(inp) as f, open(base_p, "w", buffering=1 << 22) as base:
        for line in f:
            s, p, o = line.split(" ", 2)
            ob = o[:-3]
            if p == HASP or p == P("isPaperFor"):
                old_papers.add(ob if p == HASP else s)
                c["dropped_old_hasPaper"] += 1
                continue
            if s.startswith(P("Paper_")[:-1]):
                c["dropped_old_paper_node_triples"] += 1
                continue
            if p == P("hasInChIKey"):
                ik2c[ob[1:-1]] = s
            elif p == L and (s.startswith(P("Plant_")[:-1]) or s.startswith(P("Organism_")[:-1])):
                bin2p.setdefault(nb(ob[1 : ob.rfind('"')]), s)
            elif p == P("hasCompound"):
                occ.add((s, ob))
            base.write(line)
    add = open(add_p, "w")

    def W(s, p, o):
        add.write(f"{s} {p} {o} .\n")

    seen = set()
    for ik, lst in dois.items():
        ci = ik2c.get(ik)
        if not ci:
            continue
        for d in lst:
            d = d.strip().rstrip(".")
            if not re.match(r"^10\.\d{4,9}/\S+$", d):
                c["coconut_doi_malformed"] += 1
                continue
            pp = P("Paper_" + safe(d.lower()))
            if pp not in seen:
                seen.add(pp)
                W(pp, T, PAPER)
                W(pp, HASDOI, lit(d))
                W(pp, L, lit("doi:" + d))
                W(pp, f"<{SKOS}exactMatch>", f"<https://doi.org/{d}>")
            W(ci, HASP, pp)
            W(ci, P("hasPaperPerCOCONUT"), pp)
            c["compound_paper_links_coconut"] += 1
    c["papers_doi"] = len(seen)
    refs = {
        r["REFERENCE"].strip(): r
        for r in csv.DictReader(open(f"{raw}/REFERENCES.csv", encoding="latin-1"))
    }
    tax = {r["FNFNUM"]: r for r in csv.DictReader(open(f"{raw}/FNFTAX.csv", encoding="latin-1"))}
    chemid = {
        r["CHEM"]: r["CHEMID"]
        for r in csv.DictReader(open(f"{raw}/CHEMICALS.csv", encoding="latin-1"))
    }
    dref, pairs = set(), set()
    for fn in ("FARMACY.csv", "FARMACY_NEW.csv"):
        for r in csv.DictReader(open(f"{raw}/{fn}", encoding="latin-1")):
            code = (r.get("REFERENCE") or "").strip()
            t = tax.get(r["FNFNUM"])
            if not code or not t:
                continue
            pl = bin2p.get(nb(t["TAXON"] or (t["GENUS"] + " " + t["SPECIES"])))
            cid = (r.get("CHEMID") or "").strip() or chemid.get(r["CHEM"]) or nname(r["CHEM"])
            key = P("Chemical_" + safe(cid))
            cm = dm.get(key, key)
            if not pl or (pl, cm) not in occ:
                c["duke_ref_rows_without_occurrence"] += 1
                continue
            toks = [code] if code in refs else re.split(r"[\s;,]+", code)
            resolved = [t for t in toks if t in refs and is_citation(refs[t].get("LONGREF") or "")]
            if not resolved:
                c["duke_ref_rows_code_unresolved"] += 1
                continue
            for tok in resolved:
                rp = P("DukeRef_" + safe(tok))
                if rp not in dref:
                    dref.add(rp)
                    W(rp, T, PAPER)
                    W(rp, L, lit(refs[tok]["LONGREF"].strip()))
                    W(rp, P("dukeReferenceCode"), lit(tok))
                for ent in (pl, cm):
                    if (ent, rp) not in pairs:
                        pairs.add((ent, rp))
                        W(ent, HASP, rp)
                        W(ent, P("hasPaperPerDrDuke"), rp)
                        c["duke_ref_links"] += 1
    c["duke_references"] = len(dref)
    for k, lab in (
        ("hasPaperPerCOCONUT", "has paper (COCONUT 2.0 literature)"),
        ("hasPaperPerDrDuke", "has reference (Dr. Duke's FARMACY occurrence citation)"),
    ):
        W(P(k), T, "<http://www.w3.org/2002/07/owl#ObjectProperty>")
        W(P(k), f"<{RDFS}subPropertyOf>", HASP)
        W(P(k), L, lit(lab))
    W(P("dukeReferenceCode"), T, "<http://www.w3.org/2002/07/owl#DatatypeProperty>")
    W(
        HASP,
        f"<{RDFS}comment>",
        lit(
            "v2.4: COCONUT 2.0 DOIs for compounds; Dr. Duke's citations for plants/compounds backed by a FARMACY occurrence. v1 links removed."
        ),
    )
    add.close()
    c["old_papers_removed"] = len(old_papers)
    print(json.dumps(c, indent=1))


if __name__ == "__main__":
    main()
