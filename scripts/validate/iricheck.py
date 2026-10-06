"""iricheck.py - RFC 3987 character-level check of every IRI in an N-Triples file."""

import re
import sys
import collections


def lines(spec, **kw):
    """Yield lines from one file or several comma-separated files (e.g. core,module)."""
    for path in spec.split(","):
        yield from open(path, **kw)


LINE = re.compile(r"^(<[^>]*>|_:\S+) (<[^>]*>) (.*) \.$")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
UCS = " -퟿豈-﷏ﷰ-￯\U00010000-\U000efffd"
PATHBAD = re.compile(r"%(?![0-9A-Fa-f]{2})|[^A-Za-z0-9\-._~!$&'()*+,;=:@/%?#" + UCS + "]")


def bad(iri):
    if not SCHEME.match(iri):
        return "no scheme"
    rest = iri[SCHEME.match(iri).end() :]
    if rest.startswith("//"):
        a = rest[2:]
        i = min([k for k in (a.find("/"), a.find("?"), a.find("#")) if k >= 0] or [len(a)])
        rest = a[i:]
    m = PATHBAD.search(rest)
    if m:
        return "char " + repr(m.group())
    if rest.count("#") > 1:
        return "two #"
    return None


c = collections.Counter()
ex = {}
unparsed = 0
for line in lines(sys.argv[1], encoding="utf-8"):
    m = LINE.match(line.rstrip("\n"))
    if not m:
        unparsed += 1
        ex.setdefault("UNPARSED", line[:150])
        continue
    for t in m.groups():
        if t.startswith("<") and t.endswith(">"):
            r = bad(t[1:-1])
            if r:
                c[r] += 1
                ex.setdefault(r, t[:150])
print("unparsed lines", unparsed, "| bad IRIs", sum(c.values()), dict(c))
[print(k, v) for k, v in ex.items()]
