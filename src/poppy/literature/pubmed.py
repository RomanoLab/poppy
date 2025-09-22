"""poppy.literature.pubmed
Skeleton module for literature ingestion (PubMed → plants & compounds).
Move your existing logic from Scientific_Paper_data.py into helper functions
and wire them inside run(...).
"""
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Example placeholders — replace with your real implementations:
# def search_pubmed(...): ...
# def fetch_details(...): ...
# def validate_plants(...): ...
# def extract_compounds(...): ...
# def resolve_pubchem(...): ...
# def add_maccs(...): ...
# def materialize_rows(...): ...

def run(
    email: str,
    start_year: int,
    end_year: int,
    out_csv: str,
    cache_dir: str = ".cache/literature",
    pmid_chunk: int = 200,
    ret_chunk: int = 1000,
    compute_maccs: bool = True,
) -> str:
    """Query PubMed → extract plants/compounds → validate/resolve → (opt) MACCS → write CSV."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)

    # Wire your real pipeline here, e.g.:
    # pmids = search_pubmed(start_year, end_year, ret_chunk=ret_chunk, email=email, cache_dir=cache_dir)
    # records = fetch_details(pmids, pmid_chunk=pmid_chunk, email=email, cache_dir=cache_dir)
    # rows: List[Dict[str, Any]] = []
    # for rec in records:
    #     plants = validate_plants(rec, cache_dir=cache_dir)
    #     compounds = extract_compounds(rec)
    #     resolved = resolve_pubchem(compounds)
    #     if compute_maccs:
    #         resolved = add_maccs(resolved)
    #     rows.extend(materialize_rows(rec, plants, resolved))
    # df = pd.DataFrame(rows)

    # Minimal placeholder so file writes
    df = pd.DataFrame([])
    df.to_csv(out_csv, index=False)
    return out_csv
