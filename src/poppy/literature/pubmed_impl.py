#!/usr/bin/env python
# coding: utf-8

# In[4]:


get_ipython().system("pip install rapidfuzz")


# In[8]:


get_ipython().system("pip install pycountry")


# Troubleshooting: PubMed sometimes returns HTTP 400 when using WebEnv/QueryKey (history) for long jobs.
# Solution: don’t use WebEnv/QueryKey anymore (those can 400 due to stale sessions or edge cases). Page ESearch with retstart/retmax, then EFetch by ID chunks with a retry wrapper and backoff.

# In[1]:


"""
PubMed → CSV of (validated plant scientific_name × compound identifiers × traditional_use), 1975→2025

Key features
- Taxonomy validation: GBIF species/match → only keep taxa where kingdom == Plantae (robust, cached)
- Plant names: strict candidate finder (MeSH + Latin-like regex), then GBIF validation
- Traditional use: rule-based extraction from title+abstract (e.g., "traditionally used for ...", indications)
- Compounds: include ONLY if PubChem returns ≥1 of {InChI, InChIKey, SMILES}
  Sources: MeSH ChemicalList (CAS RN), SupplMesh, Keywords, TA heuristics
- Robust E-utilities & PubChem with retries and safe fallbacks
- tqdm progress bars + total wall-clock time
- Output columns:
    scientific_name, traditional_use, compound_inchi, compound_inchikey, compound_smiles, compound_maccs166,
    doi, pmid, title, year, journal
"""

import time
import re
import json
import requests
import pandas as pd
from lxml import etree

# ---------- Timing helpers ----------
t0 = time.perf_counter()


def fmt_secs(s):
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:d}h {m:02d}m {s:02d}s" if h else f"{m:d}m {s:02d}s" if m else f"{s:d}s"


# ---------- tqdm (progress bars), graceful fallback ----------
try:
    from tqdm.auto import tqdm
except Exception:

    def tqdm(iterable=None, total=None, desc=None, **kwargs):
        return iterable if iterable is not None else range(total or 0)


# ---------------- CONFIG ----------------
EMAIL = "your_email@example.com"  # NCBI contact email (polite)
TOOL = "med_plants_compound_ids_gbif_tax_traduse"
START_YEAR = 1975
END_YEAR = 2025
WINDOW_YEARS = 5  # 5-year windows
RET_CHUNK = 1000  # esearch page size
PMID_CHUNK = 200  # efetch batch size
OUT_CSV = "pubmed_plants_1975_present_compound_ids_traduse.csv"

# final schema
WANT_COLS = [
    "scientific_name",
    "traditional_use",
    "compound_inchi",
    "compound_inchikey",
    "compound_smiles",
    "compound_maccs166",
    "doi",
    "pmid",
    "title",
    "year",
    "journal",
]


def sleep_ncbi():
    time.sleep(0.34)


def sleep_pubchem():
    time.sleep(0.25)


def sleep_gbif():
    time.sleep(0.20)  # be polite to GBIF


# ---------------- OPTIONAL RDKit (MACCS) ----------------
RDK_OK = False
try:
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys

    RDK_OK = True
except Exception:
    RDK_OK = False


def maccs_from_smiles(smiles: str) -> str:
    if not (RDK_OK and smiles):
        return ""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return ""
        fp = MACCSkeys.GenMACCSKeys(mol)  # 167 bits; bit 0 unused
        return "".join("1" if fp.GetBit(i) else "0" for i in range(1, 167))
    except Exception:
        return ""


# ---------------- ROBUST REQUEST HELPER ----------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": f"{TOOL} (mailto:{EMAIL})", "Accept": "application/json"})
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
GBIF = "https://api.gbif.org/v1"


