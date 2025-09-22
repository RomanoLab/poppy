from pathlib import Path
from . import pubmed_impl as impl
def run(email, start_year, end_year, out_csv, cache_dir=".cache/literature",
        pmid_chunk=200, ret_chunk=1000, compute_maccs=True):
    for name, value in [
        ("EMAIL", email), ("START_YEAR", int(start_year)), ("END_YEAR", int(end_year)),
        ("OUT_CSV", out_csv), ("PMID_CHUNK", int(pmid_chunk)), ("RET_CHUNK", int(ret_chunk)),
    ]:
        if hasattr(impl, name):
            setattr(impl, name, value)
    if hasattr(impl, "RDK_OK") and not compute_maccs:
        impl.RDK_OK = False

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)

    if hasattr(impl, "run"):
        impl.run()
        return out_csv
    raise RuntimeError("pubmed_impl.run() not found")
