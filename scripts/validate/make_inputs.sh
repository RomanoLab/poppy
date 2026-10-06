#!/bin/bash
# Build the small validation inputs from a full POPPy N-Triples release:
#   <out>/tbox.nt        schema only (classes/properties/ontology header + all blank-node axioms)
#   <out>/abox_sample.nt per predicate: first 20 + every 613th triple (max 80), plus rdf:type of the nodes used
# usage: make_inputs.sh poppy.nt out_dir
set -euo pipefail
NT=$1; OUT=$2; mkdir -p "$OUT"
LC_ALL=C grep -E '^<[^>]*> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#(Class|ObjectProperty|DatatypeProperty|AnnotationProperty|Ontology|DataRange)> \.$' "$NT" \
  | cut -d' ' -f1 | sort -u > "$OUT/schema_subjects.txt"
LC_ALL=C awk 'NR==FNR{s[$1];next} ($1 in s) || /^_:/' "$OUT/schema_subjects.txt" "$NT" > "$OUT/tbox.nt"
LC_ALL=C awk 'NR==FNR{s[$1];next} !($1 in s) && !/^_:/ && $2!="<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>" {
    k=$2; if (c[k]<20 || (FNR%613==0 && c[k]<80)) {c[k]++; print; n[$1]; if ($3 ~ /^</) n[$3]} }
  END {for (k in n) print k > "/dev/stderr"}' "$OUT/schema_subjects.txt" "$NT" > "$OUT/abox_sample.nt" 2> "$OUT/sample_nodes.txt"
LC_ALL=C awk 'NR==FNR{s[$1];next} ($1 in s) && $2=="<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"' "$OUT/sample_nodes.txt" "$NT" >> "$OUT/abox_sample.nt"
wc -l "$OUT/tbox.nt" "$OUT/abox_sample.nt"
