#!/usr/bin/env python
import argparse
from poppy.ontology.pipeline import build_and_export

def main():
    ap = argparse.ArgumentParser(description="Build and export the POPPy ontology from config.")
    ap.add_argument("--config", default="configs/ontology.yaml", help="Path to YAML config.")
    args = ap.parse_args()
    out = build_and_export(args.config)
    print(f"✅ Ontology exported to: {out}")

if __name__ == "__main__":
    main()