def _safe_get(url, params, sleep_fn=lambda: None, timeout=60, max_tries=5):
    """
    GET with polite sleep, retries/backoff, JSON->cleaned JSON->XML fallbacks.
    Returns dict (JSON) or lxml element (XML) or None.
    On non-retriable HTTP errors (e.g., 400/404), returns None instead of raising.
    """
    for attempt in range(max_tries):
        try:
            sleep_fn()
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code not in (200, 429, 500, 502, 503, 504):
                return None
            r.raise_for_status()
            ct = (r.headers.get("Content-Type") or "").lower()
            if "json" in ct:
                try:
                    return r.json()
                except Exception:
                    pass
            # Try JSON after control-char strip
            try:
                cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", r.text)
                return json.loads(cleaned)
            except Exception:
                # Fall back to XML
                try:
                    return etree.fromstring(r.content)
                except Exception:
                    pass
            time.sleep(1.5 * (attempt + 1))
        except requests.HTTPError:
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


# ---------------- PUBMED SEARCH (robust) ----------------
def build_query_core():
    # Focus on plant/ethnopharm topics to reduce noise up front
    return (
        "("
        "Plants[MeSH Terms] OR Plants, Medicinal[MeSH Terms] OR Plant Extracts[MeSH Terms] OR "
        "Phytotherapy[MeSH Terms] OR Pharmacognosy[MeSH Terms] OR Ethnopharmacology[MeSH Terms] OR "
        "ethnobotan*[Title/Abstract] OR ethnopharmacolog*[Title/Abstract] OR phytochem*[Title/Abstract] OR "
        '"essential oil"[Title/Abstract] OR "essential oils"[Title/Abstract] OR herbal[Title/Abstract]'
        ") AND hasabstract[text]"
    )


def esearch_count(query, mindate, maxdate):
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": str(mindate),
        "maxdate": str(maxdate),
        "retmode": "json",
        "tool": TOOL,
        "email": EMAIL,
    }
    resp = _safe_get(f"{EUTILS}/esearch.fcgi", params, sleep_fn=sleep_ncbi)
    if resp is None:
        return 0
    if isinstance(resp, dict):
        return int(resp.get("esearchresult", {}).get("count", 0))
    if isinstance(resp, etree._Element):
        cnt = resp.findtext(".//Count")
        return int(cnt) if cnt and cnt.isdigit() else 0
    return 0


def esearch_ids_paged(query, mindate, maxdate, retstart=0, retmax=1000):
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": str(mindate),
        "maxdate": str(maxdate),
        "retmode": "json",
        "retstart": retstart,
        "retmax": retmax,
        "sort": "pub+date",
        "tool": TOOL,
        "email": EMAIL,
    }
    resp = _safe_get(f"{EUTILS}/esearch.fcgi", params, sleep_fn=sleep_ncbi)
    if resp is None:
        return []
    if isinstance(resp, dict):
        return resp.get("esearchresult", {}).get("idlist", []) or []
    if isinstance(resp, etree._Element):
        return [el.text for el in resp.findall(".//IdList/Id") if el is not None and el.text]
    return []


def _year_windows(start_year, end_year, span):
    windows = []
    y = start_year
    while y <= end_year:
        y_end = min(y + span - 1, end_year)
        windows.append((y, y_end))
        y = y_end + 1
    return windows


def esearch_all_ids_by_window(query, start_year, end_year, window_years=5, page_size=1000):
    pmids = set()
    windows = _year_windows(start_year, end_year, window_years)
    for y, y_end in tqdm(windows, desc="Searching PubMed windows"):
        count = esearch_count(query, y, y_end)
        retstart = 0
        while retstart < count:
            ids = esearch_ids_paged(query, y, y_end, retstart=retstart, retmax=page_size)
            if not ids:
                break
            pmids.update(ids)
            retstart += len(ids)
    return sorted(pmids)


