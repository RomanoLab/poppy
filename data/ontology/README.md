# data/ontology/

Ontology resources used by POPPy.

## Files

- `poppystructure.rdf`
  - **What it is:** the core POPPy ontology scaffold / structure.
  - **How it is produced:** edited manually in Protégé and exported as RDF/XML.
  - **Role in pipeline:** treated as a source input that other scripts/configs build on.

## Editing / update workflow (Protégé)

When updating `poppystructure.rdf`:

1. Open and edit in Protégé (avoid hand-editing RDF/XML unless necessary).
2. Keep the export format consistent (RDF/XML).
3. Save/export, then run the repo’s validation/build steps (and ensure CI passes) before opening a PR.

## Provenance checklist for PRs

When you change `poppystructure.rdf`, please include in the PR description:
- a high-level summary of what changed (classes/properties/IRIs)
- the reason for the change
- the Protégé version used (optional but helpful)
