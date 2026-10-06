"""fetch_unichem_xrefs.py - look up UniChem cross-references for a list of InChIKeys (resumable, parallel).

Run on a machine with internet access. Appends one JSON object per InChIKey to the cache:
  {"ik": "...", "sources": {"chembl": ["CHEMBL..."], "pubchem": ["123"], ...}}   (empty dict = not in UniChem)
Errors and throttling are retried with backoff and, if still failing, left out of the cache so the next run
retries them. Re-running skips everything already cached.
usage: fetch_unichem_xrefs.py unichem_worklist.tsv unichem_cache.jsonl [--workers 8]"""

import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "https://www.ebi.ac.uk/unichem/api/v1/compounds"


def fetch(ik):
    body = json.dumps({"type": "inchikey", "compound": ik}).encode()
    delay = 2.0
    for _ in range(6):
        req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(delay, 60) + random.uniform(0, 1))
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(min(delay, 60) + random.uniform(0, 1))
            delay *= 2
            continue
        srcs = {}
        comps = data.get("compounds") or [{"sources": data.get("sources", [])}]
        for c in comps:
            for s in c.get("sources", []) or []:
                name = (s.get("shortName") or s.get("name") or "").lower()
                cid = s.get("compoundId") or s.get("src_compound_id")
                if name and cid:
                    srcs.setdefault(name, [])
                    if str(cid) not in srcs[name]:
                        srcs[name].append(str(cid))
        return srcs
    raise RuntimeError("throttled; retry later")


def main(worklist, cache, workers=8):
    todo = [
        line.split("\t")[0] for line in open(worklist, encoding="utf-8").read().splitlines()[1:]
    ]
    done = set()
    if os.path.exists(cache):
        for line in open(cache, encoding="utf-8"):
            try:
                done.add(json.loads(line)["ik"])
            except (ValueError, KeyError):
                pass
    todo = [ik for ik in todo if ik not in done]
    print(f"{len(done):,} cached; {len(todo):,} to fetch with {workers} workers", flush=True)
    lock, n, failed, t0 = threading.Lock(), 0, 0, time.time()
    with open(cache, "a", encoding="utf-8") as fo, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch, ik): ik for ik in todo}
        for f in as_completed(futs):
            ik = futs[f]
            try:
                srcs = f.result()
            except Exception as e:  # left uncached -> retried on the next run
                failed += 1
                if failed <= 5:
                    print(f"  failed {ik}: {e}", flush=True)
                continue
            with lock:
                fo.write(json.dumps({"ik": ik, "sources": srcs}) + "\n")
                n += 1
                if n % 1000 == 0:
                    fo.flush()
                    rate = n / (time.time() - t0)
                    print(
                        f"  {n:,}/{len(todo):,}  {rate:.1f}/s  ~{(len(todo) - n) / rate / 60:.0f} min left",
                        flush=True,
                    )
    print(f"done: fetched {n:,}, failed {failed:,} (re-run to retry failures)")


if __name__ == "__main__":
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8
    main(sys.argv[1], sys.argv[2], w)