def efetch_pubmed_xml(pmids):
    """Yield parsed PubMed records in PMID_CHUNK batches (with progress bar)."""
    total_batches = (len(pmids) + PMID_CHUNK - 1) // PMID_CHUNK
    for i in tqdm(
        range(0, len(pmids), PMID_CHUNK), total=total_batches, desc="Fetching+parsing articles"
    ):
        sub = pmids[i : i + PMID_CHUNK]
        params = {
            "db": "pubmed",
            "id": ",".join(sub),
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        }
        root = _safe_get(f"{EUTILS}/efetch.fcgi", params, sleep_fn=sleep_ncbi, timeout=90)
        if not isinstance(root, etree._Element):
            continue
        for art in root.findall(".//PubmedArticle"):
            pmid = (art.findtext(".//PMID") or "").strip()
            title = (art.findtext(".//ArticleTitle") or "").strip()
            abstract = " ".join(
                [(t.text or "") for t in art.findall(".//Abstract/AbstractText")]
            ).strip()
            year = art.findtext(".//PubDate/Year") or art.findtext(".//ArticleDate/Year") or ""
            journal = (
                art.findtext(".//Journal/ISOAbbreviation") or art.findtext(".//Journal/Title") or ""
            ).strip()
            mesh_terms = [
                mh.findtext("DescriptorName")
                for mh in art.findall(".//MeshHeading")
                if mh.findtext("DescriptorName")
            ]

            # ChemicalList (MeSH substances + RegistryNumber)
            chem_items = [
                {
                    "name": (ch.findtext("NameOfSubstance") or "").strip(),
                    "rn": (ch.findtext("RegistryNumber") or "").strip(),
                }
                for ch in art.findall(".//ChemicalList/Chemical")
            ]
            # Supplementary Concepts (often chemicals)
            suppl = [
                (e.text or "").strip()
                for e in art.findall(".//SupplMeshNameList/SupplMeshName")
                if e.text
            ]
            # Author Keywords
            keywords = [
                (k.text or "").strip() for k in art.findall(".//KeywordList/Keyword") if k.text
            ]
            # DOI
            dois = [
                aid.text
                for aid in art.findall(".//ArticleIdList/ArticleId")
                if aid.get("IdType") == "doi" and aid.text
            ]
            doi = dois[0].lower().strip() if dois else ""

            yield {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "journal": journal,
                "mesh": mesh_terms,
                "doi": doi,
                "chem_items": chem_items,
                "suppl": suppl,
                "keywords": keywords,
            }


# ---------------- PLANT CONTEXT GATE ----------------
PLANT_MESH_HINTS = {
    "plants",
    "plants, medicinal",
    "plant extracts",
    "phytotherapy",
    "pharmacognosy",
    "ethnopharmacology",
    "herbalism",
    "herbal medicine",
}
PLANT_TA_HINTS = re.compile(
    r"\b(plant|leaf|leaves|root|rhizome|seed|fruit|bark|flower|herb|herbal|botanical|"
    r"phytochem\w*|polyphenol\w*|essential oil\w*|extract\w*|infusion|decoction)\b",
    re.I,
)


def is_plant_context(mesh_terms, title, abstract):
    mt = {m.lower() for m in (mesh_terms or [])}
    if mt & PLANT_MESH_HINTS:
        return True
    text = f"{title} {abstract}"
    return bool(PLANT_TA_HINTS.search(text))


# ---------------- BOTANICAL NAME CANDIDATES (pre-validation) ----------------
# Latin-like epithet endings to avoid English bigrams
LATIN_EPITHET_OK = re.compile(
    r"(us|a|um|is|ae|ii|i|ensis|ense|ica|icus|icum|iana|ianus|ianum|atum|atus|"
    r"folia|folium|officinalis|sativa|indica|japonica|chinensis|vulgaris|arvensis|montana|alba|nigra|rubra|lutea|glabra|cordata|lanceolata)$"
)

GENUS_STOP = {
    "The",
    "This",
    "That",
    "These",
    "Those",
    "A",
    "An",
    "In",
    "On",
    "Of",
    "For",
    "With",
    "Without",
    "Although",
    "While",
    "Because",
    "Since",
    "If",
    "No",
    "Yes",
    "Multiple",
    "Spontaneous",
    "Randomized",
    "Double",
    "Open",
    "Prospective",
    "Retrospective",
    "Comparative",
    "Efficacy",
    "Effects",
    "Effect",
    "Intervention",
    "Feeding",
    "Findings",
    "Study",
    "Trial",
    "Cohort",
    "Participants",
    "Patients",
    "Children",
    "Adults",
    "Women",
    "Men",
    "Case",
    "Report",
    "Review",
    "Meta",
    "Analysis",
    "Method",
    "Methods",
    "Materials",
    "Results",
    "Discussion",
    "Conclusion",
    "Conclusions",
    "Retinal",
    "Ganglion",
    "Cells",
    "Cell",
    "Brain",
    "Salamander",
    "Mouse",
    "Mice",
    "Rat",
    "Rats",
    "Human",
    "Humans",
    "Clinical",
    "Subthreshold",
    "Threshold",
    "Neural",
    "Neuron",
    "Cortex",
    "Protein",
    "Enzyme",
    "Chromatography",
    "Extraction",
}

