#!/usr/bin/env bash
# fetch_inputs.sh — download the public build inputs for scripts/rebuild_ontology.py
#
# Pulls everything that has a stable direct URL into data/raw/ (idempotent: skips files
# already present). Two inputs cannot be auto-fetched (interactive/zip portals) and one
# is a DB, not a file — those are printed as manual TODOs at the end.
#
# Usage:
#   bash scripts/fetch_inputs.sh                 # CMAUP + COCONUT 2.0 SDF
#   bash scripts/fetch_inputs.sh --with-chebi    # also ChEBI (only needed for the optional
#                                                #   ChEBI stage, which is currently passthrough)
#   DATA_DIR=/some/dir bash scripts/fetch_inputs.sh
#
# Sources verified 2026-06-23. URLs drift — see data/SOURCES.md if one 404s.
set -euo pipefail

DATA_DIR="${DATA_DIR:-data/raw}"
WITH_CHEBI=0
[[ "${1:-}" == "--with-chebi" ]] && WITH_CHEBI=1
mkdir -p "$DATA_DIR"

dl() {  # dl <url> <dest-filename>
  local url="$1" name="$2" dest="$DATA_DIR/$2"
  if [[ -s "$dest" ]]; then
    echo "  [skip] $name (already present, $(du -h "$dest" | cut -f1))"
    return
  fi
  echo "  [get ] $name"
  curl -fL --retry 3 --progress-bar -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
}

echo "==> CMAUP v2.0  (https://bidd.group/CMAUP/download.html)"
CMAUP="https://bidd.group/CMAUP/downloadFiles"
for f in \
  CMAUPv2.0_download_Plants.txt \
  CMAUPv2.0_download_Ingredients_All.txt \
  CMAUPv2.0_download_Targets.txt \
  CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt \
  CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt \
  CMAUPv2.0_download_Plant_Human_Disease_Associations.txt ; do
  dl "$CMAUP/$f" "$f"
done

echo "==> COCONUT 2.0 — full 2D SDF  (https://coconut.naturalproducts.net/download)"
SDF="coconut_sdf_2d-06-2026.sdf"
if [[ -s "$DATA_DIR/$SDF" ]]; then
  echo "  [skip] $SDF (already present, $(du -h "$DATA_DIR/$SDF" | cut -f1))"
else
  dl "https://coconut.s3.uni-jena.de/prod/downloads/2026-06/coconut_sdf_2d-06-2026.zip" \
     "coconut_sdf_2d-06-2026.zip"
  echo "  [unzip] coconut_sdf_2d-06-2026.zip"
  unzip -o "$DATA_DIR/coconut_sdf_2d-06-2026.zip" -d "$DATA_DIR" >/dev/null
  # the archive may nest the .sdf in a folder — normalize to the expected flat name
  if [[ ! -s "$DATA_DIR/$SDF" ]]; then
    found="$(find "$DATA_DIR" -name '*.sdf' | head -1 || true)"
    [[ -n "$found" ]] && mv "$found" "$DATA_DIR/$SDF"
  fi
  echo "  [ok  ] $SDF ($(du -h "$DATA_DIR/$SDF" | cut -f1))"
fi

echo "==> NCBI taxonomy dump (offline organism validation; ~75 MB)"
TAXDIR="$DATA_DIR/taxdump"
if [[ -s "$TAXDIR/names.dmp" && -s "$TAXDIR/nodes.dmp" ]]; then
  echo "  [skip] taxdump (names.dmp + nodes.dmp present)"
else
  mkdir -p "$TAXDIR"
  dl "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdmp.zip" "taxdump/taxdmp.zip"
  echo "  [unzip] taxdmp.zip -> names.dmp, nodes.dmp"
  unzip -o "$TAXDIR/taxdmp.zip" names.dmp nodes.dmp -d "$TAXDIR" >/dev/null
fi

if [[ "$WITH_CHEBI" == "1" ]]; then
  echo "==> ChEBI (optional; only for the ChEBI alignment stage, currently passthrough)"
  dl "https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi_lite.owl" "chebi_lite.owl"
fi

cat <<'EOF'

==> MANUAL — cannot auto-fetch:

  1) Dr. Duke's (6 CSVs: ACTIVITIES, AGGREGAC, CHEMICALS, DOSAGE, ETHNOBOT, REFERENCES)
     Download "Duke-Source-CSV.zip" from Ag Data Commons / USDA, unzip into data/raw/:
       https://agdatacommons.nal.usda.gov/articles/dataset/Dr_Duke_s_Phytochemical_and_Ethnobotanical_Databases/24660351
     The zip's table CSVs map 1:1 to the expected filenames (uppercase .csv).

  2) ChEMBL drug mechanisms -> data/raw/ChEMBL_drug_mechanisms.csv
     Easiest: https://www.ebi.ac.uk/chembl/explore/drug_mechanisms/ -> export/download as CSV.
     (Must contain a SMILES column + Target Name + Action Type.)

==> NOT A FILE — comes from the database (no download):

  * COCONUT BASE plants & compounds: PMACS 'opendata' DB, coconut.* schema.
    The script reads it directly over your VPN connection (stages base_plants,
    coconut_chemicals). Set PMACS_USER / ROMANO_DB_PASSWORD and connect Penn VPN.
  * DrugCentral: public read-only mirror (unmtid-dbs.net:5433) — no setup needed.

Next:  conda activate poppy && python scripts/rebuild_ontology.py --check
EOF
