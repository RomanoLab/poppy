#!/bin/bash
# External validation of a POPPy release with Apache Jena riot + ROBOT (HermiT) + the streaming checks in this folder.
# Needs: java, riot (brew install jena), robot.jar (github.com/ontodev/robot/releases), python3.
# usage: run_checks.sh poppy.nt.gz poppy.rdf work_dir [path/to/robot.jar]
set -uo pipefail
NTGZ=$1; RDF=$2; W=$3; JAR=${4:-$HOME/tools/robot.jar}; HERE=$(cd "$(dirname "$0")" && pwd)
ROBOT="java -jar $JAR"; export JVM_ARGS="-Xmx8G"; mkdir -p "$W"
quiet() { grep -v 'sun.misc.Unsafe\|terminally deprecated\|consider reporting' || true; }
echo "== riot"; riot --count "$NTGZ"
riot --validate --strict "$NTGZ" && echo NT_PASS
riot --validate "$RDF" && echo RDF_PASS
echo "== inputs"; gzip -dc "$NTGZ" > "$W/full.nt"; bash "$HERE/make_inputs.sh" "$W/full.nt" "$W"
echo "== ROBOT"
$ROBOT validate-profile --input "$W/tbox.nt" --profile DL --output "$W/dl_profile_tbox.txt" 2>&1 | quiet; head -1 "$W/dl_profile_tbox.txt"
$ROBOT merge --input "$W/tbox.nt" --input "$W/abox_sample.nt" --output "$W/merged_sample.owl" 2>&1 | quiet
$ROBOT validate-profile --input "$W/merged_sample.owl" --profile DL --output "$W/dl_profile_sample.txt" 2>&1 | quiet; head -1 "$W/dl_profile_sample.txt"
$ROBOT reason --input "$W/merged_sample.owl" --reasoner HermiT --output "$W/reasoned_sample.owl" 2>&1 | quiet
[ -s "$W/reasoned_sample.owl" ] && echo "HermiT: consistent" || echo "HermiT: FAILED"
$ROBOT report --input "$W/tbox.nt" --fail-on none --output "$W/robot_report.tsv" 2>&1 | quiet
echo "== streaming checks"
python3 "$HERE/drcheck.py" "$W/full.nt" "$W/tbox.nt"
python3 "$HERE/dtcheck.py" "$W/full.nt" "$W/tbox.nt" | grep -c MISMATCH || true
python3 "$HERE/iricheck.py" "$W/full.nt"
python3 "$HERE/xmlcount.py" "$RDF"
