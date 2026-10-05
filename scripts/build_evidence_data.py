#!/usr/bin/env python3
"""build_evidence_data.py — per-plant and per-compound evidence shards for the Explore page.

Writes website/data/evidence/plants/<djb2>.json and website/data/evidence/compounds/<djb2>.json:
  plant:    {"trials": [[nct, title, phase]], "refs": [citation]}
  compound: {"trials": [[nct, title, phase]], "dois": [doi], "refs": [citation],
             "bio": [[gene, type, relation, value, unit, pmid]], "n": {"trials":.., "dois":.., "bio":..}}
Lists are capped (CAP) to keep shards small; "n" holds the full counts.

usage: build_evidence_data.py poppy.nt website/data
"""

import collections
import json
import os
import sys

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
CX = "<http://jdr.bio/ontologies/comptox.owl#"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
ALT = "<http://www.w3.org/2004/02/skos/core#altLabel>"
CAP = 50


def djb2(s):
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return h & 255


def val(o):
    return o[1 : o.rfind('"')].replace('\\"', '"').replace("\\\\", "\\")


def loc(u):
    return u[1:-1].split("#", 1)[1]


def main():
    nt, D = sys.argv[1], sys.argv[2]
    trial = collections.defaultdict(dict)
    paper = collections.defaultdict(dict)
    bio = collections.defaultdict(dict)
    sym = {}
    ent_trials = collections.defaultdict(list)
    ent_papers = collections.defaultdict(list)
    for line in open(nt):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if s.startswith(PH + "ClinicalTrial_"):
            if p == L:
                trial[s]["t"] = val(o)
            elif p == PH + "trialPhase>":
                trial[s]["ph"] = val(o)
            elif p == PH + "hasNCTId>":
                trial[s]["nct"] = val(o)
        elif s.startswith(PH + "Paper_") or s.startswith(PH + "DukeRef_"):
            if p == PH + "hasDOI>":
                paper[s]["doi"] = val(o)
            elif p == L:
                paper[s]["cite"] = val(o)
        elif s.startswith(PH + "Bioactivity_"):
            k = p[len(PH) : -1] if p.startswith(PH) else None
            if k in ("activityType", "activityRelation", "activityValue", "activityUnit"):
                bio[s][k] = val(o)
            elif k in ("activityCompound", "activityTarget"):
                bio[s][k] = o
            elif k == "hasReference":
                bio[s]["pmid"] = o.rsplit("/", 1)[1][:-1]
        elif s.startswith(CX) and p == ALT:
            sym[s] = val(o)
        if p == PH + "hasClinicalStudy>":
            ent_trials[s].append(o)
        elif p == PH + "hasPaper>":
            ent_papers[s].append(o)
    ent_bio = collections.defaultdict(list)
    for b in bio.values():
        if "activityCompound" in b:
            ent_bio[b["activityCompound"]].append(b)
    shards = {"plants": collections.defaultdict(dict), "compounds": collections.defaultdict(dict)}
    ents = set(ent_trials) | set(ent_papers) | set(ent_bio)
    for e in ents:
        kind = (
            "compounds"
            if "#Chemical_" in e
            else "plants" if ("#Plant_" in e or "#Organism_" in e) else None
        )
        if not kind:
            continue
        rec = {}
        tr = [trial[t] for t in ent_trials.get(e, []) if t in trial]
        tr.sort(key=lambda t: (t.get("ph", "") or "zz", t.get("nct", "")), reverse=True)
        if tr:
            rec["trials"] = [[t.get("nct", ""), t.get("t", ""), t.get("ph", "")] for t in tr[:CAP]]
        ps = [paper[x] for x in ent_papers.get(e, []) if x in paper]
        dois = sorted({x["doi"] for x in ps if "doi" in x})
        refs = sorted({x["cite"] for x in ps if "doi" not in x and "cite" in x})
        if dois:
            rec["dois"] = dois[:CAP]
        if refs:
            rec["refs"] = refs[:CAP]
        bl = ent_bio.get(e, [])
        if bl:
            rows = [
                [
                    sym.get(
                        b.get("activityTarget"),
                        loc(b["activityTarget"]) if b.get("activityTarget") else "",
                    ),
                    b.get("activityType", ""),
                    b.get("activityRelation", ""),
                    b.get("activityValue", ""),
                    b.get("activityUnit", ""),
                    b.get("pmid", ""),
                ]
                for b in bl
            ]
            rows.sort(key=lambda r: (r[0], r[1]))
            rec["bio"] = rows[:CAP]
        n = {"trials": len(tr), "dois": len(dois), "refs": len(refs), "bio": len(bl)}
        if any(v > CAP for v in n.values()):
            rec["n"] = n
        if rec:
            shards[kind][djb2(loc(e))][loc(e)] = rec
    for kind, sh in shards.items():
        os.makedirs(f"{D}/evidence/{kind}", exist_ok=True)
        for b in range(256):
            with open(f"{D}/evidence/{kind}/{b}.json", "w") as f:
                json.dump(sh.get(b, {}), f, ensure_ascii=False, separators=(",", ":"))
        print(kind, sum(len(v) for v in sh.values()), "entities with evidence")


if __name__ == "__main__":
    main()
