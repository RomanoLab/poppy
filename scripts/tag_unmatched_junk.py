#!/usr/bin/env python
"""
tag_unmatched_junk.py — split the still-unmatched residue into junk vs possible-plant.

After classify_nonplants.py + reclassify_unmatched.py, a residue of names resolves in NEITHER
NCBI nor GBIF. Inspection shows it's mostly non-taxa that don't belong in a plant ontology:
pharmacognosy drug names (Herba/Radix/Semen/Cortex ... , often with Latin "seu"), engineered
microbial strains (digits, [brackets], "recombinant"/"engineered"/"strain"/NRRL/ATCC), and
non-plant common names (fish, sponge, scallop, wrack ...). Mixed in is a minority of real plants
with typos ("Cossypium herbaceum" -> Gossypium).

This tags each still-unmatched record:
    junk            structural markers of a drug name / strain / non-plant common name
    possible_plant  a clean 1-3 word capitalised name that MIGHT be a misspelled taxon (kept)

REPORT-FIRST. --remove-junk drops the junk tier from plants_index.json (+.bak). possible_plant
is always kept for your manual review (see the report's tier column).

Heuristics are deliberately conservative: a record is only 'junk' on a positive marker, so the
salvageable binomials fall through to possible_plant rather than being deleted.

USAGE
  python3 scripts/tag_unmatched_junk.py                 # report only (prints samples of each tier)
  python3 scripts/tag_unmatched_junk.py --remove-junk   # report + drop the junk tier
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Latin plant-PART terms that head a pharmacognosy drug name (not a taxon).
_PART_TERMS = {
    "herba",
    "herbae",
    "radix",
    "radices",
    "radicis",
    "rhizoma",
    "rhizomata",
    "rhizomatis",
    "semen",
    "semina",
    "seminis",
    "fructus",
    "flos",
    "flores",
    "floris",
    "folium",
    "folia",
    "folii",
    "cortex",
    "corticis",
    "lignum",
    "caulis",
    "ramulus",
    "ramuli",
    "ramus",
    "cacumen",
    "pericarpium",
    "stamen",
    "stigma",
    "bulbus",
    "tuber",
    "spica",
    "oleum",
    "resina",
    "gummi",
    "thallus",
    "stipes",
    "arillus",
    "pollen",
    "receptaculum",
    "sclerotium",
    "succus",
    "exocarpium",
    "endocarpium",
    "mesocarpium",
    "plumula",
    "calyx",
    "vinum",
    "gemma",
    "pericarpii",
    "herbae",
    "concha",
}
# Non-plant common-name / animal markers. Deliberately EXCLUDES ambiguous words that also
# name plants (e.g. "coral" -> coral tree/coral bells/coral vine), to avoid deleting plants.
_NONPLANT_WORDS = {
    "fish",
    "shark",
    "scallop",
    "mollusk",
    "mollusc",
    "sponge",
    "snail",
    "slug",
    "urchin",
    "jellyfish",
    "anemone",
    "tunicate",
    "ascidian",
    "bryozoan",
    "octopus",
    "squid",
    "mussel",
    "oyster",
    "clam",
    "crab",
    "shrimp",
    "lobster",
    "starfish",
    "whelk",
    "abalone",
    "propolis",
    "venom",
    "gorgonian",
    "nudibranch",
    "lanternshark",
    "mackerel",
    "mahi",
    "cuttlefish",
    "barnacle",
    "tunicates",
}
_STRAIN_WORDS = {
    "recombinant",
    "engineered",
    "strain",
    "mutant",
    "overexpressed",
    "overexpressing",
    "transformant",
    "transgenic",
    "nrrl",
    "atcc",
    "endophytic",
    "endophyte",
    "knockout",
    "plasmid",
    "clone",
    "isolate",
    "unknown",
    "unclassified",
    "unidentified",
    "bacterium",
    "bacteria",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def is_junk(name: str) -> tuple[bool, str]:
    """Return (is_junk, reason)."""
    n = _norm(name)
    low = n.lower()
    toks = low.split()
    if not toks:
        return True, "empty"
    # substring markers catch hyphenated/embedded non-plant words ("Unknown-fungus sp.")
    for s in (
        "unknown",
        "unclassified",
        "unidentified",
        "fungus",
        "fungal",
        "fungi",
        "yeast",
        "mushroom",
    ):
        if s in low:
            return True, f"non-plant/unknown marker ('{s}')"
    if re.search(r"\d", n):
        return True, "contains digits (strain/catalog id)"
    if re.search(r"[\[\]()]", n):
        return True, "contains brackets/parens (strain designation)"
    if " seu " in f" {low} " or " et " in f" {low} ":
        return True, "Latin drug phrase (seu/et)"
    if toks[0] in _PART_TERMS:
        return True, f"pharmacognosy part-name ('{toks[0]}')"
    if any(w in _NONPLANT_WORDS for w in toks):
        return True, "non-plant common-name token"
    if any(w in _STRAIN_WORDS for w in toks):
        return True, "microbial strain / unknown marker"
    # NOTE: no "lowercase" or "N words" rule — those wrongly flag real plant common names
    # ("common myrtle", "star fruit", "snap bean"). We only tag on positive non-plant markers.
    return False, ""


def load_still_unmatched(report_path: Path):
    out = []
    with open(report_path, encoding="utf-8") as fh:
        for row in csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"):
            if row.get("new_status") == "still_unmatched":
                out.append((row.get("organism_id", ""), row.get("scientific_name", "")))
    return out


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument(
        "--report-in", default=str(REPO / "data" / "enrichment" / "unmatched_reclassified.tsv")
    )
    ap.add_argument("--out", default=str(REPO / "data" / "enrichment" / "unmatched_junk_tags.tsv"))
    ap.add_argument("--remove-junk", action="store_true")
    args = ap.parse_args()

    residue = load_still_unmatched(Path(args.report_in))
    print(f"Still-unmatched records to tag: {len(residue):,}")

    rows, junk_ids = [], set()
    n_junk = 0
    for oid, sci in residue:
        junk, reason = is_junk(sci)
        tier = "junk" if junk else "possible_plant"
        if junk:
            n_junk += 1
            junk_ids.add(oid)
        rows.append({"organism_id": oid, "scientific_name": sci, "tier": tier, "reason": reason})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = ["organism_id", "scientific_name", "tier", "reason"]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(
            "# tiers: junk (structural non-taxon markers) | possible_plant (kept for review)\n"
        )
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(residue) or 1
    print(f"\n  junk           : {n_junk:,} ({100*n_junk/total:.1f}%)")
    print(f"  possible_plant : {len(residue)-n_junk:,} ({100*(len(residue)-n_junk)/total:.1f}%)")
    print(f"  report: {out}")
    print("\n  --- sample JUNK (to be removed) ---")
    for r in [r for r in rows if r["tier"] == "junk"][:12]:
        print(f"    {r['scientific_name'][:45]:45s}  [{r['reason']}]")
    print("  --- sample POSSIBLE_PLANT (kept for review) ---")
    for r in [r for r in rows if r["tier"] == "possible_plant"][:12]:
        print(f"    {r['scientific_name']}")

    if not args.remove_junk:
        print(
            "\n[report only] plants_index.json NOT modified. Rerun with --remove-junk to drop the junk tier."
        )
        return 0

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    keep = [rec for rec in records if rec.get("id", "") not in junk_ids]
    removed = len(records) - len(keep)
    backup = plants_path.with_suffix(plants_path.suffix + ".bak")
    shutil.copy2(plants_path, backup)
    plants_path.write_text(json.dumps(keep, ensure_ascii=False, separators=sep))
    print(f"\nRemoved {removed:,} junk records; kept {len(keep):,}. Backup at {backup}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