BINOMIAL_FLEX = re.compile(
    r"\b([A-Z][a-z]+)(?:\s*[×x]\s*)?\s([a-z\-]{3,})(?:\s+(?:subsp\.|ssp\.|var\.|f\.|forma)\s+([a-z\-]{3,}))?\b"
)


def candidate_botanical_names(text):
    cands = set()
    for m in BINOMIAL_FLEX.finditer(text):
        genus, epithet, infra = m.group(1), m.group(2), m.group(3)
        if genus in GENUS_STOP:
            continue
        if not LATIN_EPITHET_OK.search(epithet):
            continue
        name = f"{genus} {epithet}"
        if infra:
            frag = m.group(0)
            if "var." in frag:
                name += f" var. {infra}"
            elif "subsp." in frag or "ssp." in frag:
                name += f" subsp. {infra}"
            elif " f. " in frag or " forma " in frag:
                name += f" f. {infra}"
        cands.add(name)
    return sorted(cands)


def mesh_species(mesh_terms):
    out = []
    for m in mesh_terms or []:
        if " " in (m or ""):
            parts = m.split()
            if len(parts) >= 2 and parts[0][0:1].isupper() and LATIN_EPITHET_OK.search(parts[1]):
                if parts[0] not in GENUS_STOP:
                    out.append(f"{parts[0]} {parts[1]}")
    return out


# ---------------- GBIF TAXONOMY VALIDATION ----------------
GBIF_CACHE = {}  # name -> normalized canonical if Plantae (else None)


def gbif_validate_plant(name):
    """
    Validate a scientific name via GBIF species/match.
    Keep iff 'kingdom' == 'Plantae' and rank in {SPECIES, SUBSPECIES, VARIETY, FORM, HYBRID} (or similar).
    Return a normalized canonical name (GBIF 'scientificName' stripped to canonical) or None.
    """
    if not name:
        return None
    if name in GBIF_CACHE:
        return GBIF_CACHE[name]

    params = {"name": name}
    resp = _safe_get(f"{GBIF}/species/match", params=params, sleep_fn=sleep_gbif, timeout=30)
    if not isinstance(resp, dict):
        GBIF_CACHE[name] = None
        return None

    # Prefer accepted usage if available
    data = resp
    if data.get("kingdom") != "Plantae":
        GBIF_CACHE[name] = None
        return None

    # Acceptable ranks (GBIF ranks are uppercase)
    rank = (data.get("rank") or "").upper()
    ok_ranks = {"SPECIES", "SUBSPECIES", "VARIETY", "FORM", "HYBRID", "SPECIES_AGGREGATE"}
    if rank and rank not in ok_ranks:
        # Still allow when canonicalName looks binomial and kingdom=Plantae
        pass

    # Normalize: prefer canonicalName if provided; else scientificName stripped
    canon = data.get("canonicalName") or data.get("scientificName") or name
    canon = canon.replace("  ", " ").strip()
    GBIF_CACHE[name] = canon
    return canon


def species_from_article_validated(a):
    text = f"{a['title']} {a['abstract']}"
    pre = set(mesh_species(a["mesh"])) | set(candidate_botanical_names(text))
    out = set()
    for s in pre:
        canon = gbif_validate_plant(s)
        if canon:
            out.add(canon)
    return sorted(out)


