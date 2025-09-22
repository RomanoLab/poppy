#!/usr/bin/env python
import argparse
from poppy.literature.pubmed import run

def main():
    ap = argparse.ArgumentParser("Ingest PubMed → plants + compounds CSV")
    ap.add_argument("--email", required=True, help="Contact email for NCBI")
    ap.add_argument("--start", type=int, default=1975)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default="data/processed/literature/pubmed_plants_compounds.csv")
    ap.add_argument("--pmid-chunk", type=int, default=200)
    ap.add_argument("--ret-chunk", type=int, default=1000)
    ap.add_argument("--no-maccs", action="store_true")
    args = ap.parse_args()

    path = run(
        email=args.email,
        start_year=args.start,
        end_year=args.end,
        out_csv=args.out,
        pmid_chunk=args.pmid_chunk,
        ret_chunk=args.ret_chunk,
        compute_maccs=not args.no_maccs,
    )
    print(f"✅ wrote {path}")

if __name__ == "__main__":
    main()
