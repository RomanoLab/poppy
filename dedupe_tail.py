import sys
IN = sys.argv[1]
MARK = b'<owl:AnnotationProperty rdf:about="http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#commonName"/>'
CLOSE = b'</rdf:RDF>'
f = open(IN, 'r+b')
f.seek(0, 2); size = f.tell()
tr = min(size, 40*1024*1024)
f.seek(size - tr); tail = f.read(tr)
pos = []; i = 0
while True:
    j = tail.find(MARK, i)
    if j < 0: break
    pos.append(j); i = j + 1
if len(pos) >= 2:
    cut = size - tr + pos[-1]
    f.seek(cut); f.truncate(); f.write(CLOSE + b'\n')
    print("removed duplicate fragment (markers found: %d)" % len(pos))
else:
    print("nothing to fix (markers found: %d)" % len(pos))
f.close()
