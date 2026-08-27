# Molecular layer: genes, targets, pathways, diseases

Reproducible scripts that add the gene/target/pathway/disease layer to POPPy and wire it to
plants and compounds, so `plant / compound -> gene -> pathway / disease` resolves. Genes are
keyed by the gene-stripped ComptoxAI symbol (`jdr.bio/ontologies/comptox.owl#<symbol>`).

## Scripts

| Script | Output (data/enrichment/, gitignored) | Source |
|---|---|---|
| `ingest_genes_comptox.py` | `poppy_genes.ttl` (+ `--interactions-only` -> `poppy_gene_interactions.ttl`) | `comptox_populated.rdf` (ComptoxAI, Box) |
| `ingest_targets_cmaup.py` | `poppy_targets.ttl` (plant->gene) | CMAUP Plants/Plant_Ingredient/Ingredient_Target/Targets + plants_index.json |
| `ingest_compound_targets_cmaup.py` | `poppy_compound_targets.ttl` (compound->gene) | CMAUP Ingredients_All (InChIKey) + Ingredient_Target/Targets + ontology InChIKeys |
| `ingest_pathways_comptox.py` | `poppy_pathways.ttl` | `comptox_populated.rdf` |
| `ingest_diseases_doid.py` | `poppy_diseases.ttl` | Jensen DISEASES (`--channel knowledge`) + DOID doid.obo (downloaded) |
| `merge_modules.py` | merged ontology | stream-splices TTL modules into a multi-GB RDF/XML target |

## Run

```
python3 scripts/ingest_genes_comptox.py --comptox comptox_populated.rdf --out data/enrichment/poppy_genes.ttl
python3 scripts/ingest_genes_comptox.py --comptox comptox_populated.rdf --interactions-only --out data/enrichment/poppy_gene_interactions.ttl
python3 scripts/ingest_targets_cmaup.py --cmaup-dir <cmaup> --comptox comptox_populated.rdf --plants-index website/data/plants_index.json --out data/enrichment/poppy_targets.ttl
python3 scripts/ingest_compound_targets_cmaup.py --ontology poppyontology.rdf --cmaup-dir <cmaup> --comptox comptox_populated.rdf --out data/enrichment/poppy_compound_targets.ttl
python3 scripts/ingest_pathways_comptox.py --comptox comptox_populated.rdf --out data/enrichment/poppy_pathways.ttl
python3 scripts/ingest_diseases_doid.py --comptox comptox_populated.rdf --channel knowledge --out data/enrichment/poppy_diseases.ttl
python3 scripts/merge_modules.py --target poppyontology.rdf --add data/enrichment/poppy_*.ttl --out poppyontology_molecular.rdf
```