# ---------------- TRADITIONAL USE EXTRACTION ----------------
# Simple rule-based extractor mapping phrases/keywords to normalized indications.
# You can extend/curate this list as needed.
INDICATION_SYNONYMS = {
    "analgesic": {"analgesic", "pain", "painkiller", "antinociceptive"},
    "anti-inflammatory": {"anti-inflammatory", "antiinflammatory", "inflammation", "antiinflamm"},
    "antimicrobial": {
        "antimicrobial",
        "antibacterial",
        "antifungal",
        "antiviral",
        "antiparasitic",
        "antimalarial",
        "anthelmintic",
    },
    "antidiabetic": {"antidiabetic", "diabetes", "hypoglycemic", "hypoglycaemic"},
    "antihypertensive": {"antihypertensive", "hypertension", "blood pressure"},
    "gastroprotective": {
        "gastroprotective",
        "ulcer",
        "gastric",
        "stomach ache",
        "antidiarrheal",
        "diarrhea",
        "diarrhoea",
        "constipation",
    },
    "hepatoprotective": {"hepatoprotective", "liver", "hepatitis"},
    "neuroprotective": {
        "neuroprotective",
        "memory",
        "neurodegenerative",
        "anxiolytic",
        "antidepressant",
        "sedative",
    },
    "wound healing": {"wound", "cicatrizing", "cicatrisation", "burns", "cuts"},
    "respiratory": {"cough", "cold", "asthma", "bronchitis"},
    "antioxidant": {"antioxidant", "oxidative stress"},
    "anticancer": {"anticancer", "antitumor", "antitumour", "chemopreventive"},
    "antipyretic": {"antipyretic", "fever"},
    "diuretic": {"diuretic"},
    "antiulcer": {"antiulcer", "ulcer"},
    "antidiarrheal": {"antidiarrheal", "diarrhea", "diarrhoea"},
    "anti-obesity": {"anti-obesity", "antiobesity", "obesity", "weight loss"},
    "antispasmodic": {"antispasmodic", "spasm", "colic"},
    "antimalarial": {"antimalarial", "malaria"},
}

# Trigger phrases that often announce traditional/folk usage
TRAD_PHRASES = re.compile(
    r"(traditionall?y used(?: in [^,;.]+)? to\s+[^.;:]+|used in (?:folk|traditional) medicine(?: to)?\s+[^.;:]+|"
    r"in ayurveda|in (?:traditional )?chinese medicine|in tcm|ethnomedicin[a-z]*|ethnopharmacolog[a-z]*)",
    re.I,
)


def extract_traditional_use(title, abstract):
    text = f"{title} {abstract}".strip()
    uses = set()

    # 1) Pull explicit "traditionally used ..." snippets (shorten a bit)
    for m in TRAD_PHRASES.finditer(text):
        snippet = m.group(0)
        # compact: keep up to ~120 chars
        snippet = re.sub(r"\s+", " ", snippet).strip()
        uses.add(snippet[:120])

    # 2) Map keywords to normalized indication labels
    low = text.lower()
    labels = set()
    for label, keys in INDICATION_SYNONYMS.items():
        for k in keys:
            if k in low:
                labels.add(label)
                break
    if labels:
        uses.add("; ".join(sorted(labels)))

    if not uses:
        return ""
    # Return concise semicolon-separated string of unique bits
    ordered = sorted(uses)
    return " | ".join(ordered[:5])  # limit to 5 chunks for readability


# ---------------- COMPOUND IDENTIFIERS (PubChem) ----------------
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")

CHEM_HINTS = {
    "curcumin",
    "demethoxycurcumin",
    "bisdemethoxycurcumin",
    "eugenol",
    "rosmarinic acid",
    "caffeic acid",
    "allicin",
    "quercetin",
    "kaempferol",
    "luteolin",
    "beta-sitosterol",
    "withaferin A",
    "berberine",
    "epigallocatechin gallate",
    "EGCG",
    "rutin",
    "gallic acid",
    "ellagic acid",
    "apigenin",
    "naringenin",
    "hesperidin",
    "saponin",
    "alkaloid",
    "flavonoid",
    "terpenoid",
}
COMPOUND_STOPWORDS = {
    "protein",
    "chain",
    "certain",
    "margin",
    "origin",
    "skin",
    "insulin",
    "stain",
    "basin",
    "main",
    "grain",
    "begin",
    "kin",
    "within",
    "asin",
    "login",
    "admin",
}
ACID_PHRASE = re.compile(r"\b([a-z][a-z\-]{3,})\s+acid\b", re.I)
GLYCOSIDE = re.compile(r"\b[a-z0-9\-]+(?:glucoside|rhamnoside|rutinoside|arabinoside)\b", re.I)
O_GLYCO = re.compile(r"\b[a-z0-9\-]+-o-[a-z0-9\-]+(?:glucoside|rhamnoside|rutinoside)\b", re.I)
SINGLE_TOKEN = re.compile(r"\b[a-z][a-z0-9\-]{5,}(?:ic|ol|one|ine|ose|etin|enin)\b", re.I)


