"""Chunked, streaming RDF/XML -> N-Triples converter for very large rdflib-style files.
usage: rdfxml2nt.py split <rdf> <nchunks> <offsets.json>
       rdfxml2nt.py convert <rdf> <offsets.json> <chunk_idx> <out.nt> [--drop-inverses]"""

import sys
import json
import re
import time
import xml.etree.ElementTree as ET

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XMLNS = "http://www.w3.org/XML/1998/namespace"
PH = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
A_ABOUT, A_NODE, A_RES, A_DT, A_PT, A_ID = (
    "{%s}about" % RDF,
    "{%s}nodeID" % RDF,
    "{%s}resource" % RDF,
    "{%s}datatype" % RDF,
    "{%s}parseType" % RDF,
    "{%s}ID" % RDF,
)
A_LANG = "{%s}lang" % XMLNS
RDF_ATTRS = {A_ABOUT, A_NODE, A_RES, A_DT, A_PT, A_ID, A_LANG}
INVERSES = {
    PH + p
    for p in [
        "isClinicalStudyFor",
        "isDerivedFrom",
        "isPaperFor",
        "pathwayTargetedBy",
        "therapeuticDueTo",
        "geneTargetedBy",
        "diseaseTreatedBy",
        "isAdverseEffectFor",
        "hasBeenContributedTo",
        "interactsWith",
    ]
}


def split(path, n, out):
    import os

    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = b""
        while True:
            line = f.readline()
            if line.startswith(b"  <") and not line.startswith(b"  </"):
                break
            head += line
        first = len(head)
        offs = [first]
        for k in range(1, n):
            f.seek(size * k // n)
            f.readline()
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                if line.startswith(b"  <") and not line.startswith(b"  </"):
                    offs.append(pos)
                    break
        f.seek(0, 2)
        # end = position of closing </rdf:RDF>
        f.seek(max(0, size - 4096))
        tail = f.read()
        idx = tail.rfind(b"</rdf:RDF>")
        end = size - len(tail) + idx
    offs.append(end)
    json.dump({"header": head.decode("utf-8"), "offsets": offs}, open(out, "w"))
    print("header bytes", first, "offsets", offs)


BAD_IRI = re.compile(r'[\x00-\x20<>"{}|^`\\]')


def iri(u):
    if BAD_IRI.search(u):
        u = BAD_IRI.sub(lambda m: "%%%02X" % ord(m.group()), u)
    return "<" + u + ">"


def lit(t, dt=None, lang=None):
    t = (
        (t or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    if dt:
        return f'"{t}"^^{iri(dt)}'
    if lang:
        return f'"{t}"@{lang}'
    return f'"{t}"'


def convert(path, offj, ci, out, drop_inv):
    meta = json.load(open(offj))
    a, b = meta["offsets"][ci], meta["offsets"][ci + 1]
    p = ET.XMLPullParser(events=("start", "end"))
    p.feed(meta["header"].encode("utf-8"))
    o = open(out, "w", encoding="utf-8", buffering=1 << 22)
    W = o.write
    stack = []
    bn = [0]
    n = 0
    dropped = 0
    warn = {}

    def bnode(x):
        return "_:" + re.sub(r"[^A-Za-z0-9]", "", x)

    def newb():
        bn[0] += 1
        return f"_:c{ci}b{bn[0]}"

    def emit(s, pr, ob):
        nonlocal n, dropped
        if drop_inv and pr in INVERSES:
            dropped += 1
            return
        W(f"{s} {iri(pr)} {ob} .\n")
        n += 1

    def handle(ev, el):
        if ev == "start":
            if el.tag == "{%s}RDF" % RDF:
                stack.append(("root",))
                return
            parent = stack[-1]
            if parent[0] in ("root", "prop"):
                at = el.attrib
                if A_ABOUT in at:
                    s = iri(at[A_ABOUT])
                elif A_ID in at:
                    s = iri("#" + at[A_ID])
                elif A_NODE in at:
                    s = bnode(at[A_NODE])
                else:
                    s = newb()
                tag = el.tag[1:].replace("}", "")
                if tag != RDF + "Description":
                    emit(s, RDF + "type", iri(tag))
                for k, v in at.items():
                    if k not in RDF_ATTRS:
                        emit(s, k[1:].replace("}", ""), lit(v))
                if parent[0] == "prop":
                    parent[4].append(s)
                stack.append(("node", s))
            else:
                if A_PT in el.attrib:
                    warn[el.attrib[A_PT]] = warn.get(el.attrib[A_PT], 0) + 1
                stack.append(("prop", parent[1], el.tag[1:].replace("}", ""), el, []))
        else:
            top = stack.pop()
            if top[0] == "prop":
                _, s, pr, e, objs = top
                at = e.attrib
                if objs:
                    for x in objs:
                        emit(s, pr, x)
                elif A_RES in at:
                    emit(s, pr, iri(at[A_RES]))
                elif A_NODE in at:
                    emit(s, pr, bnode(at[A_NODE]))
                else:
                    emit(s, pr, lit(e.text, at.get(A_DT), at.get(A_LANG)))
            if len(stack) == 1:
                el.clear()

    t0 = time.time()
    with open(path, "rb") as f:
        f.seek(a)
        rem = b - a
        while rem > 0:
            buf = f.read(min(1 << 24, rem))
            rem -= len(buf)
            p.feed(buf)
            for ev, el in p.read_events():
                handle(ev, el)
    p.feed(b"</rdf:RDF>")
    for ev, el in p.read_events():
        handle(ev, el)
    o.close()
    print(
        f"chunk {ci}: {n} triples written, {dropped} inverse dropped, warn={warn}, {time.time()-t0:.0f}s"
    )


if __name__ == "__main__":
    if sys.argv[1] == "split":
        split(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        convert(
            sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], "--drop-inverses" in sys.argv
        )
