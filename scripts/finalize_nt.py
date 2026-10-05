#!/usr/bin/env python3
"""finalize_nt.py — one rdfs:label per subject (others -> skos:altLabel) and stream-write RDF/XML.
Input must be sorted N-Triples (grouped by subject). usage: finalize_nt.py in.nt out.nt out.rdf"""

import sys
import re
from xml.sax.saxutils import escape, quoteattr

LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
ALT = "<http://www.w3.org/2004/02/skos/core#altLabel>"
NS = {
    "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#": "phyto",
    "http://jdr.bio/ontologies/comptox.owl#": "cmptx",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2002/07/owl#": "owl",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://www.w3.org/2001/XMLSchema#": "xsd",
}
UNESC = re.compile(r"\\(.)")


def unesc(v):
    return UNESC.sub(lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m.group(1), m.group(1)), v)


def score(lab):  # prefer a well-formed binomial, then shorter
    w = lab.split()
    ok = len(w) >= 2 and w[0][:1].isupper() and w[1].islower()
    return (0 if ok else 1, "var." in lab or "subsp." in lab, len(lab))


def qname(u):
    for k, v in NS.items():
        if u.startswith(k) and re.match(r"^[A-Za-z_][\w.\-]*$", u[len(k) :]):
            return v + ":" + u[len(k) :]
    return None


def main(inp, out_nt, out_rdf):
    fo = open(out_nt, "w", buffering=1 << 22)
    fx = open(out_rdf, "w", encoding="utf-8", buffering=1 << 22)
    fx.write(
        '<?xml version="1.0" encoding="utf-8"?>\n<rdf:RDF '
        + " ".join(f'xmlns:{v}="{k}"' for k, v in NS.items())
        + ">\n"
    )
    cur = None
    group = []
    nalt = 0
    nx = 0

    def flush():
        nonlocal nalt, nx
        if not group:
            return
        labs = [g for g in group if g[1] == LABEL]
        if len(labs) > 1:
            keep = min(labs, key=lambda g: score(unesc(g[2][1 : g[2].rfind('"')])))
            group[:] = [
                (s, ALT if (p == LABEL and (s, p, o) != keep) else p, o) for s, p, o in group
            ]
            nalt += len(labs) - 1
        s = group[0][0]
        about = f'rdf:nodeID="{s[2:]}"' if s.startswith("_:") else f"rdf:about={quoteattr(s[1:-1])}"
        fx.write(f"  <rdf:Description {about}>\n")
        for s_, p, o in group:
            fo.write(f"{s_} {p} {o} .\n")
            pu = p[1:-1]
            q = qname(pu)
            extra = ""
            if not q:
                i = max(pu.rfind("#"), pu.rfind("/")) + 1
                q = "ns0:" + pu[i:]
                extra = f' xmlns:ns0="{escape(pu[:i])}"'
            if o.startswith("<"):
                fx.write(f"    <{q}{extra} rdf:resource={quoteattr(o[1:-1])}/>\n")
            elif o.startswith("_:"):
                fx.write(f'    <{q}{extra} rdf:nodeID="{o[2:]}"/>\n')
            else:
                j = o.rfind('"')
                v = unesc(o[1:j])
                suf = o[j + 1 :]
                attr = ""
                if suf.startswith("^^"):
                    attr = f" rdf:datatype={quoteattr(suf[3:-1])}"
                elif suf.startswith("@"):
                    attr = f' xml:lang="{suf[1:]}"'
                v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)
                fx.write(f"    <{q}{extra}{attr}>{escape(v)}</{q.split(' ')[0]}>\n")
            nx += 1
        fx.write("  </rdf:Description>\n")
        group.clear()

    for line in open(inp):
        s, p, o = line.split(" ", 2)
        o = o[:-3]
        if s != cur:
            flush()
            cur = s
        group.append((s, p, o))
    flush()
    fx.write("</rdf:RDF>\n")
    fo.close()
    fx.close()
    print("triples", nx, "labels moved to altLabel", nalt)


main(*sys.argv[1:4])
