from typing import Dict, List, Iterable
import csv

def load_csv_rows(path: str, sep: str = ',', columns: List[str] = None, rename: Dict[str, str] = None) -> Iterable[dict]:
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=('	' if sep == '	' else sep))
        for row in reader:
            if columns:
                row = {k: row.get(k) for k in columns}
            if rename:
                row = {rename.get(k, k): v for k, v in row.items()}
            yield row