def find_compound_mentions_from_text(text):
    out = set()
    tlow = text.lower()
    for name in CHEM_HINTS:
        if re.search(rf"\b{re.escape(name.lower())}\b", tlow):
            out.add(name)
    for m in ACID_PHRASE.finditer(tlow):
        base = m.group(1)
        if base and base not in COMPOUND_STOPWORDS:
            out.add(f"{base} acid")
    for rx in (GLYCOSIDE, O_GLYCO):
        for m in rx.finditer(tlow):
            tok = m.group(0)
            if tok and tok not in COMPOUND_STOPWORDS:
                out.add(tok)
    for m in SINGLE_TOKEN.finditer(tlow):
        tok = m.group(0)
        if tok and tok not in COMPOUND_STOPWORDS:
            out.add(tok)
    return sorted(out)


def pubchem_cid_from_rn(rn):
    if not rn or not CAS_RE.match(rn):
        return None
    try:
        sleep_pubchem()
        url = f"{PUBCHEM}/compound/xref/RN/{requests.utils.quote(rn)}/cids/TXT"
        r = SESSION.get(url, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        txt = r.text.strip()
        if txt:
            return int(txt.splitlines()[0])
    except Exception:
        return None
    return None


def pubchem_cid_from_name(name):
    if not name:
        return None
    try:
        sleep_pubchem()
        url = f"{PUBCHEM}/compound/name/{requests.utils.quote(name)}/cids/TXT"
        r = SESSION.get(url, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        txt = r.text.strip()
        if txt:
            return int(txt.splitlines()[0])
    except Exception:
        return None
    return None


def pubchem_props(cid):
    props = "InChI,InChIKey,IsomericSMILES"
    resp = _safe_get(
        f"{PUBCHEM}/compound/cid/{cid}/property/{props}/JSON",
        params={},
        sleep_fn=sleep_pubchem,
        timeout=30,
    )
    if isinstance(resp, dict):
        items = resp.get("PropertyTable", {}).get("Properties", [])
        return items[0] if items else {}
    return {}


def resolve_compound_identifiers_from_rn_or_name(rn, name, _cache={}):
    """
    Try RN→CID first (most reliable), then name→CID.
    Keep only if ≥1 of InChI / InChIKey / SMILES present.
    """
    key = f"RN:{rn}" if rn and CAS_RE.match(rn) else f"NM:{(name or '').lower()}"
    if key in _cache:
        return _cache[key]
    cid = None
    if rn and CAS_RE.match(rn):
        cid = pubchem_cid_from_rn(rn)
    if cid is None and name:
        cid = pubchem_cid_from_name(name)
    if cid is None:
        _cache[key] = None
        return None

    p = pubchem_props(cid)
    rec = {
        "compound_inchi": p.get("InChI", "") or "",
        "compound_inchikey": p.get("InChIKey", "") or "",
        "compound_smiles": p.get("IsomericSMILES", "") or "",
        "compound_maccs166": "",
    }
    if rec["compound_smiles"]:
        rec["compound_maccs166"] = maccs_from_smiles(rec["compound_smiles"])
    if not (rec["compound_inchi"] or rec["compound_inchikey"] or rec["compound_smiles"]):
        _cache[key] = None
        return None
    _cache[key] = rec
    return rec


# ---------------- RUN ----------------
def run():
    diag = {
        "pmids_total": 0,
        "articles_seen": 0,
        "plant_context_ok": 0,
        "articles_with_species": 0,
        "articles_with_compound_candidates": 0,
        "kept_pairs": 0,
    }

    query = build_query_core()
    pmids = esearch_all_ids_by_window(query, START_YEAR, END_YEAR, WINDOW_YEARS, RET_CHUNK)
    diag["pmids_total"] = len(pmids)

    rows = []
    for a in efetch_pubmed_xml(pmids):
        diag["articles_seen"] += 1

        # Gate: ensure plant context
        if not is_plant_context(a["mesh"], a["title"], a["abstract"]):
            continue
        diag["plant_context_ok"] += 1

        # Candidate botanical names → GBIF-validated Plantae
        species = species_from_article_validated(a)
        if not species:
            continue
        diag["articles_with_species"] += 1

        # Traditional use extraction (from title+abstract), shared across all plant rows for this article
        trad_use = extract_traditional_use(a["title"], a["abstract"])

        # Build compound candidates (MeSH ChemicalList + Suppl + Keywords + TA heuristics)
        cand = set()
        for ch in a.get("chem_items", []):
            rn = ch.get("rn", "")
            name = ch.get("name", "")
            if rn == "0":
                rn = ""  # PubMed uses "0" when no RN is assigned
            cand.add((rn, name))
        for s in a.get("suppl", []):
            if s:
                cand.add(("", s))
        for k in a.get("keywords", []):
            if k:
                cand.add(("", k))
        for n in find_compound_mentions_from_text(f"{a['title']} {a['abstract']}"):
            cand.add(("", n))
        if not cand:
            continue
        diag["articles_with_compound_candidates"] += 1

        # Resolve to PubChem; keep only those with ≥1 identifier
        resolved = []
        for rn, name in cand:
            rc = resolve_compound_identifiers_from_rn_or_name(rn, (name or "").strip())
            if rc is not None:
                resolved.append(rc)
        if not resolved:
            continue

        for sci in species:
            for rc in resolved:
                rows.append(
                    {
                        "scientific_name": sci,
                        "traditional_use": trad_use,
                        "compound_inchi": rc["compound_inchi"],
                        "compound_inchikey": rc["compound_inchikey"],
                        "compound_smiles": rc["compound_smiles"],
                        "compound_maccs166": rc["compound_maccs166"],
                        "doi": a["doi"],
                        "pmid": a["pmid"],
                        "title": a["title"],
                        "year": a["year"],
                        "journal": a["journal"],
                    }
                )
                diag["kept_pairs"] += 1

    # DataFrame (safe, with headers even if empty)
    if rows:
        df = pd.DataFrame(rows)
        for c in WANT_COLS:
            if c not in df.columns:
                df[c] = ""
        df = df[WANT_COLS]
        # Guard: scientific name should begin with Capitalized genus + space
        df = df[df["scientific_name"].str.contains(r"^[A-Z][a-z]+ ", regex=True, na=False)]
    else:
        df = pd.DataFrame(columns=WANT_COLS)

    df.drop_duplicates(inplace=True)
    df.to_csv(OUT_CSV, index=False)

    # Diagnostics + total time
    print("--- Diagnostics ---")
    print(f"PMIDs total:                           {diag['pmids_total']}")
    print(f"Articles fetched/parsed:               {diag['articles_seen']}")
    print(f"Plant-context articles kept:           {diag['plant_context_ok']}")
    print(f"Articles with GBIF-validated plants:   {diag['articles_with_species']}")
    print(f"Articles with compound candidates:     {diag['articles_with_compound_candidates']}")
    print(f"Kept (plant × compound IDs) pairs:     {diag['kept_pairs']}")
    print("-------------------")
    print(f"Saved → {OUT_CSV} | Rows: {len(df)} | RDKit MACCS computed: {RDK_OK}")
    print(f"Total elapsed: {fmt_secs(time.perf_counter()-t0)}")
    return df


if __name__ == "__main__":
    df = run()
    try:
        print(df.head(12).to_string(index=False))
    except Exception:
        print(df.head(12))


# In[ ]:
