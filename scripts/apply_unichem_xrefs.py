"""apply_unichem_xrefs.py - turn the UniChem cache into skos:exactMatch cross-references.

Writes one N-Triples line per new cross-reference (identifiers.org / OBO IRIs, the same forms already used in
POPPy) for the sources PubChem, ChEMBL, ChEBI, HMDB, DrugBank and KEGG; prints per-source counts.
DrugCentral IDs are deliberately not added (ShareAlike licence; see split_licence_module_v25.py).
usage: apply_unichem_xrefs.py unichem_worklist.tsv unichem_cache.jsonl out_xrefs.nt"""

import collections
import json
import re
import sys

EXM = "<http://www.w3.org/2004/02/skos/core#exactMatch>"
FORM = {
    "pubchem": lambda v: f"http://identifiers.org/pubchem.compound/{v}",
    "chembl": lambda v: f"http://identifiers.org/chembl.compound/{v}",
    "chebi": lambda v: f"http://purl.obolibrary.org/obo/CHEBI_{v.replace('CHEBI:', '')}",
    "hmdb": lambda v: f"http://identifiers.org/hmdb/{v}",
    "drugbank": lambda v: f"http://identifiers.org/drugbank/{v}",
    "kegg_ligand": lambda v: (
        f"http://identifiers.org/kegg.compound/{v}" if v.startswith("C") else None
    ),
}
OK = re.compile(r"^[A-Za-z0-9:._-]+$")


def main(worklist, cache, out):
    iri = dict(
        line.split("\t") for line in open(worklist, encoding="utf-8").read().splitlines()[1:]
    )
    counts, comps, n_hit, n_seen = collections.Counter(), collections.defaultdict(set), 0, 0
    seen = set()
    with open(out, "w", encoding="utf-8") as fo:
        for line in open(cache, encoding="utf-8"):
            rec = json.loads(line)
            ik = rec["ik"]
            if ik not in iri or ik in seen:
                continue
            seen.add(ik)
            n_seen += 1
            hit = False
            for src, ids in (rec.get("sources") or {}).items():
                f = FORM.get(src)
                if not f:
                    continue
                for v in ids:
                    v = str(v).strip()
                    u = f(v) if OK.match(v) else None
                    if u:
                        fo.write(f"<{iri[ik]}> {EXM} <{u}> .\n")
                        counts[src] += 1
                        comps[src].add(ik)
                        hit = True
            n_hit += hit
    print(
        f"cache records used {n_seen:,} of {len(iri):,} worklist compounds; compounds with >=1 new xref {n_hit:,}"
    )
    for s in FORM:
        print(f"  {s}: {counts[s]:,} xrefs over {len(comps[s]):,} compounds")


main(*sys.argv[1:4])
