# POPPy ontology v2 rebuild (phase 1 + phase 2), 2026-10-01

Input:  Box `Romano_Lab_Oresta/poppyontology_molecular_enriched.rdf` (4.17 GB, 30.77M triples) — unchanged.
Output: Box `Romano_Lab_Oresta/POPPy_v2_working/poppy_phase2.rdf` (809 MB) + `.nt.gz` (93 MB), 6.67M triples.
All steps stream; peak RAM < 2 GB; each step < 1 min.

```bash
S=scripts; W=~/work; RDF=~/Box/Romano_Lab_Oresta/poppyontology_molecular_enriched.rdf
python3 $S/rdfxml2nt.py split "$RDF" 6 $W/offsets.json
for i in 0 1 2 3 4 5; do python3 $S/rdfxml2nt.py convert "$RDF" $W/offsets.json $i $W/part$i.nt --drop-inverses; done
cat $W/part*.nt > $W/all.nt
# phase 1: in-file fixes
python3 $S/patch_phase1.py collect $W/all.nt $W/state.pkl --taxdump data/raw/taxdump/nodes.dmp \
   --classification data/enrichment/plant_classification.tsv --junk data/enrichment/unmatched_junk_tags.tsv
python3 $S/patch_phase1.py apply $W/all.nt $W/state.pkl $W/p1raw.nt --map data/patches/phase1_iri_map.tsv --stats data/patches/phase1_stats.json
LC_ALL=C sort -u $W/p1raw.nt -o $W/p1.nt && python3 $S/finalize_nt.py $W/p1.nt $W/poppy_phase1.nt $W/poppy_phase1.rdf
# phase 2: rebuild occurrences / trials / targets from sources
python3 $S/build_phase2.py index  $W/poppy_phase1.nt $W/idx2.pkl --taxdump data/raw/taxdump/nodes.dmp
python3 $S/build_phase2.py build  $W/idx2.pkl $W/add2.nt --cmaup-dir ~/Downloads --website website/data --duke data/raw \
   --classification data/enrichment/plant_classification.tsv
python3 $S/build_phase2.py filter $W/poppy_phase1.nt $W/add2.nt $W/base2.nt
LC_ALL=C sort -u $W/base2.nt $W/add2.nt -o $W/p2.nt
python3 $S/finalize_nt.py $W/p2.nt $W/p2f.nt /dev/null
python3 $S/prune_orphans.py $W/p2f.nt $W/p2p.nt data/patches/phase2_orphan_compounds_removed.tsv
python3 $S/finalize_nt.py $W/p2p.nt $W/poppy_phase2.nt $W/poppy_phase2.rdf
python3 $S/audit_nt.py $W/poppy_phase2.nt data/patches/phase2_audit.json
```

CMAUP inputs (in ~/Downloads): Ingredients_All, Plants, Plant_Ingredient_Associations_allIngredients (2),
Plant_Clinical_Trials_Associations (1), Ingredient_Target_Associations_ActivityValues_References, Targets.

## Modelling changes agents/queries must know
- `hasCompound` = union of `hasCompoundPerCMAUP`, `hasCompoundPerCOCONUT`, `hasCompoundPerDrDuke` (sub-properties carry provenance).
- `hasClinicalStudy`: on a Plant = trial of the plant itself (CMAUP "plant" association, 739 edges);
  on a compound = compound is the intervention (16,411 edges). Plants are NOT linked to trials of their constituents.
- `compoundTargetsGene` (12,495 pairs) + `BioactivityMeasurement` nodes (activityType/Relation/Value/Unit, PMID via hasReference).
- `targetsGene` (plant→gene) is no longer stored: owl:propertyChainAxiom hasCompound ∘ compoundTargetsGene.
- Compound IRIs `Chemical_ik_<InChIKey>`; name-only Dr. Duke compounds remain `Chemical_<CHEMID>` (no structure).
- `heuristicPhytochemicalClass` literal replaces the old rdf:type classes (deprecated).
- `MechanismOfAction_*` (was TherapeuticEffect_INHIBITOR…), `ProteinTarget_*` (was TargetedPathway_*), mapped to genes via skos:exactMatch where possible.
- Materialized inverse properties are not stored (declared with owl:inverseOf).

## Known gaps
- 123,679 compounds lack SMILES and/or a name (website-build compounds came with InChIKey only). Run
  `scripts/fetch_pubchem_smiles_names.py` on a networked machine; merge step to follow.
- COCONUT-only occurrences include some implausible links (e.g. paclitaxel in Garcinia); filter by source if needed.
- Plant–disease (CMAUP Plant_Human_Disease_Associations) not loaded; DISEASES confidence scores not stored.
- website/data/ still reflects the old build — regenerate from poppy_phase2.

