#!/usr/bin/env python3
"""retype_duke_nonchemicals.py — Dr. Duke's FARMACY lists enzymes, elements and nutrient/compound classes as
constituents. Retype those name-only nodes as phyto:NonCompoundConstituent and move their plant links from
hasCompound/hasCompoundPerDrDuke to phyto:hasReportedConstituent. usage: in.nt out.nt report.tsv"""

import sys
import re
import collections

PH = "<http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
L = "<http://www.w3.org/2000/01/rdf-schema#label>"
T = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
ELEM = set(
    """ALUMINUM ALUMINIUM IRON CALCIUM MAGNESIUM POTASSIUM SODIUM ZINC COPPER MANGANESE PHOSPHORUS SULFUR SELENIUM BORON CHROMIUM COBALT
NICKEL LEAD CADMIUM MERCURY ARSENIC SILICON STRONTIUM BARIUM IODINE FLUORINE CHLORINE LITHIUM MOLYBDENUM TIN TITANIUM VANADIUM SILVER GOLD
PLATINUM RUBIDIUM BROMINE CESIUM ASH WATER FAT FIBER PROTEIN CARBOHYDRATES KILOCALORIES CALORIES ENERGY SUGARS STARCH MUCILAGE GUM RESIN
TANNIN TANNINS ALKALOIDS FLAVONOIDS SAPONINS ESSENTIAL-OIL EO OIL PECTIN CELLULOSE LIGNIN PHYTOSTEROLS GLYCOSIDES STEROLS TERPENES
POLYPHENOLS ALPHA-GLUCAN BETA-GLUCAN NITROGEN AMINO-ACIDS FATTY-ACIDS""".split()
)


def kind(n):
    u = re.sub(r"[^A-Z0-9-]", "", n.upper().replace(" ", "-"))
    if u in ELEM or u.rstrip("S") in ELEM:
        return "element_or_nutrient_class"
    if re.search(r"(ASE|ASES)$", u):
        return "enzyme"
    if re.search(r"-(COMPOUNDS|DERIVATIVES?)$", u):
        return "compound_class"
    return None


inp, out, rep = sys.argv[1:4]
lab = {}
for l in open(inp):
    s, p, o = l.split(" ", 2)
    if p == L and s.startswith(PH + "Chemical_") and "#Chemical_ik_" not in s:
        lab[s] = o[1 : o.rfind('"')]
bad = {s: kind(n) for s, n in lab.items() if kind(n)}
c = collections.Counter()
with open(out, "w", buffering=1 << 22) as f:
    for l in open(inp):
        s, p, o = l.split(" ", 2)
        ob = o[:-3]
        if ob in bad and p in (PH + "hasCompound>", PH + "hasCompoundFamilyUnreplicated>"):
            c["link_moved"] += 1
            f.write(f"{s} {PH}hasReportedConstituent> {ob} .\n")
            continue
        if ob in bad and p in (
            PH + "hasCompoundPerDrDuke>",
            PH + "hasCompoundPerCMAUP>",
            PH + "hasCompoundPerCOCONUT>",
        ):
            continue
        if s in bad and p == T and ob == PH + "ChemicalConcept>":
            f.write(f"{s} {T} {PH}NonCompoundConstituent> .\n")
            f.write(f'{s} {PH}constituentKind> "{bad[s]}" .\n')
            continue
        f.write(l)
    S = PH + "hasReportedConstituent>"
    f.write(
        f'{S} {T} <{OWL}ObjectProperty> .\n{S} <{RDFS}label> "has reported constituent (non-compound)" .\n'
    )
    f.write(
        f'{S} <{RDFS}comment> "Dr. Duke\'s FARMACY entry that is an enzyme, element, nutrient or compound class rather than a defined compound." .\n'
    )
    C = PH + "NonCompoundConstituent>"
    f.write(
        f'{C} {T} <{OWL}Class> .\n{C} <{RDFS}label> "Non-compound constituent (enzyme, element, nutrient class)" .\n'
    )
    f.write(f"{PH}constituentKind> {T} <{OWL}DatatypeProperty> .\n")
open(rep, "w").write(
    "iri\tlabel\tkind\n" + "".join(f"{s[1:-1]}\t{lab[s]}\t{k}\n" for s, k in sorted(bad.items()))
)
print("retyped", len(bad), collections.Counter(bad.values()), dict(c))
