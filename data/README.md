# data

This directory contains small, versioned data assets that are required to run or build POPPy.

## Contents

- `ontology/` — ontology resources used by the build pipeline (see `data/ontology/README.md`).

## What belongs here

Commit:
- small, stable inputs required for builds (e.g., ontology scaffolds)
- small mapping/metadata files that are hard requirements for scripts

Do not commit:
- large, regenerable build outputs
- private/restricted datasets
- temporary caches/logs

## Updating data files

If you replace or update files under `data/`, please include a short note in the PR description explaining:
- what changed and why
- how the new file was generated (manual vs script)
- any implications for reproducibility