## v2.1 (2026-10-03) — on top of poppy_phase2.nt
```bash
python3 $S/fill_from_coconut.py $W/poppy_phase2.nt ~/Downloads/coconut_sdf_2d-10-2026.zip $W/add_coconut.nt $W/label_replace.txt
python3 $S/enrich_v21.py $W/poppy_phase2.nt $W/idx2.pkl $W/add_v21.nt --taxdump data/raw/taxdump/nodes.dmp \
   --phda "~/Downloads/CMAUPv2.0_download_Plant_Human_Disease_Associations (1).txt" \
   --cmaup-plants ~/Downloads/CMAUPv2.0_download_Plants.txt --report data/patches/v21_report.json
# drop rdfs:label of subjects in label_replace.txt (and "No Data" labels) from poppy_phase2.nt, then:
LC_ALL=C sort -u base.nt $W/add_coconut.nt $W/add_v21.nt -o v21.nt
python3 $S/retype_duke_nonchemicals.py v21.nt v21b.nt data/patches/v21_duke_noncompounds.tsv
LC_ALL=C sort -u v21b.nt -o v21b.nt && python3 $S/finalize_nt.py v21b.nt poppy_v21.nt poppy_v2.1.rdf
python3 $S/build_website_data.py poppy_v21.nt website/data
```
Added in v2.1: SMILES/IUPAC/NPClassifier/ClassyFire/COCONUT IDs from COCONUT 2.0 (10-2026); placeholder labels
"<formula> (CNP…)" flagged phyto:labelIsPlaceholder for 18,942 unnamed NPs; phyto:taxonomicFamily/Genus;
phyto:hasCompoundFamilyUnreplicated (94,972 COCONUT-only links whose plant is the only member of its family with that
compound — weak heuristic); CMAUP plant–disease associations (associatedWithDisease + 4 evidence sub-properties,
1,351 ICD-11 disease nodes, 138 closeMatch to DOID); 318 Dr. Duke's enzymes/elements/nutrient classes retyped
NonCompoundConstituent with links moved to hasReportedConstituent.

## v2.2 (2026-10-04) — PubChem names
```bash
# on the Mac (needs internet; ~1.5 h, resumable)
python3 scripts/fetch_pubchem_smiles_names.py data/patches/compounds_needing_names.tsv data/patches/pubchem_fill.tsv
# then
python3 scripts/apply_pubchem_names.py poppy_v21.nt data/patches/pubchem_fill.tsv v22.nt
LC_ALL=C sort -u v22.nt -o v22.nt && python3 scripts/finalize_nt.py v22.nt poppy_v22.nt poppy_v2.2.rdf
python3 scripts/build_website_data.py poppy_v22.nt website/data --keep-names website/data/plants_index.json  # keeps curated common names + synonyms
```
Result: 20,908 queried; 15,076 found in PubChem; 14,743 labels replaced; 14,723 IUPAC names added.
Remaining: 5,243 "<formula> (CNP…)" placeholder labels (not in PubChem), 923 InChIKey-only labels.

## Files in data/patches
Large lists are gzipped: `phase1_iri_map.tsv.gz` (old->new IRIs), `phase2_orphan_compounds_removed.tsv.gz`,
`pubchem_fill.tsv.gz` (gunzip before passing to apply_pubchem_names.py). `compounds_needing_names.tsv` is the
PubChem worklist. Reports: phase1/phase2/v21 audit + stats JSON, v21_duke_noncompounds.tsv.

## v2.3 (2026-10-05) — plant rescue + descriptors for all compounds
```bash
# candidates = plants in the pre-v2.2 website index missing from v2.2 (by id and binomial), classified as
# rescue_ncbi_species / rescue_ncbi_genus / rescue_typo_corrected / reject_* (see data/patches/v23_rescue_decisions.tsv)
python3 scripts/rescue_plants.py poppy_v22.nt dropped_classified.json up_web idx2.pkl data/raw/taxdump/nodes.dmp \
    add_rescue.nt new_compounds.nt v23_rescue_decisions.tsv     # up_web = plant_edges/compounds shards of commit c84101f
python3 scripts/fill_from_coconut.py new_compounds.nt ~/Downloads/coconut_sdf_2d-10-2026.zip add_newc_coconut.nt /dev/null
python3 scripts/compute_missing_descriptors.py desc_input.tsv add_desc.nt   # IRI<TAB>SMILES for compounds lacking phyto:mw
cat add_rescue.nt new_compounds.nt add_newc_coconut.nt add_desc.nt | LC_ALL=C sort -u > adds.nt
LC_ALL=C sort -m -u poppy_v22.nt adds.nt > v23.nt && python3 scripts/finalize_nt.py v23.nt poppy_v23.nt poppy_v2.3.rdf
python3 scripts/build_website_data.py poppy_v23.nt website/data --keep-names <current + previous plants_index merged>
```
Result: 1,315 plants rescued (1,199 NCBI genus match, 1 NCBI species, 115 genus-typo corrections of which 111 merged
into existing plants); 595 rejected (316 genus not an NCBI plant genus, 236 sp./spp./cf., 40 pharmacognosy drug names,
3 other). 7,426 occurrence links and 730 compounds restored. RDKit descriptors added for 124,719 compounds
(32 SMILES unparseable). v2.3: 11,866,566 triples; 40,109 plants with compounds; 208,939 compounds (183,868 with descriptors).

