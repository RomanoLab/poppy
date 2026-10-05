#!/usr/bin/env python3
"""fetch_pubchem_smiles_names.py — look up names / IUPAC names / SMILES in PubChem by InChIKey.
Run on a machine with internet (your Mac Terminal). Standard library only, no pip installs.

  cd ~/poppy
  python3 scripts/fetch_pubchem_smiles_names.py data/patches/compounds_needing_names.tsv data/patches/pubchem_fill.tsv

- Resumable: re-run the same command after an interruption; finished InChIKeys are skipped.
- ~4 requests/s (PubChem allows 5/s). Retries throttling/server errors with back-off; a 404 means
  "not in PubChem" and is recorded with empty fields.
"""

import sys
import csv
import time
import json
import os
import urllib.request
import urllib.parse
import urllib.error

inp, outp = sys.argv[1], sys.argv[2]
done = set()
if os.path.exists(outp):
    done = {r["inchikey"] for r in csv.DictReader(open(outp), delimiter="\t")}
rows = [r for r in csv.DictReader(open(inp), delimiter="\t") if r["inchikey"] not in done]
new = not os.path.exists(outp)
out = open(outp, "a", newline="")
w = csv.writer(out, delimiter="\t")
if new:
    w.writerow(["compound_iri", "inchikey", "cid", "title", "iupac_name", "smiles"])
URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{}/property/Title,IUPACName,SMILES,IsomericSMILES,CanonicalSMILES/JSON"
print(f"{len(done)} already done, {len(rows)} to fetch (~{len(rows)/4/60:.0f} min)", flush=True)
found = missing = 0
t0 = time.time()
for i, r in enumerate(rows):
    for attempt in range(6):
        try:
            req = urllib.request.Request(
                URL.format(urllib.parse.quote(r["inchikey"])),
                headers={"User-Agent": "POPPy-ontology/2.1"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                ps = json.load(resp)["PropertyTable"]["Properties"]
            p = ps[0]
            smi = p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES") or ""
            w.writerow(
                [
                    r["compound_iri"],
                    r["inchikey"],
                    p.get("CID", ""),
                    p.get("Title", ""),
                    p.get("IUPACName", ""),
                    smi,
                ]
            )
            found += 1
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                w.writerow([r["compound_iri"], r["inchikey"], "", "", "", ""])
                missing += 1
                break
            time.sleep(2**attempt)  # 503 throttling / 5xx: back off and retry
        except Exception:
            time.sleep(2**attempt)
    else:
        print("giving up for now on", r["inchikey"], "(will retry on next run)", flush=True)
    if i % 200 == 0:
        out.flush()
        el = time.time() - t0
        print(
            f"{i}/{len(rows)}  found {found}  not in PubChem {missing}  ~{(len(rows)-i)*el/max(i,1)/60:.0f} min left",
            flush=True,
        )
    time.sleep(0.25)
out.close()
print(f"done: found {found}, not in PubChem {missing}")
