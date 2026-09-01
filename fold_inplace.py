import sys
IN, FRAG = sys.argv[1], sys.argv[2]
REMOVE = [b'Organism_227"', b'Organism_26781"', b'Organism_21610"', b'Organism_52857"', b'Organism_57584"']
CLOSE = b'</rdf:RDF>'
f = open(IN, 'r+b')
ranges = []; skip = False; off = 0
while True:
    line = f.readline()
    if not line: break
    s = off; e = off + len(line); off = e
    if skip:
        if b'</rdf:Description>' in line:
            skip = False
            ranges[-1] = (ranges[-1][0], e)
        continue
    hit = any(p in line for p in REMOVE)
    if hit and b'<rdf:Description rdf:about=' in line:
        ranges.append((s, e))
        if b'</rdf:Description>' not in line: skip = True
        continue
    if hit and b'rdf:resource=' in line:
        ranges.append((s, e))
        continue
nb = 0
for s, e in ranges:
    f.seek(s); f.write(b' ' * (e - s)); nb += 1
f.seek(0, 2); size = f.tell()
tr = min(size, 65536); f.seek(size - tr); tail = f.read(tr)
idx = tail.rfind(CLOSE)
close_off = size - tr + idx
f.seek(close_off); f.truncate()
frag = open(FRAG, 'rb').read()
f.write(frag); f.write(CLOSE + b'\n'); f.close()
sys.stderr.write(f"blanked_ranges={nb}\n")
