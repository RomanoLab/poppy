"""dedup_plants_v25.py - merge plant nodes that are the same species (same genus + epithet).

Two Plant nodes merge when their labels share genus + specific epithet after dropping author strings and case
(e.g. "Artemisia abrotanum" + "Artemisia abrotanum L."; "Berberis vulgaris" + "Berberis vulgaris L.").
Never merged: infraspecific names (ssp./subsp./var./f./cv.), hybrids, "sp./spp./cf./aff." names, and nodes
whose NCBI taxon IDs (phyto:hasTaxon) disagree. Canonical node = most compounds, then has a taxon, then the
shorter IRI. Every triple of a merged node is redirected to the canonical node; its rdfs:label becomes
skos:altLabel; its single-valued taxonomy fields are dropped when the canonical node has its own.
usage: dedup_plants_v25.py in.nt out.nt merge_map.tsv"""

import collections
import re
import sys

P = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
ALT = "<http://www.w3.org/2004/02/skos/core#altLabel>"
SINGLE = {
    P + x + ">"
    for x in "hasTaxon hasGenus hasSpecies taxonomicFamily taxonomicGenus taxonomyStatus".split()
}
NCBI = "<http://purl.obolibrary.org/obo/NCBITaxon_"
EXM = "<http://www.w3.org/2004/02/skos/core#exactMatch>"
INFRA = re.compile(
    r"(^|[\s.(])(ssp|subsp|var|forma|cv|nothosubsp|nothovar|race|strain|chemotype|ecotype|cultivar|hybrid|group|aggr|agg|sensu|complex)(\.|\s|$)"
    r"|\sf\.\s|\ss\.\s?(l|str)\.|'|\"|×|\sx\s",
    re.I,
)
BAD_EPI = {"sp", "spp", "cf", "aff", "x"}
AUTHOR_WORDS = {"ex", "et", "de", "del", "da", "van", "von", "der", "den", "du", "le", "la", "fil"}


def unq(o):
    return o[1 : o.rfind('"')] if o.startswith('"') else None


def binomial(label):
    if not label or INFRA.search(label):
        return None
    t = label.replace("'", "").split()
    if len(t) < 2 or not re.fullmatch(r"[A-Za-z][a-z-]+", t[0].capitalize()):
        return None
    epi = t[1].lower().rstrip(".")
    # an unmarked lower-case third word ("Citrus reticulata tangerine") is an infraspecific/common name, not an author
    if len(t) > 2 and re.fullmatch(r"[a-z]{3,}", t[2]) and t[2] not in AUTHOR_WORDS:
        return None
    if epi in BAD_EPI or not re.fullmatch(r"[a-z][a-z-]+", epi):
        return None
    return t[0].capitalize() + " " + epi


def main(inp, out, mapf):
    plants, lab, tax, ncomp = set(), {}, {}, collections.Counter()
    for line in open(inp, encoding="utf-8"):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if p == TYPE and o == P + "Plant>":
            plants.add(s)
        elif p == LABEL:
            lab[s] = unq(o)
        elif p == P + "hasTaxon>":
            tax[s] = o
        elif p == P + "hasCompound>":
            ncomp[s] += 1
    groups = collections.defaultdict(list)
    for s in plants:
        b = binomial(lab.get(s))
        if b:
            groups[b].append(s)
    canon, conflicts = {}, 0
    rank = lambda s: (-ncomp[s], 0 if s in tax else 1, len(s), s)
    for b, nodes in groups.items():
        if len(nodes) < 2:
            continue
        nodes.sort(key=rank)
        keep = nodes[0]
        for d in nodes[1:]:
            if d in tax and keep in tax and tax[d] != tax[keep]:
                conflicts += 1  # different NCBI taxa: leave separate
                continue
            canon[d] = keep
    keepers = set(canon.values())
    with open(mapf, "w", encoding="utf-8") as fm:
        fm.write(
            "merged_iri\tmerged_label\tmerged_compounds\tcanonical_iri\tcanonical_label\tcanonical_compounds\n"
        )
        for d, k in sorted(canon.items(), key=lambda x: x[1]):
            fm.write(f"{d[1:-1]}\t{lab.get(d)}\t{ncomp[d]}\t{k[1:-1]}\t{lab.get(k)}\t{ncomp[k]}\n")
    keep_single = collections.defaultdict(
        set
    )  # canonical subject -> single-valued props it already has
    existing = set()  # triples already on a canonical node (to avoid duplicates after redirect)
    for line in open(inp, encoding="utf-8"):
        s, p, o = line.split(" ", 2)
        if s in keepers:
            existing.add(line)
            if p in SINGLE or (p == EXM and o.startswith(NCBI)):
                keep_single[s].add(p if p != EXM else "NCBI")
        elif o[:-3] in keepers:
            existing.add(line)
    n_in = n_rew = n_dup = n_drop = 0
    with open(out, "w", encoding="utf-8", buffering=1 << 22) as fo:
        for line in open(inp, encoding="utf-8"):
            n_in += 1
            s, p, o = line.split(" ", 2)
            oo = o[:-3]
            if s not in canon and oo not in canon:
                fo.write(line)
                continue
            if s in canon:
                k = canon[s]
                if (
                    p in SINGLE
                    and p in keep_single[k]
                    or (p == EXM and o.startswith(NCBI) and "NCBI" in keep_single[k])
                ):
                    n_drop += 1
                    continue
                if p == LABEL:
                    p = ALT
                s = k
            if oo in canon:
                o = canon[oo] + " .\n"
            new = f"{s} {p} {o}"
            if new in existing:
                n_dup += 1
                continue
            existing.add(new)
            fo.write(new)
            n_rew += 1
    print(
        f"plants {len(plants)}; merged {len(canon)} nodes into {len(keepers)}; taxon conflicts kept apart {conflicts}; "
        f"triples in {n_in}, rewritten {n_rew}, duplicates removed {n_dup}, single-valued dropped {n_drop}"
    )


main(*sys.argv[1:4])