## v2.4 (2026-10-05) — literature evidence + website evidence panel
```bash
# COCONUT per-compound DOIs: {InChIKey: [doi,...]} extracted from the COCONUT 2.0 SDF `dois` field
python3 scripts/rebuild_papers.py poppy_v23.nt coconut_dois.json data/raw add2.nt.drop.pkl base.nt add.nt
LC_ALL=C sort -u add.nt -o add.nt && LC_ALL=C sort -m -u base.nt add.nt > v24.nt
python3 scripts/finalize_nt.py v24.nt poppy_v24.nt poppy_v2.4.rdf
python3 scripts/build_website_data.py poppy_v24.nt website/data --keep-names <merged plants_index>
python3 scripts/build_evidence_data.py poppy_v24.nt website/data     # data/evidence/{plants,compounds}/<djb2>.json
python3 scripts/cache_bust.py
```
- v1 hasPaper links removed (116,782; untraceable, e.g. one 1968 paper on 2,389 compounds).
- Compound literature: 433,588 links to 73,549 DOIs from COCONUT 2.0 (hasPaperPerCOCONUT).
- Dr. Duke's citations: 714 references with full citation text, linked to plant and compound only when the FARMACY
  occurrence is in the ontology (hasPaperPerDrDuke). Codes not in the local REFERENCES.csv (most of them) and
  non-citations ("personal files", "see species file", bare journal names) are skipped.
- CMAUP bioactivity references: only IDs >= 5,000,000 are treated as PubMed IDs (3,962). 21,677 smaller IDs, labelled
  "PMID" by CMAUP but behaving like ChEMBL assay IDs, are kept as hasReferenceText without a PubMed link.
- Explore page: Evidence panel (clinical trials -> clinicaltrials.gov, bioactivity -> PubMed, literature -> doi.org /
  citation text), first 10 per block with "Show all"; compound rows now open in place.
v2.4: 12,849,926 triples.

## v2.4.1 (2026-10-06) — validation fixes (schema only)
v2.4 was checked with Apache Jena `riot`, ROBOT 1.9.11 (`validate-profile --profile DL`, `report`, `reason` with
HermiT/ELK) and full-file streaming checks. They found: 507 DOI IRIs with characters illegal in IRIs (SICI DOIs with
`< > [ ]`); `commonName`/`scientificSynonym` punned as data + annotation properties and `skos:*` used undeclared
(not OWL 2 DL); 9 RDKit count descriptors declared `xsd:double` but stored as `xsd:integer` (inconsistent under
HermiT); `hasCommonName` domain that would re-infer the 318 non-compound constituents as `ChemicalConcept`;
two contradictory unused properties (`interactsWith`, `hasInteractionsWith`); orphan OWL 1 `DataRange` lists; an
empty blank-node label; logical axioms on deprecated classes; 15 missing labels; no title/description/licence.
```bash
python3 scripts/patch_v241.py poppy_v2.4.nt.gz poppy_v241.nt      # 93 triples dropped, 84 added, 507 IRIs encoded
python3 scripts/finalize_nt.py poppy_v241.nt /dev/null poppy_v2.4.1.rdf
gzip -c poppy_v241.nt > poppy_v2.4.1.nt.gz
python3 scripts/validate/verify241.py poppy_v2.4.1.nt.gz            # every fix present / defect absent
bash scripts/validate/run_checks.sh poppy_v2.4.1.nt.gz poppy_v2.4.1.rdf ~/work/val   # riot + ROBOT/HermiT + streaming checks
```
Also added: `owl:AllDisjointClasses` for the top-level domains, Gene/Pathway/ProteinTarget/DiseaseConcept, and
ClinicalTrial/ScientificPaper/BioactivityMeasurement; `dcterms:license` CC BY-NC 4.0; `phyto:Gene`
IAO:0100001 → `cmptx:Gene`; `hasReportedConstituent` domain Plant / range NonCompoundConstituent.
The only data changes are the 507 re-encoded DOI IRIs and 46 `heuristicPhytochemicalClass "Unknown"` values removed
from non-compound constituents.

Results (reports in `data/patches/v241_validation/`, before/after): riot strict N-Triples + RDF/XML pass;
12,849,917 triples; OWL 2 DL profile pass (schema, and schema + 16,976-triple ABox sample); HermiT consistent on
schema + sample with disjointness; ROBOT report 0 errors (127 `missing_definition` warnings);
`drcheck.py` 0 disjointness/domain/range violations over 13,569,594 checks; `dtcheck.py` 0 datatype mismatches;
`iricheck.py` 0 invalid IRIs. HermiT was not run over all 12.85M triples — full-graph conformance rests on the
streaming checks. `website/downloads/poppy-schema.rdf` regenerated from the v2.4.1 schema (586 triples).
Browse data (`website/data`) is unchanged apart from the version string in `meta.json`.

## v2.5 (2026-10-06) — plant deduplication, licence module, UniChem cross-references
```bash
gzip -dc poppy_v2.4.1.nt.gz > poppy_v241.nt
python3 scripts/dedup_plants_v25.py poppy_v241.nt v25a.nt plant_merge_map.tsv
python3 scripts/split_licence_module_v25.py v25a.nt v25b_core.nt module.nt unichem_worklist.tsv
# on a machine with internet (~2.5 h at 8 workers, resumable):
python3 scripts/fetch_unichem_xrefs.py unichem_worklist.tsv unichem_cache.jsonl --workers 8
python3 scripts/apply_unichem_xrefs.py unichem_worklist.tsv unichem_cache.jsonl xrefs.nt
python3 scripts/assemble_v25.py v25b_core.nt xrefs.nt poppy_v25.nt \
    --replace data/patches/v25_validation/v25_tautomer_descriptor_fix.nt
python3 scripts/finalize_nt.py poppy_v25.nt /dev/null poppy_v2.5.rdf && gzip -c poppy_v25.nt > poppy_v2.5.nt.gz
LC_ALL=C sort -u module.nt > poppy_v2.5_drugcentral_chembl.nt
python3 scripts/finalize_nt.py poppy_v2.5_drugcentral_chembl.nt /dev/null poppy_v2.5_drugcentral_chembl.rdf
bash scripts/validate/make_inputs.sh poppy_v25.nt val
python3 scripts/validate/drcheck.py poppy_v25.nt,poppy_v2.5_drugcentral_chembl.nt val/tbox.nt   # also dtcheck/iricheck
python3 scripts/build_website_data.py poppy_v25.nt website/data --keep-names <previous plants_index.json>
python3 scripts/build_evidence_data.py poppy_v25.nt website/data
```
- Plant dedup: nodes sharing genus + specific epithet (author strings and case ignored) merged, 1,980 into 1,876;
  infraspecific names (ssp./var./f./cv./race/strain…), hybrids, aggregates, "sp./cf." and multi-taxon labels never
  merged; 11 pairs with conflicting NCBI taxa kept apart. Merged labels -> skos:altLabel. Map:
  `data/patches/v25_plant_merge_map.tsv.gz`. 43,828 plant nodes, 39,941 with compounds; 1,013,231 plant-compound links.
- Licence module (CC BY-SA 4.0, `poppy_v2.5_drugcentral_chembl.*`, 9,987 triples): ProteinTarget (1,334) and
  MechanismOfAction (18) nodes, targetsProtein 3,208, hasMechanismOfAction 307, hasATC 745. 150 empty legacy
  TherapeuticEffect nodes dropped. ComptoxAI content stays in the core pending the author's licence OK.
- UniChem: 154,787 compounds queried, 137,470 got >=1 new xref (118,763 new triples after removing ones already
  present). Compounds with a PubChem/ChEMBL/ChEBI/HMDB/DrugBank xref: 168,080 of 183,900 with structure (91.4%);
  PubChem 166,999, ChEMBL 37,396, ChEBI 18,355, HMDB 8,100, DrugBank 1,529, KEGG 0.
- 7 compounds had two tautomeric SMILES and therefore two descriptor values: descriptors and canonical SMILES
  recomputed from the RDKit canonical tautomer (RDKit 2026.03.6).
- Validation: DL profile pass (schema; schema + per-predicate sample + full module; module alone), HermiT consistent,
  ROBOT report 0 errors; drcheck 0 violations / 13,544,235 checks; dtcheck 0; iricheck 0; RDF/XML well-formed,
  12,933,298 triples. riot to be re-run by the user. Reports: `data/patches/v25_validation/`.
