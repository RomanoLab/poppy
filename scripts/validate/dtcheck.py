"""dtcheck.py - check every datatype-property value against the declared rdfs:range datatype.
usage: dtcheck.py poppy.nt schema_tbox.nt   (lines marked MISMATCH = fail)"""

import sys
import collections


def lines(spec, **kw):
    """Yield lines from one file or several comma-separated files (e.g. core,module)."""
    for path in spec.split(","):
        yield from open(path, **kw)


tb = [l.split(" ", 2) for l in open(sys.argv[2])]
RNG = "<http://www.w3.org/2000/01/rdf-schema#range>"
DP = "<http://www.w3.org/2002/07/owl#DatatypeProperty>"
dps = {s for s, p, o in tb if o.startswith(DP)}
rng = {s: o[:-3] for s, p, o in tb if p == RNG and s in dps}
cnt = collections.Counter()
ex = {}
for line in lines(sys.argv[1]):
    s, p, o = line.split(" ", 2)
    if p in dps:
        o = o[:-3]
        if o.startswith('"'):
            j = o.rfind('"')
            suf = o[j + 1 :]
            dt = (
                suf[2:]
                if suf.startswith("^^")
                else (
                    "rdf:langString"
                    if suf.startswith("@")
                    else "<http://www.w3.org/2001/XMLSchema#string>"
                )
            )
        else:
            dt = "NON-LITERAL"
        k = (p, rng.get(p, "(none)"), dt)
        cnt[k] += 1
        ex.setdefault(k, o[:60])
sh = (
    lambda x: x.replace(
        "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#", "P:"
    )
    .replace("<http://jdr.bio/ontologies/comptox.owl#", "C:")
    .replace("<http://www.w3.org/2001/XMLSchema#", "xsd:")
    .replace(">", "")
)
for (p, r, d), v in sorted(cnt.items()):
    flag = "" if r == "(none)" or r == d or (r.endswith("#Literal>")) else "  <-- MISMATCH"
    print(v, sh(p), "range", sh(r), "values", sh(d), sh(ex[(p, r, d)]) if flag else "", flag)
