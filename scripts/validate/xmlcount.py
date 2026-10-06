"""xmlcount.py - stream-parse POPPy RDF/XML (well-formedness) and count property elements (= triples).
usage: xmlcount.py poppy.rdf"""

import sys
import xml.parsers.expat

d = [0]
n = [0]
p = xml.parsers.expat.ParserCreate(namespace_separator=" ")


def st(name, attrs):
    d[0] += 1
    if d[0] == 3:
        n[0] += 1


def en(name):
    d[0] -= 1


p.StartElementHandler = st
p.EndElementHandler = en
with open(sys.argv[1], "rb") as f:
    p.ParseFile(f)
print("well-formed; property elements (triples):", n[0])
