#!/usr/bin/env python
"""
enrich_common_names_powo.py — last-tier common-name gap-fill from POWO / Kew Species Profiles.

Runs ONLY on plants_index.json records that STILL lack a ``common`` field after the
GBIF/NCBI/Wikidata/Duke/iNaturalist passes, and tries to recover a common name from
Plants of the World Online (POWO, powo.science.kew.org).

METHOD (per still-unnamed scientific name)
  1. /api/2/search?q=<name> — the matched result's ``snippet`` field carries the common
     name directly, e.g. "<b>Common Name</b>: restong bark". This is the PRIMARY signal
     and needs only ONE request per plant.
  2. Fallback: image caption "Sci name (common)" from the same search response.
  3. Optional (--with-prose): a 2nd request to /api/2/taxon/{fqId}?fields=descriptions to
     mine Kew Species Profile prose when 1 and 2 miss (adds little; most names are in 1).
  Gap-only: never overwrites an existing common name. Cached (resumable). Provenance TSV.

LANGUAGE: POWO's snippet gives ONE vernacular, often regional (Thai, Malay, Spanish,
Chinese pinyin, ...), not necessarily English. Each hit is tagged with a best-effort
``language`` flag ("en" | "und") and the full comma-separated vernacular list is kept in
``all_common_names`` so you can filter later. The flag is a heuristic, not authoritative.

TRANSPORT: POWO is behind Cloudflare; a plain client gets 403-challenged (see CF_CLEARANCE
below). cloudscraper helps at low volume but is unreliable at scale; the robust option is
to export your browser's cf_clearance cookie + User-Agent.

DEFAULT IS --dry-run: nothing is written to plants_index.json until you inspect
data/enrichment/powo_common_names.tsv and re-run with --commit.

USAGE (needs network; run after the other enrichment passes)
  python3 scripts/enrich_common_names_powo.py --limit 40 --dry-run   # smoke test + TSV
  python3 scripts/enrich_common_names_powo.py --dry-run              # full pass, review TSV
  python3 scripts/enrich_common_names_powo.py --commit               # fill gaps (+ .bak)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POWO = "https://powo.science.kew.org/api/2"
# Bump when extraction logic changes so stale cached results are not replayed.
CACHE_VERSION = "4"
UA = "poppy-powo-enrich/1.0 (https://github.com/RomanoLab/poppy; ontology common-name enrichment)"

# POWO is behind Cloudflare bot protection: a plain urllib client gets a 403 "Just a
# moment..." challenge page. Two ways through, tried in this order:
#   1) cloudscraper, if installed  (pip install cloudscraper) — solves some challenges.
#   2) your browser's clearance: export the cookie + matching UA from a logged-in Chrome
#      session that can load POWO, so scripted requests ride your existing clearance:
#         export POWO_CF_CLEARANCE="<value of the cf_clearance cookie>"
#         export POWO_UA="<the exact User-Agent string your browser sends>"
#      (cf_clearance is tied to your IP + UA and expires; re-export when it 403s again.)
CF_CLEARANCE = os.environ.get("POWO_CF_CLEARANCE", "").strip()
CF_UA = os.environ.get("POWO_UA", "").strip()
try:
    import cloudscraper  # type: ignore

    _SCRAPER = cloudscraper.create_scraper()
except Exception:
    _SCRAPER = None

# Tokens that must never appear inside a candidate common name (connectives, botanical
# boilerplate, descriptors). A candidate containing any of these is rejected outright.
BAD_TOKENS = {
    "and",
    "or",
    "but",
    "of",
    "in",
    "on",
    "to",
    "for",
    "with",
    "from",
    "by",
    "at",
    "is",
    "are",
    "was",
    "were",
    "which",
    "who",
    "whose",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "a",
    "an",
    "the",
    "widespread",
    "common",
    "commonly",
    "widely",
    "locally",
    "native",
    "endemic",
    "cultivated",
    "grown",
    "growing",
    "grows",
    "found",
    "member",
    "members",
    "family",
    "families",
    "genus",
    "genera",
    "species",
    "subspecies",
    "variety",
    "one",
    "two",
    "three",
    "several",
    "many",
    "most",
    "some",
    "source",
    "used",
    "using",
    "defining",
    "iconic",
    "icon",
    "known",
    "called",
    "named",
    "referred",
    "perennial",
    "annual",
    "biennial",
    "flowering",
    "deciduous",
    "evergreen",
    "tropical",
    "temperate",
    "wild",
    "important",
    "popular",
    "famous",
    "well",
    "very",
    "also",
    "often",
    "usually",
    "sometimes",
    "typically",
    "generally",
    "native",
    "distributed",
    "occurs",
    "occurring",
}
# Leading stopwords stripped from the front of a candidate before guarding.
LEAD_STRIP = {"this", "the", "a", "an", "its", "their"}

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip().lower())


def clean_text(s: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s or ""))).strip()


# POWO search results carry the common name in the highlighted ``snippet`` field, e.g.
# "<b>Common Name</b>: restong bark". This is the PRIMARY forward signal (one request per
# plant, no taxon fetch needed). Tag-stripping can leave a space before the colon.
_SNIPPET_CN = re.compile(r"common names?\s*:\s*(.+)$", re.I)

# Best-effort English signal. POWO vernaculars are frequently regional (Thai, Malay,
# Spanish, Chinese pinyin, ...); this only flags likely-English names for later filtering,
# it is NOT authoritative language detection.
_EN_WORDS = {
    "bark",
    "lily",
    "tree",
    "root",
    "wort",
    "grass",
    "flower",
    "fruit",
    "apple",
    "bean",
    "pepper",
    "ginger",
    "wood",
    "leaf",
    "berry",
    "nut",
    "vine",
    "weed",
    "bush",
    "palm",
    "rose",
    "oak",
    "pine",
    "sage",
    "mint",
    "lotus",
    "bamboo",
    "cherry",
    "plum",
    "fig",
    "gum",
    "reed",
    "fern",
    "moss",
    "rush",
    "sea",
    "white",
    "black",
    "red",
    "yellow",
    "common",
    "wild",
    "false",
    "climbing",
    "creeping",
    "spiny",
    "hairy",
    "giant",
    "dwarf",
    "sacred",
    "holy",
    "water",
    "swamp",
    "mountain",
    "chinese",
    "japanese",
    "indian",
    "african",
    "american",
    "stinking",
    "sweet",
    "bitter",
    "milk",
    "snake",
    "resurrection",
    "pretty",
    "devil",
    "spider",
    "umbrella",
    "custard",
    "thorn",
    "spurge",
    "nettle",
}


def guess_lang(name: str) -> str:
    toks = _norm(name).replace("-", " ").split()
    return "en" if any(t in _EN_WORDS for t in toks) else "und"


def snippet_common(snippet: str):
    """Return (first_common_name, full_common_name_list) parsed from a POWO snippet."""
    m = _SNIPPET_CN.search(clean_text(snippet))
    if not m:
        return None, None
    full = m.group(1).strip().rstrip(".")
    first = _norm(re.split(r"[,;]", full)[0]).strip()
    if not first or len(first) < 2 or re.search(r"aceae$", first):
        return None, full
    return first, full


# Set to a status code (e.g. 403) when Cloudflare last challenged us, so the caller can
# warn the user instead of silently returning zero fills.
LAST_BLOCK = {"code": None}


def _http_get(url: str, timeout: int = 30):
    # Prefer your browser's clearance cookie when provided — it is the most reliable way
    # past Cloudflare. Only fall back to cloudscraper (installed) when no cookie is set.
    use_cookie = bool(CF_CLEARANCE)
    for attempt in range(4):
        try:
            if _SCRAPER is not None and not use_cookie:
                r = _SCRAPER.get(url, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                LAST_BLOCK["code"] = r.status_code
            else:
                headers = {"User-Agent": CF_UA or UA}
                if CF_CLEARANCE:
                    headers["Cookie"] = f"cf_clearance={CF_CLEARANCE}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                    return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            LAST_BLOCK["code"] = e.code
        except Exception:
            pass
        if attempt < 3:
            time.sleep(1.0 * (2**attempt))
    return None


def collect_text(descriptions) -> list[tuple[str, str, str]]:
    """Flatten POWO ``descriptions`` -> list of (source, field, cleaned_text) segments.

    Kept per-field (not merged) so the leading-sentence patterns see each field's real
    start, e.g. "This tree sea lavender," (KSP.general) or "Baobab," (KSP.snippet).
    """
    segs: list[tuple[str, str, str]] = []
    if not isinstance(descriptions, dict):
        return segs
    for source, payload in descriptions.items():

        def add(field, v):
            if isinstance(v, str):
                t = clean_text(v)
                if t:
                    segs.append((source, field, t))
            elif isinstance(v, dict):
                for k, vv in v.items():
                    add(k, vv)
            elif isinstance(v, list):
                for vv in v:
                    add(field, vv)

        add("_", payload)
    return segs


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _candidate_ok(cand: str, name_tokens: set[str]) -> str | None:
    """Trim/guard a raw candidate phrase. Return a clean common name or None."""
    cand = _norm(cand).strip(" -'’\"“”")
    # strip a leading determiner ("this tree sea lavender" -> "tree sea lavender")
    toks = cand.split()
    while toks and toks[0] in LEAD_STRIP:
        toks = toks[1:]
    if not toks:
        return None
    cand = " ".join(toks)
    if not (1 <= len(toks) <= 4):
        return None
    if any(t in BAD_TOKENS for t in toks):
        return None
    if any(t in name_tokens for t in toks):  # don't echo the Latin name back
        return None
    if re.search(r"[0-9]", cand):
        return None
    if not re.fullmatch(r"[a-z][a-z'’\- ]+[a-z]", cand):
        return None
    return cand


def _count(cand: str, text_low: str) -> int:
    return len(re.findall(r"\b" + re.escape(cand) + r"\b", text_low))


# Ordered extraction patterns. Each returns (candidate, pattern_id, needs_recurrence).
_P_EXPLICIT = re.compile(
    r"(?:commonly|widely|locally|variously|sometimes|also)?\s*"
    r"(?:known|called|referred to)\s+(?:variously\s+|locally\s+|commonly\s+)?as\s+"
    r"(?:the|a|an)?\s*([a-z][a-z'’\- ]{2,40}?)\s*(?:[.,;:()\"“”]|\band\b|\bor\b|$)",
    re.I,
)
_P_VERNACULAR = re.compile(r"vernacular names?\s*:?\s*([a-z][a-z'’\- ]{2,40})", re.I)
_P_THIS = re.compile(r"^this\s+([a-z][a-z'’\- ]{2,40}?)\s*,", re.I)
_P_LEAD = re.compile(r"^([A-Z][A-Za-z'’\-]+(?:\s+[a-z][A-Za-z'’\-]+){0,3})\s*,")

# Only the curated Kew Species Profile narrative fields are safe for the leading-noun
# patterns. Flora treatments (FIQ, CPLC, FWTA, ...) embed author citations like
# "Ghazanfar, S., Edmondson, J., & Haloob, A." that read exactly like "Name, ...".
KSP_NARRATIVE = {"snippet", "general", "summary", "description"}
# A sentence that looks like a bibliographic citation (author initials, ampersands,
# years, ed./pp./vol.) must never yield a common name.
_CITATION = re.compile(
    r"[A-Z]\.\s*[A-Z]?\.?\s*[,)]|&|\b(?:1[6-9]|20)\d{2}\b|\bed\.|\beds\.|\bpp?\.|\bvol\.|\bno\.",
    re.I,
)


def caption_common(sci_name: str, captions, name_tokens):
    """Parse a POWO image caption like 'Zingiber officinale (ginger)' -> 'ginger'.

    Highest-precision POWO signal: the caption pairs the scientific name with the common
    name explicitly. Only trusts captions whose leading text is our target taxon's name.
    """
    nkey = _norm(sci_name)
    toks = nkey.split()
    genus_species = f"{toks[0]} {toks[1]}" if len(toks) >= 2 else nkey
    for cap in captions or []:
        capn = _norm(cap)
        if not (capn.startswith(nkey) or capn.startswith(genus_species)):
            continue
        m = re.search(r"\(([^)]+)\)", cap)
        if not m:
            continue
        cand = _candidate_ok(m.group(1), name_tokens)
        if cand and cand not in {"illustration", "specimen"}:
            return cand, cap[:200]
    return None


def extract_common(sci_name: str, segments, captions=None):
    """Return (common, source, pattern, occurrences, evidence) or None.

    ``segments`` is a list of (source, field, text) tuples; ``captions`` a list of image
    caption strings. Caption pairings win; then explicit prose; then leading-noun phrases
    gated by recurrence across all text.
    """
    name_tokens = {t for t in re.split(r"[^a-z]+", _norm(sci_name)) if len(t) > 2}

    # 1) image caption "Sci name (common)" — most reliable
    cap_hit = caption_common(sci_name, captions, name_tokens)
    if cap_hit:
        cand, evid = cap_hit
        return cand, "IMG", "caption", 1, evid

    # 2) prose. Prefer KSP; concatenate everything for the recurrence test.
    ordered = sorted(segments, key=lambda seg: (seg[0] != "KSP", seg[0], seg[1]))
    full_low = _norm(" ".join(t for _, _, t in ordered))

    best = None  # (rank, occ, tuple)

    def consider(cand_raw, source, pat_id, rank, needs_recur):
        nonlocal best
        cand = _candidate_ok(cand_raw, name_tokens)
        if not cand:
            return
        occ = _count(cand, full_low)
        if needs_recur and occ < 2:
            return
        key = (rank, occ)
        if best is None or key > best[0]:
            best = (key, (cand, source, pat_id, occ))

    for source, _field, text in ordered:
        # explicit "known/called as X" and "vernacular names: X" — highest precision.
        # Any source, but never from a citation-shaped sentence.
        for m in _P_EXPLICIT.finditer(text):
            if not _CITATION.search(m.group(0)):
                consider(m.group(1), source, "explicit", 4, False)
        for m in _P_VERNACULAR.finditer(text):
            if not _CITATION.search(m.group(0)):
                consider(m.group(1), source, "vernacular", 4, False)
        # Leading-noun patterns are citation-prone: restrict to curated KSP narrative
        # fields AND skip any sentence that looks like a bibliographic reference.
        if source != "KSP" or _field not in KSP_NARRATIVE:
            continue
        sents = _sentences(text)
        for s in sents[:2]:
            if _CITATION.search(s):
                continue
            m = _P_THIS.match(s)
            if m:
                cand = _candidate_ok(m.group(1), name_tokens)
                multiword = bool(cand and " " in cand)
                consider(m.group(1), source, "this", 3, not multiword)
            m = _P_LEAD.match(s)
            if m:
                consider(m.group(1), source, "lead", 2, True)

    if not best:
        return None
    cand, source, pat_id, occ = best[1]
    # find a short evidence sentence containing the candidate
    evidence = ""
    for _src, _field, text in ordered:
        for s in _sentences(text):
            if re.search(r"\b" + re.escape(cand) + r"\b", s, re.I):
                evidence = s[:200]
                break
        if evidence:
            break
    return cand, source, pat_id, occ, evidence


class PowoSource:
    def __init__(self, cache_path: Path, sleep: float = 1.0, timeout: int = 30, with_prose=False):
        self.cache_path = Path(cache_path)
        self.sleep, self.timeout = sleep, timeout
        self.with_prose = with_prose  # default: search-only (snippet+caption), 1 request/plant
        self.cache: dict[str, dict] = {}
        if self.cache_path.exists():
            try:
                loaded = json.loads(self.cache_path.read_text())
                # Discard caches written by an older extractor version (stale results).
                if loaded.get("__version__") == CACHE_VERSION:
                    self.cache = loaded
            except Exception:
                self.cache = {}
        self.cache["__version__"] = CACHE_VERSION
        self._dirty = 0

    def _resolve_fqid(self, name: str):
        url = POWO + "/search?" + urllib.parse.urlencode({"q": name, "perPage": 10})
        data = _http_get(url, self.timeout)
        results = (data or {}).get("results") or []
        if not results:
            return None, "", False, [], ""
        key = _norm(name)
        exact_acc = exact_any = first_acc = None
        for r in results:
            rn = _norm(r.get("name", ""))
            acc = bool(r.get("accepted"))
            if rn == key and acc and exact_acc is None:
                exact_acc = r
            if rn == key and exact_any is None:
                exact_any = r
            if acc and first_acc is None:
                first_acc = r
        chosen = exact_acc or exact_any or first_acc or results[0]
        captions = [
            img.get("caption", "")
            for img in (chosen.get("images") or [])
            if isinstance(img, dict) and img.get("caption")
        ]
        return (
            chosen.get("fqId"),
            chosen.get("name", ""),
            bool(chosen.get("accepted")),
            captions,
            chosen.get("snippet", ""),
        )

    def lookup(self, name: str) -> dict:
        key = _norm(name)
        if key in self.cache:
            return self.cache[key]
        rec = {
            "fqid": "",
            "matched_name": "",
            "accepted": False,
            "common": "",
            "all_names": "",
            "language": "",
            "source": "",
            "pattern": "",
            "evidence": "",
        }
        fqid, matched, accepted, captions, snippet = self._resolve_fqid(name)
        time.sleep(self.sleep)
        if fqid:
            rec.update(fqid=fqid, matched_name=matched, accepted=accepted)
            # 1) PRIMARY: the common name in the search snippet (no extra request).
            cn, full = snippet_common(snippet)
            if cn:
                rec.update(
                    common=cn,
                    all_names=full or cn,
                    language=guess_lang(cn),
                    source="POWO",
                    pattern="snippet",
                    evidence=(clean_text(snippet))[:200],
                )
            else:
                # 2) FALLBACK: image caption, then (optional) profile prose.
                segments = []
                if self.with_prose:
                    url = (
                        POWO
                        + "/taxon/"
                        + urllib.parse.quote(fqid, safe="")
                        + "?fields=descriptions"
                    )
                    data = _http_get(url, self.timeout)
                    time.sleep(self.sleep)
                    segments = collect_text((data or {}).get("descriptions"))
                hit = extract_common(name, segments, captions)
                if hit:
                    cand, src, pat, _occ, evid = hit
                    rec.update(
                        common=cand,
                        all_names=cand,
                        language=guess_lang(cand),
                        source="POWO",
                        pattern=pat,
                        evidence=evid,
                    )
        self.cache[key] = rec
        self._dirty += 1
        if self._dirty >= 50:
            self._flush()
        return rec

    def _flush(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache))
        self._dirty = 0

    def close(self):
        if self._dirty:
            self._flush()


def detect_separators(raw: str):
    head = raw[:400]
    return (", ", ": ") if '", "' in head or '": "' in head else (",", ":")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plants-index", default=str(REPO / "website" / "data" / "plants_index.json"))
    ap.add_argument("--cache", default=str(REPO / "data" / "enrichment" / "powo_cache.json"))
    ap.add_argument(
        "--provenance-out", default=str(REPO / "data" / "enrichment" / "powo_common_names.tsv")
    )
    ap.add_argument("--limit", type=int, default=0, help="Process only first N gap records.")
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between HTTP calls.")
    ap.add_argument(
        "--with-prose",
        action="store_true",
        help="Add a 2nd request per plant to mine Kew profile prose when the snippet/caption "
        "miss. Doubles load; the snippet already carries most common names.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default. Write TSV only; do not touch plants_index.json.",
    )
    ap.add_argument(
        "--commit",
        dest="dry_run",
        action="store_false",
        help="Actually write filled names into plants_index.json (+ .bak).",
    )
    args = ap.parse_args()

    plants_path = Path(args.plants_index)
    raw = plants_path.read_text()
    sep = detect_separators(raw)
    records = json.loads(raw)
    already = sum(1 for r in records if r.get("common"))
    gaps = [r for r in records if not r.get("common")]
    if args.limit:
        gaps = gaps[: args.limit]
    print(
        f"Loaded {len(records):,} records; {already:,} already named; {len(gaps):,} gaps to try"
        + (f" (limited to {args.limit})" if args.limit else "")
    )

    powo = PowoSource(Path(args.cache), sleep=args.sleep, with_prose=args.with_prose)
    mode = "search+prose (2 req/plant)" if args.with_prose else "search-only (1 req/plant)"
    print(f"[powo] cache: {max(0, len(powo.cache) - 1):,} memoized; mode: {mode}")

    retrieved = _dt.date.today().isoformat()
    prov, filled = [], 0
    for i, rec in enumerate(gaps):
        sci = rec.get("name", "")
        r = powo.lookup(sci)
        name = (r.get("common") or "").strip()
        if name:
            rec["common"] = name
            filled += 1
        prov.append(
            {
                "organism_id": rec.get("id", ""),
                "scientific_name": sci,
                "powo_fqid": r.get("fqid", ""),
                "matched_name": r.get("matched_name", ""),
                "accepted": "yes" if r.get("accepted") else "no",
                "powo_common_name": name,
                "language": r.get("language", ""),
                "all_common_names": (r.get("all_names", "") or "").replace("\t", " "),
                "pattern": r.get("pattern", ""),
                "evidence": (r.get("evidence", "") or "").replace("\t", " "),
            }
        )
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1:,}/{len(gaps):,} tried, {filled:,} filled")
    powo.close()

    prov_path = Path(args.provenance_out)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "organism_id",
        "scientific_name",
        "powo_fqid",
        "matched_name",
        "accepted",
        "powo_common_name",
        "language",
        "all_common_names",
        "pattern",
        "evidence",
    ]
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# source: POWO /api/2 (Kew Species Profiles prose); extracted heuristically, REVIEW ME\n"
        )
        fh.write(f"# retrieved: {retrieved}\n")
        fh.write("\t".join(header) + "\n")
        for r in prov:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    total = len(records) or 1
    new_total = already + filled
    print("\n=== POWO / KSP GAP-FILL (last-tier, review the TSV) ===")
    print(f"  filled this pass:   {filled:,}/{len(gaps):,} gaps")
    print(f"  coverage before:    {already:,}/{len(records):,} ({100*already/total:.1f}%)")
    print(f"  coverage after:     {new_total:,}/{len(records):,} ({100*new_total/total:.1f}%)")
    print(f"  provenance table:   {prov_path}  <-- inspect before committing")

    if LAST_BLOCK["code"] in (403, 429, 503):
        engine = "cloudscraper" if _SCRAPER is not None else "urllib"
        print(
            f"\n  !! POWO returned HTTP {LAST_BLOCK['code']} (Cloudflare challenge) via {engine}."
            "\n     Requests are being blocked, so fills above are unreliable/zero. Options:"
            "\n       - pip install cloudscraper --break-system-packages   (then re-run)"
            "\n       - export POWO_CF_CLEARANCE / POWO_UA from a browser that can load POWO"
            "\n       - wait for the IP block to cool down and raise --sleep"
        )

    if args.dry_run:
        print("\n[dry-run] plants_index.json NOT modified. Re-run with --commit to write.")
        return 0

    backup = plants_path.with_suffix(plants_path.suffix + ".bak")
    shutil.copy2(plants_path, backup)
    plants_path.write_text(json.dumps(records, ensure_ascii=False, separators=sep))
    print(f"\nWrote enriched {plants_path} (backup at {backup}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
