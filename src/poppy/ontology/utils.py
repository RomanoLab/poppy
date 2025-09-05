import re
from contextlib import contextmanager
import time

def sanitize_for_uri(text: str) -> str:
    return re.sub(r"\W|^(?=\d)", "_", str(text or "").strip())

@contextmanager
def timer(label: str):
    t0 = time.time()
    yield
    print(f"[{label}] {time.time()-t0:.2f}s")
