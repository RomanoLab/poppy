#!/usr/bin/env python
"""
rebuild_ontology.py — resumable, logged rebuild of the POPPy phytotherapy ontology.

This is a faithful port of ``notebooks/Ontology_Work_clean.ipynb`` into a single,
restartable CLI. Each stage loads the previous stage's RDF checkpoint from disk, does
its work, and saves its own checkpoint — so a failed or interrupted run resumes from the
last completed stage instead of starting over. Progress, counts and timings are logged to
both the console and a per-run logfile.

WHY THIS EXISTS (and how it differs from the notebook — read before trusting output):
  * Resumability. The notebook keeps one in-memory graph across cells; here every stage is
    independently runnable and re-entrant. Re-running a completed stage is a no-op unless
    --force is given (tracked in <work-dir>/state.json).
  * Deterministic IRIs. The notebook minted CMAUP chemical IRIs with ``abs(hash(smiles))``,
    which Python randomizes per process — fine in one kernel, broken across invocations.
    We use a stable SHA1-derived id (``stable_id``) so URIs are identical on every run.
  * Dependency-correct order. The notebook's cell order is not its data-flow order (e.g.
    paper/DOI linking consumed a CSV produced two stages later). Stages here run in the
    order their inputs actually require; the Dr. Duke's DOI CSV is built BEFORE paper
    linking, which now happens inside the drduke stage.
  * Plant-only scope (the point of this rebuild). Organism validation uses an OFFLINE local
    NCBI taxdump (names.dmp/nodes.dmp), NOT per-name web calls — the notebook's live Entrez+POWO
    validation took ~12 h for the full COCONUT set; the taxdump runs in minutes. Stages
    ``base_plants`` and ``coconut2_sdf`` keep only organisms under Viridiplantae (taxid 33090);
    this is the gate the original COCONUT 2.0 import skipped, which let bacteria/fungi/animals in.
    Toggle with --no-plants-only (old contaminated behavior); --keep-unmatched to retain names the
    taxdump can't resolve (default drops them → counts are a conservative floor).
  * ChEBI alignment (notebook Stage 13) depends on an ``ontology_ext`` package that is not
    in this repo; that stage is OPTIONAL and skipped automatically if the package is absent.

REQUIREMENTS
  * Run inside the build env:  conda activate poppy   (Python 3.11 + rdkit from conda-forge)
  * Env vars: PMACS_USER, ROMANO_DB_PASSWORD (PMACS opendata DB). ENTREZ_EMAIL is optional
    (no longer used for validation). Penn VPN must be up so romanodb1.pmacs.upenn.edu resolves.
  * Local NCBI taxdump in --taxdump-dir (default data/raw/taxdump/) — auto-downloads (~75 MB)
    on first run if absent.
  * Input files in --data-dir (default data/raw/) — see data/SOURCES.md and
    docs/nar-submission/REBUILD-RUNBOOK.md for the retrieval manifest.

USAGE
  python scripts/rebuild_ontology.py --list                 # show stages + status
  python scripts/rebuild_ontology.py                        # run all pending stages
  python scripts/rebuild_ontology.py --only drugcentral     # run one stage
  python scripts/rebuild_ontology.py --from cmaup           # run from a stage onward
  python scripts/rebuild_ontology.py --from cmaup --to chembl
  python scripts/rebuild_ontology.py --force --only stats   # re-run even if done
  python scripts/rebuild_ontology.py --check                # env/input preflight, no run

The headline deliverable (the protein-targets count) is written by the final ``stats``
stage to results/ontology_stats.json.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & logging
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO / "data" / "raw"
DEFAULT_WORK_DIR = REPO / "build"
SCAFFOLD = REPO / "data" / "ontology" / "poppystructure.rdf"
STATS_OUT = REPO / "results" / "ontology_stats.json"

log = logging.getLogger("rebuild")


def setup_logging(work_dir: Path, verbose: bool) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    logdir = work_dir / "logs"
    logdir.mkdir(exist_ok=True)
    logfile = logdir / f"rebuild_{time.strftime('%Y%m%d_%H%M%S')}.log"
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    fh.setLevel(logging.DEBUG)
    log.handlers[:] = [sh, fh]
    return logfile


# ---------------------------------------------------------------------------
# Heavy imports (deferred so --list/--help work without the build env)
# ---------------------------------------------------------------------------
def _env_error(missing: str) -> str:
    in_poppy = "/envs/poppy/" in sys.executable
    hint = (
        "Run inside the build env:  conda activate poppy  &&  "
        "python scripts/rebuild_ontology.py ..."
    )
    if in_poppy:
        hint = (
            "The poppy env is active but a dependency is missing — reinstall:\n"
            '  conda activate poppy && pip install -e ".[dev]"\n'
            "  (rdkit comes from conda-forge: "
            "mamba install -n poppy -c conda-forge rdkit)"
        )
    return (
        f"\nMissing build dependency: {missing!r}\n"
        f"Current interpreter: {sys.executable}\n"
        f"(This is almost always the wrong env — your shell auto-activates conda 'base',\n"
        f" which does NOT have the build deps. The deps live in the 'poppy' env.)\n\n"
        f"{hint}\n"
    )


def _imports():
    global pd, requests, psycopg2, tqdm, Chem, Descriptors, MACCSkeys, rdMolDescriptors
    global RDInchi, HAS_INCHI, Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef, BNode
    global XSD, SKOS, Entrez
    try:
        import pandas as pd  # noqa
        import requests  # noqa
        import psycopg2  # noqa
        from tqdm import tqdm  # noqa
        from rdkit import Chem  # noqa
        from rdkit.Chem import Descriptors, MACCSkeys, rdMolDescriptors  # noqa

        try:
            from rdkit.Chem import inchi as RDInchi  # noqa

            HAS_INCHI = True
        except Exception:
            RDInchi, HAS_INCHI = None, False
        from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef, BNode  # noqa
        from rdflib.namespace import XSD, SKOS  # noqa
        from Bio import Entrez  # noqa
    except ModuleNotFoundError as e:
        sys.exit(_env_error(e.name))


# ---------------------------------------------------------------------------
# Namespace, predicates, phytochemical classes (notebook Cell 2)
# ---------------------------------------------------------------------------
NS_STR = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"


class Ctx:
    """Shared build context: namespace, predicates, config, paths."""

    def __init__(self, args):
        self.NS = Namespace(NS_STR)
        N = self.NS
        self.isDerivedFrom = N.isDerivedFrom
        self.hasCompound = N.hasCompound
        self.hasMolecularWeight = N.hasMolecularWeight
        self.hasMolecularFormula = N.hasMolecularFormula
        self.hasCommonName = N.hasCommonName
        self.hasIUPACName = N.hasIUPACName
        self.hasSMILES = N.hasSMILES
        self.hasCanonicalSMILES = N.hasCanonicalSMILES
        self.hasMACCs = N.hasMACCs
        self.hasInChIKey = N.hasInChIKey
        self.hasATC = N.hasATC
        self.hasDOI = N.hasDOI
        self.hasPaper = N.hasPaper
        self.hasClinicalStudy = N.hasClinicalStudy
        self.hasEvidenceText = N.hasEvidenceText
        self.hasNCTId = N.hasNCTId
        self.hasTherapeuticEffect = N.hasTherapeuticEffect
        self.targetsPathway = N.targetsPathway
        self.hasValue = N.hasValue
        self.hasGenus = N.hasGenus
        self.hasSpecies = N.hasSpecies
        self.hasTaxon = N.hasTaxon
        self.hasNPSuper = N.hasNPClassifierSuperclass
        self.hasNPClass = N.hasNPClassifierClass
        self.hasNPPath = N.hasNPClassifierPathway
        self.PHYTOCHEM_CLASSES = {
            "Carotenoid": N.Carotenoid,
            "DietaryFiber": N.DietaryFiber,
            "Isoprenoid": N.Isoprenoid,
            "Phytosterol": N.Phytosterol,
            "Polyphenol": N.Polyphenol,
            "Polysaccharide": N.Polysaccharide,
            "Saponin": N.Saponin,
            "Unknown": N.Unknown,
        }
        # config
        self.data_dir = Path(args.data_dir)
        self.work_dir = Path(args.work_dir)
        self.plants_only = args.plants_only
        self.keep_unmatched = args.keep_unmatched
        self.taxdump_dir = Path(args.taxdump_dir)
        self.workers = args.workers
        # NPClassifier endpoint (template with one {} for the URL-encoded SMILES). Default is the
        # public GNPS2 server (small/academic → throttles); override with a LOCAL server for scale.
        self.npc_url = (
            getattr(args, "npclassifier_url", None)
            or os.environ.get("NPCLASSIFIER_URL")
            or "https://npclassifier.gnps2.org/classify?smiles={}"
        )
        # finalize the NPClassifier stage from the current cache without calling the API
        # (escape hatch for a few stuck/pathological SMILES); leaves them uncached to retry later.
        self.npclass_finalize = getattr(args, "npclass_finalize", False)
        self.pmacs_host = os.environ.get("PMACS_HOST", "romanodb1.pmacs.upenn.edu")
        self.pmacs_user = os.environ.get("PMACS_USER", "")
        self.pmacs_pass = os.environ.get("ROMANO_DB_PASSWORD")
        self.entrez_email = os.environ.get("ENTREZ_EMAIL", "")
        Entrez.email = self.entrez_email
        # caches live in work_dir
        self.cache_dir = self.work_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._taxonomy = None

    def taxonomy(self):
        """Lazy-load the local NCBI taxdump once per process (offline plant validation)."""
        if self._taxonomy is None:
            from poppy.io.taxonomy_local import LocalTaxonomy

            log.info("  loading local NCBI taxdump from %s …", self.taxdump_dir)
            t0 = time.time()
            self._taxonomy = LocalTaxonomy.ensure(self.taxdump_dir)
            log.info("  taxdump ready (%.1fs)", time.time() - t0)
        return self._taxonomy

    # ---- input file resolution ----
    def inp(self, *names) -> Path:
        """Resolve an input file by trying several candidate names in data_dir."""
        for n in names:
            p = self.data_dir / n
            if p.exists():
                return p
        raise FileNotFoundError(
            f"Required input not found in {self.data_dir}: tried {list(names)}. "
            f"See data/SOURCES.md / docs/nar-submission/REBUILD-RUNBOOK.md."
        )

    def inp_opt(self, *names):
        for n in names:
            p = self.data_dir / n
            if p.exists():
                return p
        return None

    def ckpt(self, name: str) -> Path:
        return self.work_dir / name

    # ---- DB connections ----
    def sql_conn(self, dbname="opendata"):
        if not self.pmacs_pass:
            raise RuntimeError("ROMANO_DB_PASSWORD not set — cannot reach PMACS opendata DB.")
        if not self.pmacs_user:
            raise RuntimeError("PMACS_USER not set — set it to your opendata account.")
        return psycopg2.connect(
            host=self.pmacs_host,
            port=5432,
            dbname=dbname,
            user=self.pmacs_user,
            password=self.pmacs_pass,
            sslmode="prefer",
            gssencmode="disable",
        )

    def drugcentral_conn(self):
        return psycopg2.connect(
            host="unmtid-dbs.net",
            port=5433,
            dbname="drugcentral",
            user="drugman",
            password="dosage",
        )


# ---------------------------------------------------------------------------
# Helpers (notebook Cell 2) — pure functions, take/return rdflib objects
# ---------------------------------------------------------------------------
def sanitize_for_uri(text) -> str:
    s = re.sub(r"\s+", "_", str(text).strip())
    s = re.sub(r"[^\w\-\.]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:200] or "unknown"


def stable_id(value) -> int:
    """Deterministic positive int from a string (replaces notebook's process-random hash)."""
    return int(hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:15], 16)


def make_uri(ctx, kind, value):
    return URIRef(f"{ctx.NS}{kind}_{sanitize_for_uri(value)}")


def canon_smiles(smiles) -> str:
    s = (smiles or "").strip()
    if not s:
        return ""
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m, canonical=True) if m else ""


def normalize_doi(doi) -> str:
    d = str(doi).strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^(doi|dois)\s*:?\s*", "", d, flags=re.I)
    return d.rstrip(").,;]")


def find_class_by_label_or_local(g, names):
    names = list(names)
    for n in names:
        for s in g.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in g:
                return s
    for s in g.subjects(RDF.type, OWL.Class):
        local = str(s).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        if local in names:
            return s
    return None


def subclass_closure(g, root) -> set:
    out = {root}
    q = deque([root])
    while q:
        c = q.popleft()
        for sub in g.subjects(RDFS.subClassOf, c):
            if (sub, RDF.type, OWL.Class) in g and sub not in out:
                out.add(sub)
                q.append(sub)
    return out


def classify_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ["Unknown"]
    classes = []
    mw = Descriptors.MolWt(mol)
    num_rings = Descriptors.RingCount(mol)
    num_oh = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[OH]")))
    num_c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    num_o = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")
    num_double = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C=C")))
    if num_rings >= 2 and num_oh >= 2:
        classes.append("Polyphenol")
    if num_c >= 30 and num_double >= 5:
        classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1:
        classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5:
        classes.append("Saponin")
    if mw > 500 and num_o > 10:
        classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15:
        classes.append("DietaryFiber")
    if "C=C" in (smiles or "") and num_c % 5 == 0:
        classes.append("Isoprenoid")
    return classes or ["Unknown"]


def set_mw_range_union(ctx, g):
    p = ctx.hasMolecularWeight
    if (p, RDF.type, OWL.DatatypeProperty) not in g:
        g.add((p, RDF.type, OWL.DatatypeProperty))
        g.add((p, RDFS.label, Literal("hasMolecularWeight")))
    for o in list(g.objects(p, RDFS.range)):
        g.remove((p, RDFS.range, o))
    u, a, b = BNode(), BNode(), BNode()
    g.add((u, RDF.type, OWL.DataRange))
    g.add((u, OWL.unionOf, a))
    g.add((a, RDF.first, XSD.float))
    g.add((a, RDF.rest, b))
    g.add((b, RDF.first, XSD.double))
    g.add((b, RDF.rest, RDF.nil))
    g.add((p, RDFS.range, u))


def load_graph(path) -> "Graph":
    g = Graph()
    fmt = "turtle" if str(path).lower().endswith((".ttl", ".turtle")) else "xml"
    t0 = time.time()
    g.parse(str(path), format=fmt)
    log.info("  loaded %s (%s triples, %.1fs)", Path(path).name, f"{len(g):,}", time.time() - t0)
    return g


def save_graph(g, path):
    fmt = "turtle" if str(path).lower().endswith((".ttl", ".turtle")) else "xml"
    t0 = time.time()
    g.serialize(destination=str(path), format=fmt)
    log.info("  saved → %s (%s triples, %.1fs)", Path(path).name, f"{len(g):,}", time.time() - t0)


# ===========================================================================
# STAGES
# Each stage(ctx, state) -> dict of counts. Loads its input checkpoint and
# saves its output checkpoint. Checkpoint filenames are the stage 'out' values.
# ===========================================================================


def stage_base_plants(ctx):
    """Load scaffold; classify COCONUT organisms via the local NCBI taxdump; add Plant individuals.

    SPEED FIX vs. notebook: the notebook validated each organism with live NCBI Entrez + POWO
    calls (~2 HTTP round-trips + a throttle sleep each → ~12 h for the full COCONUT set). We use
    an OFFLINE taxdump lookup instead — the whole set classifies in seconds. 'plant' == under
    Viridiplantae (taxid 33090). When --plants-only (default), only plants are minted; unmatched
    names are dropped unless --keep-unmatched.
    """
    scaffold = ctx.inp_opt("poppystructure.rdf") or SCAFFOLD
    g = load_graph(scaffold)
    N = ctx.NS
    if (N.Plant, RDF.type, OWL.Class) not in g:
        g.add((N.Plant, RDF.type, OWL.Class))
        g.add((N.Plant, RDFS.subClassOf, N.PlantTaxonomy))
        g.add((N.Plant, RDFS.label, Literal("Plant")))

    tax = ctx.taxonomy()
    with ctx.sql_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name FROM coconut.organisms")
        organisms = cur.fetchall()
    log.info("  %s organisms from coconut.organisms", f"{len(organisms):,}")

    added = nonplant = unmatched = 0
    for org_id, name in tqdm(organisms, desc="classify organisms"):
        if not name:
            continue
        verdict, taxid = tax.classify_name(name)
        keep = (
            verdict == "plant"
            or (verdict == "unmatched" and ctx.keep_unmatched)
            or (not ctx.plants_only)
        )
        if verdict == "nonplant":
            nonplant += 1
        elif verdict == "unmatched":
            unmatched += 1
        if not keep:
            continue
        uri = N[f"Organism_{org_id}"]
        g.add((uri, RDF.type, OWL.NamedIndividual))
        g.add((uri, RDF.type, N.Plant))
        g.add((uri, RDFS.label, Literal(name)))
        if taxid:
            g.add((uri, ctx.hasTaxon, Literal(taxid)))
        added += 1
    log.info(
        "  classified: kept=%s nonplant(dropped)=%s unmatched=%s (keep_unmatched=%s)",
        added,
        nonplant,
        unmatched,
        ctx.keep_unmatched,
    )
    save_graph(g, ctx.ckpt("01_augmented.rdf"))
    return {
        "plants_added": added,
        "organisms_seen": len(organisms),
        "nonplant_dropped": nonplant,
        "unmatched": unmatched,
    }


def stage_coconut_chemicals(ctx):
    """Add chemical individuals + properties + isDerivedFrom from COCONUT DB."""
    g = load_graph(ctx.ckpt("01_augmented.rdf"))
    with ctx.sql_conn() as conn:
        DF = pd.read_sql(
            """
            SELECT p.molecule_id, p.chemical_class, mo.organism_id, p.molecular_weight,
                   p.molecular_formula, m.name AS molecule_name, m.iupac_name,
                   e.canonical_smiles
            FROM coconut.properties p
            JOIN coconut.molecule_organism mo ON p.molecule_id = mo.molecule_id
            JOIN coconut.molecules m            ON p.molecule_id = m.id
            JOIN coconut.entries e              ON p.molecule_id = e.molecule_id
            """,
            conn,
        ).fillna("")
    log.info("  %s chemical-organism links from COCONUT", f"{len(DF):,}")

    set_mw_range_union(ctx, g)
    added_chems, total_links = set(), 0
    for _, row in tqdm(DF.iterrows(), total=len(DF), desc="coconut chemicals"):
        chem_uri = make_uri(ctx, "Chemical", row["molecule_id"])
        org_uri = make_uri(ctx, "Organism", row["organism_id"])
        if chem_uri not in added_chems:
            g.add((chem_uri, RDF.type, OWL.NamedIndividual))
            smi = row["canonical_smiles"]
            for cls in classify_smiles(smi):
                cls_uri = ctx.PHYTOCHEM_CLASSES.get(cls)
                if cls_uri and (cls_uri, RDF.type, OWL.Class) in g:
                    g.add((chem_uri, RDF.type, cls_uri))
            if row["molecular_weight"] not in ("", None):
                try:
                    g.add(
                        (chem_uri, ctx.hasMolecularWeight, Literal(float(row["molecular_weight"])))
                    )
                except ValueError:
                    pass
            if row["molecular_formula"]:
                g.add((chem_uri, ctx.hasMolecularFormula, Literal(row["molecular_formula"])))
            if row["molecule_name"]:
                g.add((chem_uri, ctx.hasCommonName, Literal(row["molecule_name"])))
            if row["iupac_name"]:
                g.add((chem_uri, ctx.hasIUPACName, Literal(row["iupac_name"])))
            if smi:
                g.add((chem_uri, ctx.hasSMILES, Literal(smi)))
                g.add((chem_uri, RDFS.label, Literal(smi)))
            added_chems.add(chem_uri)
        g.add((chem_uri, ctx.isDerivedFrom, org_uri))
        total_links += 1
    save_graph(g, ctx.ckpt("02_chemicals.rdf"))
    return {"chemicals_added": len(added_chems), "derived_links": total_links}


def stage_cmaup(ctx):
    """Build cmaup_clean.csv and load CMAUP plants/chemicals/links."""
    g = load_graph(ctx.ckpt("02_chemicals.rdf"))
    N = ctx.NS
    assoc = pd.read_csv(
        ctx.inp("CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt"),
        sep="\t",
        header=None,
        names=["Plant_ID", "Ingredient_ID"],
    )
    plants = pd.read_csv(ctx.inp("CMAUPv2.0_download_Plants.txt"), sep="\t")
    ingr_target = pd.read_csv(
        ctx.inp("CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt"),
        sep="\t",
    )
    ingredients = pd.read_csv(
        ctx.inp(
            "CMAUPv2.0_download_Ingredients_All (1).txt", "CMAUPv2.0_download_Ingredients_All.txt"
        ),
        sep="\t",
    ).rename(columns={"np_id": "Ingredient_ID"})
    targets = pd.read_csv(
        ctx.inp("CMAUPv2.0_download_Targets.txt"), sep="\t", dtype=str, low_memory=False
    )

    df = (
        assoc.merge(plants[["Plant_ID", "Plant_Name"]], on="Plant_ID", how="left")
        .merge(ingr_target[["Ingredient_ID", "Target_ID"]], on="Ingredient_ID", how="left")
        .merge(
            ingredients[["Ingredient_ID", "pref_name", "MW", "SMILES", "iupac_name"]],
            on="Ingredient_ID",
            how="left",
        )
    ).drop_duplicates()
    targets.columns = [c.strip() for c in targets.columns]
    tmap = dict(
        zip(
            targets["Target_ID"].astype(str).str.strip(),
            targets["Protein_Name"].astype(str).str.strip(),
        )
    )
    df["TargetedPathway"] = (
        df["Target_ID"].astype(str).str.strip().map(tmap).fillna(df["Target_ID"])
    )
    df = df.drop(columns=["Target_ID"])
    df["Molecular_Formula"] = df["SMILES"].apply(
        lambda s: (
            rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(s))
            if Chem.MolFromSmiles(str(s) or "")
            else None
        )
    )
    df = df.dropna(subset=["SMILES"]).drop_duplicates(subset="SMILES")
    df["SMILES"] = df["SMILES"].astype(str)
    df["Phytochemical_Class"] = df["SMILES"].apply(lambda s: ";".join(classify_smiles(s)))
    df = df.drop(columns=["Plant_ID", "Ingredient_ID"], errors="ignore").replace("n.a.", "")
    cmaup_csv = ctx.work_dir / "cmaup_clean.csv"
    df.to_csv(cmaup_csv, index=False)
    log.info("  cmaup_clean.csv: %s rows", f"{len(df):,}")

    cmaup_df = pd.read_csv(cmaup_csv, na_values=["", "nan", "NaN"]).dropna(
        subset=["SMILES", "Phytochemical_Class", "Plant_Name"]
    )
    for col in [
        "SMILES",
        "Phytochemical_Class",
        "Plant_Name",
        "Molecular_Formula",
        "iupac_name",
        "pref_name",
    ]:
        cmaup_df[col] = cmaup_df[col].astype(str).str.strip()
    cmaup_df["MW"] = pd.to_numeric(cmaup_df["MW"], errors="coerce")
    cmaup_df = cmaup_df.drop_duplicates(subset=["SMILES"])

    existing_plant_labels = {
        str(o).strip().lower()
        for s, _, o in g.triples((None, RDFS.label, None))
        if (s, RDF.type, N.Plant) in g
    }
    plants_added = 0
    for name in cmaup_df["Plant_Name"].drop_duplicates():
        if name.lower() in existing_plant_labels:
            continue
        uri = N[f"Plant_{name.replace(' ', '_')}"]
        g.add((uri, RDF.type, OWL.NamedIndividual))
        g.add((uri, RDF.type, N.Plant))
        g.add((uri, RDFS.label, Literal(name)))
        plants_added += 1

    existing_smiles = {str(o).strip() for _, _, o in g.triples((None, ctx.hasSMILES, None))}
    chems_added = 0
    for _, row in cmaup_df.iterrows():
        if row["SMILES"] in existing_smiles:
            continue
        uri = N[f"Chemical_{stable_id(row['SMILES'])}"]
        g.add((uri, RDF.type, OWL.NamedIndividual))
        for cls in row["Phytochemical_Class"].split(";"):
            cls_uri = ctx.PHYTOCHEM_CLASSES.get(cls.strip())
            if cls_uri:
                g.add((uri, RDF.type, cls_uri))
        g.add((uri, ctx.hasSMILES, Literal(row["SMILES"])))
        g.add((uri, RDFS.label, Literal(row["SMILES"])))
        if pd.notna(row["MW"]):
            g.add((uri, ctx.hasMolecularWeight, Literal(row["MW"])))
        if pd.notna(row["Molecular_Formula"]):
            g.add((uri, ctx.hasMolecularFormula, Literal(row["Molecular_Formula"])))
        if pd.notna(row["iupac_name"]):
            g.add((uri, ctx.hasIUPACName, Literal(row["iupac_name"])))
        if pd.notna(row["pref_name"]):
            g.add((uri, ctx.hasCommonName, Literal(row["pref_name"])))
        existing_smiles.add(row["SMILES"])
        chems_added += 1

    links_added = 0
    existing_links = {(str(s), str(o)) for s, _, o in g.triples((None, ctx.isDerivedFrom, None))}
    for _, row in cmaup_df.iterrows():
        chem_uri = N[f"Chemical_{stable_id(row['SMILES'])}"]
        plant_uri = N[f"Plant_{row['Plant_Name'].replace(' ', '_')}"]
        if (str(chem_uri), str(plant_uri)) not in existing_links:
            g.add((chem_uri, ctx.isDerivedFrom, plant_uri))
            existing_links.add((str(chem_uri), str(plant_uri)))
            links_added += 1
    save_graph(g, ctx.ckpt("03_cmaup.rdf"))
    return {
        "plants_added": plants_added,
        "chemicals_added": chems_added,
        "links_added": links_added,
    }


def stage_clinical_trials(ctx):
    """Add CMAUP Plant–Human-Disease clinical-trial evidence."""
    g = load_graph(ctx.ckpt("03_cmaup.rdf"))
    N = ctx.NS
    TRIAL_CLASS = (
        find_class_by_label_or_local(g, ["ClinicalTrial", "Clinical Trial"]) or N.ClinicalTrial
    )
    RESEARCH_ROOT = find_class_by_label_or_local(g, ["ResearchConcept", "Research Concept"])
    if (TRIAL_CLASS, RDF.type, OWL.Class) not in g:
        g.add((TRIAL_CLASS, RDF.type, OWL.Class))
        g.add((TRIAL_CLASS, RDFS.label, Literal("ClinicalTrial")))
    if RESEARCH_ROOT and (TRIAL_CLASS, RDFS.subClassOf, RESEARCH_ROOT) not in g:
        g.add((TRIAL_CLASS, RDFS.subClassOf, RESEARCH_ROOT))
    for prop, lbl in [
        (ctx.hasClinicalStudy, "hasClinicalStudy"),
        (ctx.hasEvidenceText, "hasEvidenceText"),
        (ctx.hasNCTId, "hasNCTId"),
    ]:
        if (prop, RDF.type, OWL.ObjectProperty) not in g and (
            prop,
            RDF.type,
            OWL.DatatypeProperty,
        ) not in g:
            ptype = OWL.ObjectProperty if prop is ctx.hasClinicalStudy else OWL.DatatypeProperty
            g.add((prop, RDF.type, ptype))
            g.add((prop, RDFS.label, Literal(lbl)))
    for o in list(g.objects(ctx.hasClinicalStudy, RDFS.range)):
        g.remove((ctx.hasClinicalStudy, RDFS.range, o))
    g.add((ctx.hasClinicalStudy, RDFS.range, TRIAL_CLASS))

    phda_path = ctx.inp(
        "CMAUPv2.0_download_Plant_Human_Disease_Associations.txt",
        "CMAUPv2.0_download_Plant_Human_Disease_Associations.tsv",
    )
    phda = pd.read_csv(phda_path, sep="\t", dtype=str).fillna("")
    plants_df = pd.read_csv(ctx.inp("CMAUPv2.0_download_Plants.txt"), sep="\t", dtype=str).fillna(
        ""
    )
    pid_to_name = dict(zip(plants_df["Plant_ID"], plants_df["Plant_Name"]))
    SPLIT_RE = re.compile(r"\s*(?:\|\||\||;;|;|\/\/|,|\n|\r)\s*")

    def split_multi(val):
        if not val or str(val).lower() in {"na", "n/a", "none"}:
            return []
        seen, out = set(), []
        for p in SPLIT_RE.split(str(val).strip()):
            p = p.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def mint_trial(plant_id, ev_text):
        ncts = sorted(set(re.findall(r"NCT\d{8}", ev_text)))
        local = (
            f"CT_{ncts[0]}"
            if ncts
            else (
                f"CT_p{sanitize_for_uri(plant_id)}_"
                f"{hashlib.sha1(f'{plant_id}|{ev_text}'.encode()).hexdigest()[:12]}"
            )
        )
        uri = N[f"ClinicalTrial_{local}"]
        if (uri, RDF.type, TRIAL_CLASS) not in g:
            g.add((uri, RDF.type, OWL.NamedIndividual))
            g.add((uri, RDF.type, TRIAL_CLASS))
            label = ncts[0] if ncts else (ev_text[:120] + ("…" if len(ev_text) > 120 else ""))
            g.add((uri, RDFS.label, Literal(label)))
            g.add((uri, ctx.hasEvidenceText, Literal(ev_text, datatype=XSD.string)))
            for n in ncts:
                g.add((uri, ctx.hasNCTId, Literal(n)))
        return uri

    plant_key_to_chems = defaultdict(set)
    for chem_uri, _, plant_uri in g.triples((None, ctx.isDerivedFrom, None)):
        pl_local = str(plant_uri).rsplit("#", 1)[-1]
        if pl_local.startswith("Plant_"):
            plant_key_to_chems[pl_local[len("Plant_") :]].add(chem_uri)

    trials = plant_links = chem_links = 0
    for _, row in tqdm(phda.iterrows(), total=len(phda), desc="clinical trials"):
        pid = str(row["Plant_ID"]).strip()
        name = pid_to_name.get(pid)
        if not name:
            continue
        p_uri = N[f"Plant_{sanitize_for_uri(name)}"]
        if not any(g.triples((p_uri, None, None))):
            continue
        key = sanitize_for_uri(name)
        for ev in split_multi(row.get("Association_by_Clinical_Trials_of_Plant", "")):
            t = mint_trial(pid, ev)
            g.add((p_uri, ctx.hasClinicalStudy, t))
            trials += 1
            plant_links += 1
        for ev in split_multi(row.get("Association_by_Clinical_Trials_of_Plant_Ingredients", "")):
            t = mint_trial(pid, ev)
            g.add((p_uri, ctx.hasClinicalStudy, t))
            trials += 1
            plant_links += 1
            for chem in plant_key_to_chems.get(key, []):
                g.add((chem, ctx.hasClinicalStudy, t))
                chem_links += 1
    save_graph(g, ctx.ckpt("04_trials.rdf"))
    return {"trials": trials, "plant_trial_links": plant_links, "chem_trial_links": chem_links}


def stage_maccs(ctx):
    """Compute MACCS fingerprints for chemicals."""
    g = load_graph(ctx.ckpt("04_trials.rdf"))
    chem_classes = set(ctx.PHYTOCHEM_CLASSES.values())
    added = 0
    subs = [s for s, _, o in g.triples((None, RDF.type, None)) if o in chem_classes]
    for s in tqdm(set(subs), desc="MACCS"):
        if (s, ctx.hasMACCs, None) in g:
            continue
        smi = next((str(x) for _, _, x in g.triples((s, ctx.hasSMILES, None))), "").strip()
        if not smi:
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol:
            g.add((s, ctx.hasMACCs, Literal(MACCSkeys.GenMACCSKeys(mol).ToBitString())))
            added += 1
    save_graph(g, ctx.ckpt("05_maccs.rdf"))
    return {"maccs_added": added}


def _ensure_factory(ctx, g, cls, prefix):
    cache = {}

    def ensure(label):
        if label in cache:
            return cache[label]
        uri = ctx.NS[f"{prefix}_{sanitize_for_uri(label)}"]
        if not any(g.triples((uri, None, None))):
            g.add((uri, RDF.type, OWL.NamedIndividual))
            g.add((uri, RDF.type, cls))
            g.add((uri, RDFS.label, Literal(label)))
            g.add((uri, ctx.hasValue, Literal(label, datatype=XSD.string)))
        cache[label] = uri
        return uri

    return ensure


def stage_drugcentral(ctx):
    """DrugCentral: InChIKeys + action types (effects), targets, ATC codes."""
    g = load_graph(ctx.ckpt("05_maccs.rdf"))
    N = ctx.NS
    for prop, ptype, lbl in [
        (ctx.hasInChIKey, OWL.DatatypeProperty, "hasInChIKey"),
        (ctx.hasTherapeuticEffect, OWL.ObjectProperty, "hasTherapeuticEffect"),
        (ctx.targetsPathway, OWL.ObjectProperty, "targetsPathway"),
        (ctx.hasValue, OWL.DatatypeProperty, "hasValue"),
        (ctx.hasATC, OWL.DatatypeProperty, "hasATC"),
    ]:
        if (prop, RDF.type, ptype) not in g:
            g.add((prop, RDF.type, ptype))
            g.add((prop, RDFS.label, Literal(lbl)))

    if HAS_INCHI:
        for s, _, smi in list(g.triples((None, ctx.hasSMILES, None))):
            if (s, ctx.hasInChIKey, None) in g:
                continue
            mol = Chem.MolFromSmiles(str(smi))
            if mol:
                try:
                    ik = RDInchi.MolToInchiKey(mol)
                    if ik:
                        g.add((s, ctx.hasInChIKey, Literal(ik)))
                except Exception:
                    pass
    inchikey_to_subj = {str(o): s for s, _, o in g.triples((None, ctx.hasInChIKey, None))}
    inchis = list(inchikey_to_subj.keys())
    log.info("  chemicals with InChIKey: %s", f"{len(inchis):,}")

    TherapeuticEffectCls = (
        find_class_by_label_or_local(g, ["TherapeuticEffect"]) or N.TherapeuticEffect
    )
    PathwayClass = find_class_by_label_or_local(g, ["Pathway"])
    if PathwayClass is None:
        raise RuntimeError("Pathway class not found in ontology — required for target linking.")

    action_df = target_df = atc_df = pd.DataFrame()
    if inchis:
        try:
            with ctx.drugcentral_conn() as conn:
                action_df = pd.read_sql(
                    "SELECT s.inchikey, atf.action_type FROM structures s "
                    "JOIN act_table_full atf ON s.id = atf.struct_id "
                    "WHERE s.inchikey = ANY(%s) AND atf.action_type IS NOT NULL",
                    conn,
                    params=(inchis,),
                )
                target_df = pd.read_sql(
                    "SELECT s.inchikey, td.name AS target FROM structures s "
                    "JOIN act_table_full atf ON s.id = atf.struct_id "
                    "JOIN target_dictionary td ON atf.target_id = td.id "
                    "WHERE s.inchikey = ANY(%s)",
                    conn,
                    params=(inchis,),
                )
                atc_df = pd.read_sql(
                    "SELECT s.inchikey, a.code AS atc_code FROM structures s "
                    "JOIN struct2atc s2a ON s.id = s2a.struct_id "
                    "JOIN atc a ON s2a.atc_code = a.code "
                    "WHERE s.inchikey = ANY(%s)",
                    conn,
                    params=(inchis,),
                )
        except Exception as e:
            log.warning("  DrugCentral query failed: %s", e)
    log.info("  action=%s target=%s atc=%s", len(action_df), len(target_df), len(atc_df))

    ensure_effect = _ensure_factory(ctx, g, TherapeuticEffectCls, "TherapeuticEffect")
    ensure_pathway = _ensure_factory(ctx, g, PathwayClass, "Pathway")
    eff = tgt = atc = 0
    for _, row in action_df.iterrows():
        s = inchikey_to_subj.get(row["inchikey"])
        a = str(row["action_type"]).strip()
        if s and a:
            g.add((s, ctx.hasTherapeuticEffect, ensure_effect(a)))
            eff += 1
    for _, row in target_df.iterrows():
        s = inchikey_to_subj.get(row["inchikey"])
        t = str(row["target"]).strip()
        if s and t:
            g.add((s, ctx.targetsPathway, ensure_pathway(t)))
            tgt += 1
    for _, row in atc_df.iterrows():
        s = inchikey_to_subj.get(row["inchikey"])
        c = row["atc_code"]
        if s and c:
            g.add((s, ctx.hasATC, Literal(c)))
            atc += 1
    # stash atc_df for chembl stage's "filtered ATC" pass via a side CSV
    if not atc_df.empty:
        atc_df.to_csv(ctx.work_dir / "_drugcentral_atc.csv", index=False)
    save_graph(g, ctx.ckpt("06_drugcentral.rdf"))
    return {"effect_links": eff, "target_links": tgt, "atc_links": atc, "inchikeys": len(inchis)}


def stage_chembl(ctx):
    """ChEMBL drug mechanisms → targets/effects via canonical SMILES; filtered ATC."""
    g = load_graph(ctx.ckpt("06_drugcentral.rdf"))
    mech_path = ctx.inp("ChEMBL_drug_mechanisms.csv")
    try:
        mech_df = pd.read_csv(mech_path, sep=";")
        if mech_df.shape[1] == 1:
            mech_df = pd.read_csv(mech_path)
    except Exception:
        mech_df = pd.read_csv(mech_path)
    mech_df = mech_df.fillna("")

    def pick(df, opts):
        return next((c for c in opts if c in df.columns), None)

    COL_SMI = pick(mech_df, ["Smiles", "SMILES", "smiles", "Canonical_smiles"])
    COL_TNAME = pick(mech_df, ["Target Name", "TargetName", "Target"])
    COL_ATYPE = pick(mech_df, ["Action Type", "ActionType", "Action"])
    if not COL_SMI:
        raise KeyError("No SMILES column in ChEMBL mechanisms CSV")
    mech_df[COL_SMI] = mech_df[COL_SMI].astype(str).map(canon_smiles)

    CHEM_ROOT = find_class_by_label_or_local(g, ["ChemicalConcept", "Chemical Concept"])
    chem_cls = subclass_closure(g, CHEM_ROOT) if CHEM_ROOT else set()
    chem_subs = {s for cls in chem_cls for s in g.subjects(RDF.type, cls)}
    ont_can_to_subj = {}
    for s in chem_subs:
        for _, _, smi in g.triples((s, ctx.hasSMILES, None)):
            c = canon_smiles(str(smi))
            if c:
                ont_can_to_subj.setdefault(c, s)

    PathwayClass = find_class_by_label_or_local(g, ["Pathway"]) or ctx.NS.Pathway
    TherapeuticEffectCls = (
        find_class_by_label_or_local(g, ["TherapeuticEffect"]) or ctx.NS.TherapeuticEffect
    )
    ensure_pathway = _ensure_factory(ctx, g, PathwayClass, "Pathway")
    ensure_effect = _ensure_factory(ctx, g, TherapeuticEffectCls, "TherapeuticEffect")

    tp = te = 0
    for _, row in mech_df.iterrows():
        smi = row[COL_SMI]
        if not smi:
            continue
        subj = ont_can_to_subj.get(smi)
        if not subj:
            continue
        if COL_TNAME:
            t = str(row[COL_TNAME]).strip()
            if t and t.lower() != "nan":
                g.add((subj, ctx.targetsPathway, ensure_pathway(t)))
                tp += 1
        if COL_ATYPE:
            a = str(row[COL_ATYPE]).strip()
            if a and a.lower() != "nan":
                g.add((subj, ctx.hasTherapeuticEffect, ensure_effect(a)))
                te += 1

    # filtered ATC (only chemicals that gained a ChEMBL/DrugCentral link)
    added_atc = 0
    atc_csv = ctx.work_dir / "_drugcentral_atc.csv"
    if atc_csv.exists():
        atc_df = pd.read_csv(atc_csv).fillna("")
        enriched = set(g.subjects(ctx.targetsPathway, None)) | set(
            g.subjects(ctx.hasTherapeuticEffect, None)
        )
        enriched_ik = {
            str(o) for s in enriched for _, _, o in g.triples((s, ctx.hasInChIKey, None))
        }
        ik_to_subj = {str(o): s for s, _, o in g.triples((None, ctx.hasInChIKey, None))}
        for _, row in atc_df.iterrows():
            if row["inchikey"] in enriched_ik:
                subj = ik_to_subj.get(row["inchikey"])
                if subj and row["atc_code"]:
                    g.add((subj, ctx.hasATC, Literal(row["atc_code"])))
                    added_atc += 1
    save_graph(g, ctx.ckpt("07_chembl.rdf"))
    return {"targetsPathway_links": tp, "effect_links": te, "filtered_atc": added_atc}


def stage_canonical_inverse(ctx):
    """Add hasCanonicalSMILES + plant→chemical inverse (hasCompound) + missing labels."""
    g = load_graph(ctx.ckpt("07_chembl.rdf"))
    if (ctx.hasCompound, RDF.type, OWL.ObjectProperty) not in g:
        g.add((ctx.hasCompound, RDF.type, OWL.ObjectProperty))
        g.add((ctx.hasCompound, RDFS.label, Literal("hasCompound")))
    if (ctx.hasCanonicalSMILES, RDF.type, OWL.DatatypeProperty) not in g:
        g.add((ctx.hasCanonicalSMILES, RDF.type, OWL.DatatypeProperty))
        g.add((ctx.hasCanonicalSMILES, RDFS.label, Literal("hasCanonicalSMILES")))
    inv = canon = label_added = 0
    for chem, _, plant in list(g.triples((None, ctx.isDerivedFrom, None))):
        if (plant, ctx.hasCompound, chem) not in g:
            g.add((plant, ctx.hasCompound, chem))
            inv += 1
        for _, _, smi in g.triples((chem, ctx.hasSMILES, None)):
            c = canon_smiles(str(smi))
            if c and (chem, ctx.hasCanonicalSMILES, Literal(c)) not in g:
                g.add((chem, ctx.hasCanonicalSMILES, Literal(c)))
                canon += 1
        if not any(g.triples((plant, RDFS.label, None))):
            genus = next((str(o).strip() for _, _, o in g.triples((plant, ctx.hasGenus, None))), "")
            species = next(
                (str(o).strip() for _, _, o in g.triples((plant, ctx.hasSpecies, None))), ""
            )
            if genus or species:
                g.add((plant, RDFS.label, Literal(f"{genus} {species}".strip())))
                label_added += 1
    save_graph(g, ctx.ckpt("08_canonical.rdf"))
    return {"hasCompound": inv, "hasCanonicalSMILES": canon, "labels": label_added}


def stage_drduke(ctx):
    """Dr. Duke's merge → DOI CSV, then link papers to chemicals/organisms.

    NOTE (divergence from notebook): the notebook linked papers in Stage 3, before this
    CSV existed. We link here, after the CSV is built, so DOIs actually attach.
    """
    g = load_graph(ctx.ckpt("08_canonical.rdf"))
    N = ctx.NS
    files = [
        "AGGREGAC.csv",
        "ACTIVITIES.csv",
        "CHEMICALS.csv",
        "DOSAGE.csv",
        "ETHNOBOT.csv",
        "REFERENCES.csv",
    ]
    paths = {f: ctx.inp_opt(f) for f in files}
    merged_csv = ctx.work_dir / "activity_chem_taxon_dosage_refs.csv"
    doi_csv = ctx.work_dir / "activity_chem_taxon_dosage_refs_with_doi.csv"

    if all(paths[f] for f in files):

        def read_any(p):
            try:
                df = pd.read_csv(p, low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(p, encoding="latin-1", low_memory=False)
            df.columns = [c.strip() for c in df.columns]
            return df

        def norm_act(s):
            return s.astype(str).str.strip().str.lower()

        def norm_chem(s):
            return s.astype(str).str.strip()

        AGG = read_any(paths["AGGREGAC.csv"])
        ACT = read_any(paths["ACTIVITIES.csv"])
        CHEM = read_any(paths["CHEMICALS.csv"])
        DOS = read_any(paths["DOSAGE.csv"])
        ETH = read_any(paths["ETHNOBOT.csv"])
        REF = read_any(paths["REFERENCES.csv"])
        AGG["chem_key"] = norm_chem(AGG["CHEM"])
        AGG["act_key"] = norm_act(AGG["ACTIVITY"])
        ACT["act_key"] = norm_act(ACT["ACTIVITY"])
        CHEM["chem_key"] = norm_chem(CHEM["CHEM"])
        DOS["chem_key"] = norm_chem(DOS.get("CHEM", pd.Series(dtype=str)))
        ETH["act_key"] = norm_act(ETH.get("ACTIVITY", pd.Series(dtype=str)))
        ref_map = (
            REF.dropna(subset=["REFERENCE"])
            .drop_duplicates()
            .set_index("REFERENCE")["LONGREF"]
            .to_dict()
        )

        bb = AGG[["chem_key", "act_key", "CHEM", "ACTIVITY", "REFERENCE"]].rename(
            columns={"REFERENCE": "agg_ref"}
        )
        bb = bb.merge(
            ACT[["act_key", "ACTIVITY"]].drop_duplicates(),
            on="act_key",
            how="left",
            suffixes=("", "_A"),
        )
        bb["ACTIVITY"] = bb["ACTIVITY_A"].where(
            bb["ACTIVITY_A"].notna() & (bb["ACTIVITY_A"] != ""), bb["ACTIVITY"]
        )
        bb = bb.drop(columns=[c for c in bb.columns if c.endswith("_A")])
        bb = bb.merge(CHEM[["chem_key", "CHEMID"]].drop_duplicates(), on="chem_key", how="left")
        bb = bb.merge(
            DOS[["chem_key", "DOSAGE", "REFERENCE"]].drop_duplicates(), on="chem_key", how="left"
        ).rename(columns={"REFERENCE": "dos_ref"})
        merged = bb.merge(
            ETH[
                ["act_key", "GENUS", "SPECIES", "FAMILY", "COUNTRY", "TAXON", "REFERENCE"]
            ].drop_duplicates(),
            on="act_key",
            how="left",
        )

        def collect_longref(row):
            keys = []
            for k in ["agg_ref", "dos_ref", "REFERENCE"]:
                v = str(row.get(k, "")).strip()
                if v:
                    for t in v.replace("|", ";").replace(",", ";").split(";"):
                        t = t.strip()
                        if t:
                            keys.append(t)
            keys = sorted(set(keys))
            longs = [ref_map.get(k, "") for k in keys if ref_map.get(k, "")]
            return "; ".join(sorted(set(longs))) if longs else "; ".join(keys)

        merged["LONGREF"] = merged.apply(collect_longref, axis=1)
        out = (
            merged[
                [
                    "ACTIVITY",
                    "CHEM",
                    "CHEMID",
                    "DOSAGE",
                    "GENUS",
                    "SPECIES",
                    "FAMILY",
                    "COUNTRY",
                    "TAXON",
                    "LONGREF",
                ]
            ]
            .fillna("")
            .drop_duplicates()
        )
        out.to_csv(merged_csv, index=False)
        log.info("  Dr. Duke's merge: %s rows", f"{len(out):,}")

        DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
        df = pd.read_csv(merged_csv, dtype=str).fillna("")
        df["DOI"] = df["LONGREF"].apply(
            lambda s: (DOI_RE.search(str(s)).group(1) if DOI_RE.search(str(s)) else "")
        )
        df["DOI"] = df["DOI"].apply(normalize_doi)
        df.to_csv(doi_csv, index=False)
    else:
        missing = [f for f in files if not paths[f]]
        log.warning(
            "  Dr. Duke's CSVs missing %s — skipping merge, paper-linking limited.", missing
        )

    # --- link papers via whatever DOI CSV exists (notebook Cell 9 logic) ---
    RESEARCH_ROOT = find_class_by_label_or_local(g, ["ResearchConcept", "Research Concept"])
    PAPER_CLASS = find_class_by_label_or_local(g, ["ScientificPaper", "Paper"]) or N.ScientificPaper
    if (PAPER_CLASS, RDF.type, OWL.Class) not in g:
        g.add((PAPER_CLASS, RDF.type, OWL.Class))
        g.add((PAPER_CLASS, RDFS.label, Literal("ScientificPaper")))
    if RESEARCH_ROOT and (PAPER_CLASS, RDFS.subClassOf, RESEARCH_ROOT) not in g:
        g.add((PAPER_CLASS, RDFS.subClassOf, RESEARCH_ROOT))
    if (ctx.hasPaper, RDF.type, OWL.ObjectProperty) not in g:
        g.add((ctx.hasPaper, RDF.type, OWL.ObjectProperty))
        g.add((ctx.hasPaper, RDFS.label, Literal("hasPaper")))
    for o in list(g.objects(ctx.hasPaper, RDFS.range)):
        g.remove((ctx.hasPaper, RDFS.range, o))
    g.add((ctx.hasPaper, RDFS.range, PAPER_CLASS))

    src = doi_csv if doi_csv.exists() else None
    papers = chem_links = plant_links = 0
    if src:
        doi_df = pd.read_csv(src, dtype=str).fillna("")

        def pick(df, opts):
            return next((c for c in opts if c in df.columns), None)

        COL_DOI = pick(doi_df, ["DOI", "doi", "paper_doi"])
        COL_CHEM = pick(doi_df, ["CHEMID", "molecule_id", "chem_id", "ID"])
        COL_ORG = pick(doi_df, ["TAXON", "organism_id", "Organism_id", "GENUS_SPECIES"])
        if COL_DOI:
            doi_to_uri = {}
            for _, row in doi_df.iterrows():
                doi = normalize_doi(row[COL_DOI])
                if not doi:
                    continue
                paper_uri = doi_to_uri.get(doi) or make_uri(ctx, "Paper", doi)
                if doi not in doi_to_uri:
                    g.add((paper_uri, RDF.type, OWL.NamedIndividual))
                    g.add((paper_uri, RDF.type, PAPER_CLASS))
                    g.add((paper_uri, RDFS.label, Literal(doi)))
                    g.add((paper_uri, ctx.hasDOI, Literal(doi)))
                    doi_to_uri[doi] = paper_uri
                    papers += 1
                if COL_CHEM and str(row[COL_CHEM]).strip():
                    chem_uri = make_uri(ctx, "Chemical", row[COL_CHEM])
                    if any(g.triples((chem_uri, None, None))):
                        g.add((chem_uri, ctx.hasPaper, paper_uri))
                        chem_links += 1
                if COL_ORG and str(row[COL_ORG]).strip():
                    org_uri = make_uri(ctx, "Organism", row[COL_ORG])
                    if any(g.triples((org_uri, None, None))):
                        g.add((org_uri, ctx.hasPaper, paper_uri))
                        plant_links += 1
    save_graph(g, ctx.ckpt("09_drduke.rdf"))
    return {"papers": papers, "chem_paper_links": chem_links, "org_paper_links": plant_links}


def stage_cleanup(ctx):
    """Fix mis-typed individuals, retag PlantConcept→Plant, drop NA literals, dedupe, sync inverses."""
    g = load_graph(ctx.ckpt("09_drduke.rdf"))
    N = ctx.NS
    ChemicalConcept = (
        find_class_by_label_or_local(g, ["ChemicalConcept", "Chemical Concept"])
        or N.ChemicalConcept
    )
    Plant = find_class_by_label_or_local(g, ["Plant"]) or N.Plant
    plant_family = {Plant} | subclass_closure(g, Plant)

    mistyped = [
        (s, str(o))
        for s, _, o in g.triples((None, ctx.hasSMILES, None))
        if any((s, RDF.type, pc) in g for pc in plant_family)
    ]
    for subj, smi in mistyped:
        if (subj, RDF.type, ChemicalConcept) not in g:
            g.add((subj, RDF.type, ChemicalConcept))
        for lbl in classify_smiles(smi):
            cls = ctx.PHYTOCHEM_CLASSES.get(lbl)
            if cls and (cls, RDF.type, OWL.Class) in g:
                g.add((subj, RDF.type, cls))
        for pc in plant_family:
            if (subj, RDF.type, pc) in g:
                g.remove((subj, RDF.type, pc))

    PLANT_ROOT = find_class_by_label_or_local(g, ["PlantConcept", "Plant Concept"])
    PLANT_LEAF = find_class_by_label_or_local(g, ["Plant"])
    moved = 0
    if PLANT_ROOT and PLANT_LEAF:
        for s in list(g.subjects(RDF.type, PLANT_ROOT)):
            if (
                (s, RDF.type, OWL.Class) in g
                or (s, RDF.type, OWL.ObjectProperty) in g
                or (s, RDF.type, OWL.DatatypeProperty) in g
            ):
                continue
            g.add((s, RDF.type, PLANT_LEAF))
            g.remove((s, RDF.type, PLANT_ROOT))
            moved += 1

    NA_TOKENS = {
        "na",
        "n/a",
        "n.a",
        "n.a.",
        "nan",
        "none",
        "null",
        "not available",
        "not_applicable",
        "not applicable",
    }

    def is_na(lit):
        if not isinstance(lit, Literal):
            return False
        s = str(lit).strip().lower()
        return s in NA_TOKENS or re.sub(r"[^a-z0-9]+", "", s) in {
            "na",
            "nan",
            "none",
            "null",
            "notavailable",
            "notapplicable",
        }

    na_removed = 0
    for s, p, o in list(g.triples((None, None, None))):
        if is_na(o):
            g.remove((s, p, o))
            na_removed += 1

    def merge_nodes(target, dup):
        for _, p, o in list(g.triples((dup, None, None))):
            if (target, p, o) not in g:
                g.add((target, p, o))
            g.remove((dup, p, o))
        for s, p, _ in list(g.triples((None, None, dup))):
            if (s, p, target) not in g:
                g.add((s, p, target))
            g.remove((s, p, dup))

    def label_of(node):
        return next((str(o) for _, _, o in g.triples((node, RDFS.label, None))), None)

    def pick_canonical(uris):
        labeled = [u for u in uris if label_of(u)]
        return min(labeled or uris, key=lambda u: (len(str(u)), str(u)))

    buckets = defaultdict(list)
    chem_subs = set()
    for cls in subclass_closure(g, ChemicalConcept):
        chem_subs |= set(g.subjects(RDF.type, cls))
    for subj in chem_subs:
        ik = next((str(o) for _, _, o in g.triples((subj, ctx.hasInChIKey, None))), None)
        if ik:
            key = ("ikey", ik.strip().lower())
        else:
            smi = next((str(o) for _, _, o in g.triples((subj, ctx.hasSMILES, None))), None)
            c = canon_smiles(smi) if smi else None
            if c:
                key = ("smi", c)
            else:
                lbl = label_of(subj)
                key = ("label", lbl.strip().lower()) if lbl else None
        if key:
            buckets[key].append(subj)
    merges = 0
    for k, uris in buckets.items():
        if len(uris) < 2:
            continue
        target = pick_canonical(uris)
        for dup in set(uris) - {target}:
            merge_nodes(target, dup)
            merges += 1

    inv_pairs = {}
    for p, q in g.subject_objects(OWL.inverseOf):
        if isinstance(p, URIRef) and isinstance(q, URIRef) and p != q:
            inv_pairs[p] = q
            inv_pairs[q] = p
    inv_added = 0
    for s, p, o in list(g.triples((None, None, None))):
        if isinstance(o, Literal):
            continue
        q = inv_pairs.get(p)
        if q and (o, q, s) not in g:
            g.add((o, q, s))
            inv_added += 1
    for p in g.subjects(RDF.type, OWL.SymmetricProperty):
        for s, _, o in g.triples((None, p, None)):
            if not isinstance(o, Literal) and (o, p, s) not in g:
                g.add((o, p, s))
                inv_added += 1

    save_graph(g, ctx.ckpt("10_cleanup.rdf"))
    return {
        "mistyped_fixed": len(mistyped),
        "retagged": moved,
        "na_removed": na_removed,
        "chem_merges": merges,
        "inverse_added": inv_added,
    }


# ---- enrichment helpers ----
def _jcache(ctx, name):
    p = ctx.cache_dir / name
    return p, (json.load(open(p)) if p.exists() else {})


_TLS = threading.local()


def _tls_session():
    """Per-thread requests.Session (Session isn't safe to share across threads)."""
    s = getattr(_TLS, "s", None)
    if s is None:
        s = _TLS.s = requests.Session()
    return s


def _parallel_fill(items, fetch_one, cache, cpath, workers, desc, passes=3, save_every=1000):
    """Concurrent enrichment for APIs with no batch endpoint (UniChem, NPClassifier).

    SPEED FIX vs. notebook: these services have no bulk/batch call, so the only lever is
    concurrency (EBI/GNPS2 tolerate it; PubChem would not). `items` is the FULL list of
    (cache_key, arg); each pass fetches only keys still missing from `cache`. `fetch_one(arg)` does
    ONE request and returns a JSON-able dict on success (empty dict = valid "no data") or RAISES on
    error (the key is left uncached). Because ~10% of these calls time out, we run up to `passes`
    rounds — timed-out keys usually succeed on a retry; concurrency hides the stragglers. Workers
    only do network I/O; cache + graph are written single-threaded. Resumable: cache persists every
    `save_every` completions and after each pass, so an interrupted stage continues where it left off.
    """
    for attempt in range(passes):
        todo = [(k, a) for k, a in items if k not in cache]
        if not todo:
            break
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch_one, a): k for k, a in todo}
            label = desc if attempt == 0 else f"{desc} (retry {attempt})"
            for fut in tqdm(concurrent.futures.as_completed(futs), total=len(futs), desc=label):
                key = futs[fut]
                try:
                    cache[key] = fut.result()
                except Exception:
                    pass  # transient failure — retried in the next pass / next run
                done += 1
                if done % save_every == 0:
                    json.dump(cache, open(cpath, "w"))
        json.dump(cache, open(cpath, "w"))
    return cache


def _pubchem_fill(iks, cache, cpath, batch=150):
    """Batched PubChem PUG-REST lookup of Title/IUPACName/CID by InChIKey (resumable).

    SPEED FIX vs. notebook: instead of one GET per InChIKey (~4.5/s → ~11 h for ~180k), POST up
    to `batch` InChIKeys per request (~hundreds/s effective). InChIKey is echoed in the response so
    results map back to inputs; keys with no PubChem record cache as empty (not retried). Cache
    format {name,cid,iupac} is backward-compatible with the old {name,cid} entries. Persists after
    every batch so an interrupted stage resumes mid-list.
    """
    # NB: do NOT list CID as a property (PUG faults); CID is always returned in PropertyTable.
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/"
        "property/Title,IUPACName,InChIKey/JSON"
    )
    sess = requests.Session()
    todo = [ik for ik in iks if ik not in cache]
    for i in tqdm(range(0, len(todo), batch), desc="PubChem (batched)"):
        chunk = todo[i : i + batch]
        try:
            time.sleep(0.2)
            r = sess.post(url, data={"inchikey": ",".join(chunk)}, timeout=90)
            rows = {
                row.get("InChIKey"): row
                for row in r.json().get("PropertyTable", {}).get("Properties", [])
            }
        except Exception:
            continue  # transient failure — leave chunk uncached, retried on next run
        for ik in chunk:
            row = rows.get(ik)
            cache[ik] = {
                "name": (row or {}).get("Title", ""),
                "cid": (row or {}).get("CID"),
                "iupac": (row or {}).get("IUPACName", ""),
            }
        json.dump(cache, open(cpath, "w"))
    return cache


def stage_enrich_names(ctx):
    """PubChem: common names + CID xref + IUPAC (batched POST by InChIKey, resumable cache)."""
    g = load_graph(ctx.ckpt("10_cleanup.rdf"))
    inchikey_to_subj = {str(o): s for s, _, o in g.triples((None, ctx.hasInChIKey, None))}
    cpath, cache = _jcache(ctx, "pubchem_names.json")
    log.info(
        "  %s compounds; %s cached; %s to fetch",
        f"{len(inchikey_to_subj):,}",
        f"{len(cache):,}",
        f"{sum(1 for ik in inchikey_to_subj if ik not in cache):,}",
    )
    _pubchem_fill(list(inchikey_to_subj), cache, cpath)
    added = 0
    for ik, subj in inchikey_to_subj.items():
        rec = cache.get(ik, {})
        if rec.get("name"):
            g.add((subj, ctx.hasCommonName, Literal(rec["name"])))
            g.add((subj, RDFS.label, Literal(rec["name"])))
            added += 1
        if rec.get("cid"):
            g.add(
                (
                    subj,
                    SKOS.exactMatch,
                    URIRef(f"https://pubchem.ncbi.nlm.nih.gov/compound/{rec['cid']}"),
                )
            )
    save_graph(g, ctx.ckpt("11_names.rdf"))
    return {"names_added": added, "cached": len(cache)}


def stage_enrich_xrefs(ctx):
    """UniChem cross-refs to ChEMBL/ChEBI/DrugBank/KEGG/HMDB (parallel, resumable cache).

    UniChem has no batch endpoint, so this parallelizes the per-InChIKey calls (~33 h serial →
    ~2-3 h at the default --workers). EBI tolerates the concurrency.
    """
    g = load_graph(ctx.ckpt("11_names.rdf"))
    UNICHEM = "https://www.ebi.ac.uk/unichem/api/v1/compounds"
    XREF = {
        "chembl": lambda v: f"https://www.ebi.ac.uk/chembl/compound_report_card/{v}",
        "chebi": lambda v: f"http://purl.obolibrary.org/obo/CHEBI_{str(v).replace('CHEBI:', '')}",
        "drugbank": lambda v: f"https://go.drugbank.com/drugs/{v}",
        "kegg_ligand": lambda v: f"https://www.kegg.jp/entry/{v}",
        "hmdb": lambda v: f"https://hmdb.ca/metabolites/{v}",
    }

    def fetch(ik):
        data = _tls_session().post(UNICHEM, json={"type": "inchikey", "compound": ik}, timeout=15)
        data = data.json()
        comps = data.get("compounds") or [{"sources": data.get("sources", [])}]
        srcs = {}
        for c in comps:
            for s in c.get("sources", []):
                nm = (s.get("shortName") or s.get("name") or "").lower()
                cid = s.get("compoundId") or s.get("src_compound_id") or s.get("id")
                if nm and cid:
                    srcs[nm] = cid
        return srcs

    inchikey_to_subj = {str(o): s for s, _, o in g.triples((None, ctx.hasInChIKey, None))}
    upath, ucache = _jcache(ctx, "unichem.json")
    items = [(ik, ik) for ik in inchikey_to_subj]
    missing = sum(1 for ik in inchikey_to_subj if ik not in ucache)
    log.info(
        "  %s compounds; %s cached; %s to fetch (workers=%s)",
        f"{len(inchikey_to_subj):,}",
        f"{len(ucache):,}",
        f"{missing:,}",
        ctx.workers,
    )
    _parallel_fill(items, fetch, ucache, upath, ctx.workers, "UniChem xrefs")
    added = 0
    for ik, subj in inchikey_to_subj.items():
        for nm, val in (ucache.get(ik) or {}).items():
            if nm in XREF:
                g.add((subj, SKOS.exactMatch, URIRef(XREF[nm](val))))
                added += 1
    save_graph(g, ctx.ckpt("12_xrefs.rdf"))
    return {"xrefs_added": added}


def stage_enrich_npclass(ctx):
    """NPClassifier super/class/pathway for compounds typed Unknown (parallel, resumable).

    No batch endpoint; parallelized. The public GNPS2 server is small/academic and THROTTLES, so:
      * `fetch` honours 429/Retry-After with capped exponential backoff + jitter, and treats a
        throttle as "retry later" (raises → left uncached), never as "no data" (empty cache).
      * concurrency is capped low (min(--workers, 3)) against the public server.
    For the full Unknown set this is still slow — run a LOCAL NPClassifier and point at it with
    `--npclassifier-url "http://localhost:PORT/classify?smiles={}"` (or $NPCLASSIFIER_URL), then a
    high --workers is safe and there's no throttling. See the NP-Classifier repo for the server.
    """
    import urllib.parse

    g = load_graph(ctx.ckpt("12_xrefs.rdf"))
    NPC = ctx.npc_url
    local = "localhost" in NPC or "127.0.0.1" in NPC
    for p in (ctx.hasNPSuper, ctx.hasNPClass, ctx.hasNPPath):
        g.add((p, RDF.type, OWL.DatatypeProperty))

    def fetch(smi):
        url = NPC.format(urllib.parse.quote(smi))
        s = _tls_session()
        delay = 2.0
        for _ in range(6):
            r = s.get(url, timeout=60)
            if r.status_code == 200:
                j = r.json()
                return {
                    "super": "; ".join(j.get("superclass_results", []) or []),
                    "cls": "; ".join(j.get("class_results", []) or []),
                    "path": "; ".join(j.get("pathway_results", []) or []),
                }
            if r.status_code in (429, 500, 502, 503, 504):  # throttled/transient → back off
                try:
                    wait = float(r.headers.get("Retry-After", delay))
                except ValueError:
                    wait = delay
                time.sleep(min(wait, 30) + random.uniform(0, 1.0))
                delay = min(delay * 2, 30)
                continue
            r.raise_for_status()  # genuine 4xx → raise (left uncached, retried next pass/run)
        raise RuntimeError("npclassifier throttled (backoff exhausted)")  # retry later

    npath, npcache = _jcache(ctx, "npclassifier.json")
    todo = []
    for subj in g.subjects(RDF.type, ctx.NS.Unknown):
        if str(subj) in npcache:
            continue
        smi = next((str(o) for _, _, o in g.triples((subj, ctx.hasSMILES, None))), "")
        if smi:
            todo.append((str(subj), smi))
    workers = ctx.workers if local else min(ctx.workers, 3)
    if ctx.npclass_finalize:
        log.info(
            "  --npclass-finalize: skipping the API. %s classified; %s left unclassified "
            "(uncached, so a later/local run will retry them).",
            f"{len(npcache):,}",
            f"{len(todo):,}",
        )
    else:
        log.info(
            "  %s Unknown compounds to classify (workers=%s, %s)",
            f"{len(todo):,}",
            workers,
            "LOCAL server" if local else "public GNPS2 — throttled; consider a local server",
        )
        # more passes against the public server: heavy throttling can starve a single pass
        _parallel_fill(
            todo, fetch, npcache, npath, workers, "NPClassifier", passes=(3 if local else 6)
        )
    added = 0
    for subj in g.subjects(RDF.type, ctx.NS.Unknown):
        rec = npcache.get(str(subj))
        if not rec:
            continue
        if rec.get("super"):
            g.add((subj, ctx.hasNPSuper, Literal(rec["super"])))
            added += 1
        if rec.get("cls"):
            g.add((subj, ctx.hasNPClass, Literal(rec["cls"])))
        if rec.get("path"):
            g.add((subj, ctx.hasNPPath, Literal(rec["path"])))
    save_graph(g, ctx.ckpt("13_npclass.rdf"))
    return {"npclass_added": added}


def stage_iupac(ctx):
    """Write IUPAC names. Reuses the IUPAC already cached by enrich_names; batches any gaps.

    enrich_names now fetches IUPACName alongside Title (same batched PubChem call), so this stage
    is usually just cache reads. Any InChIKeys still without a cached IUPAC are batch-fetched here
    (also via the shared batched POST), then applied to the graph.
    """
    g = load_graph(ctx.ckpt("13_npclass.rdf"))
    all_iks = sorted(
        {str(o).strip() for _, _, o in g.triples((None, ctx.hasInChIKey, None)) if str(o).strip()}
    )
    ipath = ctx.cache_dir / "iupac_names.json"
    iupac = json.load(open(ipath)) if ipath.exists() else {}
    # harvest IUPAC already captured by enrich_names' pubchem cache
    npath = ctx.cache_dir / "pubchem_names.json"
    if npath.exists():
        for ik, v in json.load(open(npath)).items():
            if ik not in iupac and isinstance(v, dict) and v.get("iupac"):
                iupac[ik] = v["iupac"]
    # batch-fetch IUPAC for anything still missing
    missing = [ik for ik in all_iks if ik not in iupac]
    log.info("  %s compounds; %s have IUPAC; %s to fetch", len(all_iks), len(iupac), len(missing))
    if missing:
        gap_cache = {}
        _pubchem_fill(missing, gap_cache, ctx.cache_dir / "_iupac_gap.json")
        for ik in missing:
            iupac[ik] = gap_cache.get(ik, {}).get("iupac", "")
        json.dump(iupac, open(ipath, "w"))
    added = 0
    for s, _, o in g.triples((None, ctx.hasInChIKey, None)):
        nm = iupac.get(str(o).strip())
        if nm and (s, ctx.hasIUPACName, Literal(nm)) not in g:
            g.add((s, ctx.hasIUPACName, Literal(nm)))
            added += 1
    save_graph(g, ctx.ckpt("14_named.rdf"))
    return {"iupac_added": added}


def stage_coconut2_sdf(ctx):
    """COCONUT 2.0 SDF occurrences. PLANT-ONLY GATE: classify every NEW organism (offline).

    This is the fix for the contamination the original import created — when --plants-only
    (default), a new organism from the SDF is only minted if the local NCBI taxdump places it
    under Viridiplantae. Offline (no per-name web calls), so it adds seconds, not hours.
    Unmatched names are dropped unless --keep-unmatched.
    """
    g = load_graph(ctx.ckpt("14_named.rdf"))
    N = ctx.NS
    coco_sdf = ctx.inp("coconut_sdf_2d-06-2026.sdf")
    tax = ctx.taxonomy() if ctx.plants_only else None

    INCHIKEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")  # noqa: F841 (kept for parity)

    def _na(v):
        return (v or "").strip().lower() in ("", "nan", "none", "null")

    def _norm_org(n):
        p = "".join(c if (c.isalpha() or c == " ") else " " for c in (n or "")).split()
        return f"{p[0].lower()} {p[1].lower()}" if len(p) >= 2 else (p[0].lower() if p else "")

    def _safe_local(s):
        s = re.sub(r"[^A-Za-z0-9_.\-]", "_", s.strip())
        return re.sub(r"_+", "_", s).strip("_") or "x"

    inchikey_to_subj = {
        str(o).strip(): s for s, _, o in g.triples((None, ctx.hasInChIKey, None)) if str(o).strip()
    }
    name_to_plant = {}
    for s in g.subjects(RDF.type, N.Plant):
        for _, _, lbl in g.triples((s, RDFS.label, None)):
            name_to_plant.setdefault(_norm_org(str(lbl)), s)
    log.info(
        "  index: %s compounds, %s plants", f"{len(inchikey_to_subj):,}", f"{len(name_to_plant):,}"
    )

    skipped_nonplant = {"count": 0}

    def validated_plant(name):
        """True if the name is an accepted plant (offline taxdump). Respects --plants-only."""
        if not ctx.plants_only:
            return True
        verdict, _ = tax.classify_name(name)
        return verdict == "plant" or (verdict == "unmatched" and ctx.keep_unmatched)

    def get_or_make_plant(name):
        key = _norm_org(name)
        if key in name_to_plant:
            return name_to_plant[key]
        if not validated_plant(name):
            skipped_nonplant["count"] += 1
            return None
        uri = N["Plant_" + _safe_local(name)]
        g.add((uri, RDF.type, OWL.NamedIndividual))
        g.add((uri, RDF.type, N.Plant))
        g.add((uri, RDFS.label, Literal(name.strip())))
        name_to_plant[key] = uri
        return uri

    def get_or_make_chemical(smiles, inchikey, formula=None, name=None, iupac=None):
        if inchikey in inchikey_to_subj:
            return inchikey_to_subj[inchikey]
        uri = N["Chemical_ik_" + inchikey.replace("-", "_")]
        g.add((uri, RDF.type, OWL.NamedIndividual))
        g.add((uri, RDF.type, N.ChemicalConcept))
        if smiles:
            g.add((uri, ctx.hasSMILES, Literal(smiles)))
        g.add((uri, ctx.hasInChIKey, Literal(inchikey)))
        if formula:
            g.add((uri, ctx.hasMolecularFormula, Literal(formula)))
        if iupac:
            g.add((uri, ctx.hasIUPACName, Literal(iupac)))
        g.add((uri, RDFS.label, Literal(name or iupac or smiles or inchikey)))
        if name:
            g.add((uri, ctx.hasCommonName, Literal(name)))
        inchikey_to_subj[inchikey] = uri
        return uri

    WANT = {
        "canonical_smiles",
        "standard_inchi_key",
        "molecular_formula",
        "name",
        "iupac_name",
        "organisms",
        "np_classifier_superclass",
        "np_classifier_class",
        "np_classifier_pathway",
    }

    def iter_sdf(path, want):
        cur, tag = {}, None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("$$$$"):
                    if cur:
                        yield cur
                    cur, tag = {}, None
                elif line.startswith(">") and "<" in line:
                    m = re.search(r"<([^>]+)>", line)
                    tag = m.group(1) if (m and m.group(1) in want) else None
                elif tag is not None:
                    if line.strip() == "":
                        tag = None
                    else:
                        cur[tag] = (cur[tag] + " " + line.strip()) if tag in cur else line.strip()
        if cur:
            yield cur

    recs = newc = links = 0
    for rec in tqdm(iter_sdf(coco_sdf, WANT), total=738823, desc="COCONUT-SDF"):
        recs += 1
        ik = "" if _na(rec.get("standard_inchi_key")) else rec["standard_inchi_key"].strip()
        if not ik:
            continue
        orgs = rec.get("organisms", "")
        organisms = [] if _na(orgs) else [o.strip() for o in re.split(r"[|;]", orgs) if not _na(o)]
        is_existing = ik in inchikey_to_subj
        if not is_existing and not organisms:
            continue
        chem = get_or_make_chemical(
            "" if _na(rec.get("canonical_smiles")) else rec["canonical_smiles"].strip(),
            ik,
            None if _na(rec.get("molecular_formula")) else rec["molecular_formula"].strip(),
            None if _na(rec.get("name")) else rec["name"].strip(),
            None if _na(rec.get("iupac_name")) else rec["iupac_name"].strip(),
        )
        if not is_existing:
            newc += 1
        if not _na(rec.get("np_classifier_superclass")):
            g.add((chem, ctx.hasNPSuper, Literal(rec["np_classifier_superclass"])))
        if not _na(rec.get("np_classifier_class")):
            g.add((chem, ctx.hasNPClass, Literal(rec["np_classifier_class"])))
        if not _na(rec.get("np_classifier_pathway")):
            g.add((chem, ctx.hasNPPath, Literal(rec["np_classifier_pathway"])))
        for org in organisms:
            plant = get_or_make_plant(org)
            if plant is None:
                continue
            if (plant, ctx.hasCompound, chem) not in g:
                g.add((plant, ctx.hasCompound, chem))
                g.add((chem, ctx.isDerivedFrom, plant))
                links += 1

    # sanitize unsafe IRIs
    BAD = re.compile(r"[^A-Za-z0-9_.\-]")

    def _fix(u):
        if isinstance(u, URIRef) and str(u).startswith(NS_STR):
            loc = str(u)[len(NS_STR) :]
            if BAD.search(loc):
                return URIRef(NS_STR + (re.sub(r"_+", "_", BAD.sub("_", loc)).strip("_") or "x"))
        return u

    changed = [(s, p, o) for s, p, o in g if (_fix(s), _fix(p), _fix(o)) != (s, p, o)]
    for s, p, o in changed:
        g.remove((s, p, o))
        g.add((_fix(s), _fix(p), _fix(o)))
    save_graph(g, ctx.ckpt("15_named_coconut.rdf"))
    return {
        "records": recs,
        "new_compounds": newc,
        "occurrence_links": links,
        "skipped_nonplant_orgs": skipped_nonplant["count"],
        "plants_only": ctx.plants_only,
    }


def stage_references(ctx):
    """Literature evidence from COCONUT citations: molecule → DOI → paper, with metadata.

    Dr. Duke's references carry no DOIs (so the drduke stage links 0 papers). COCONUT's `entries`
    table maps molecule_id → doi, and `citations` adds title/authors/citation_text. We mint
    `ScientificPaper` nodes from the real DOIs and attach them to existing `Chemical_<molecule_id>`
    nodes — clean because that's the same id space the COCONUT chemicals were minted from. Only
    compounds present in the (plant-only) graph get linked, so non-plant DOIs are naturally excluded.
    """
    g = load_graph(ctx.ckpt("15_named_coconut.rdf"))
    N = ctx.NS
    RESEARCH_ROOT = find_class_by_label_or_local(g, ["ResearchConcept", "Research Concept"])
    PAPER_CLASS = find_class_by_label_or_local(g, ["ScientificPaper", "Paper"]) or N.ScientificPaper
    if (PAPER_CLASS, RDF.type, OWL.Class) not in g:
        g.add((PAPER_CLASS, RDF.type, OWL.Class))
        g.add((PAPER_CLASS, RDFS.label, Literal("ScientificPaper")))
    if RESEARCH_ROOT and (PAPER_CLASS, RDFS.subClassOf, RESEARCH_ROOT) not in g:
        g.add((PAPER_CLASS, RDFS.subClassOf, RESEARCH_ROOT))
    if (ctx.hasPaper, RDF.type, OWL.ObjectProperty) not in g:
        g.add((ctx.hasPaper, RDF.type, OWL.ObjectProperty))
        g.add((ctx.hasPaper, RDFS.label, Literal("hasPaper")))

    with ctx.sql_conn() as conn:
        DF = pd.read_sql(
            """
            SELECT e.molecule_id, e.doi, c.title, c.citation_text
            FROM coconut.entries e
            LEFT JOIN coconut.citations c ON c.doi = e.doi
            WHERE e.doi IS NOT NULL AND e.doi <> ''
            """,
            conn,
        ).fillna("")
    log.info("  %s molecule–DOI rows from COCONUT", f"{len(DF):,}")

    # set of chemical nodes actually present in the (plant-only) graph, for O(1) membership
    present = set(g.subjects())
    papers = {}  # doi -> uri
    paper_count = link_count = 0
    for _, row in tqdm(DF.iterrows(), total=len(DF), desc="references"):
        mol_id = str(row["molecule_id"]).strip()
        doi = normalize_doi(row["doi"])
        if not mol_id or not doi:
            continue
        chem_uri = make_uri(ctx, "Chemical", mol_id)
        if chem_uri not in present:
            continue
        paper_uri = papers.get(doi)
        if paper_uri is None:
            paper_uri = make_uri(ctx, "Paper", doi)
            papers[doi] = paper_uri
            g.add((paper_uri, RDF.type, OWL.NamedIndividual))
            g.add((paper_uri, RDF.type, PAPER_CLASS))
            g.add((paper_uri, ctx.hasDOI, Literal(doi)))
            title = str(row["title"]).strip()
            g.add((paper_uri, RDFS.label, Literal(title or doi)))
            txt = str(row["citation_text"]).strip()
            if txt:
                g.add((paper_uri, ctx.hasEvidenceText, Literal(txt, datatype=XSD.string)))
            paper_count += 1
        if (chem_uri, ctx.hasPaper, paper_uri) not in g:
            g.add((chem_uri, ctx.hasPaper, paper_uri))
            link_count += 1
    save_graph(g, ctx.ckpt("15b_references.rdf"))
    return {"papers": paper_count, "chem_paper_links": link_count}


def stage_final_cleanup(ctx):
    """Sanitize IRIs, merge duplicate compounds (InChIKey) and plants (label)."""
    g = load_graph(ctx.ckpt("15b_references.rdf"))
    N = ctx.NS
    BAD = re.compile(r"[^A-Za-z0-9_.\-]")

    def safe(u):
        if isinstance(u, URIRef) and str(u).startswith(NS_STR):
            loc = str(u)[len(NS_STR) :]
            if BAD.search(loc):
                return URIRef(NS_STR + (re.sub(r"_+", "_", BAD.sub("_", loc)).strip("_") or "x"))
        return u

    changed = [(s, p, o) for s, p, o in g if (safe(s), safe(p), safe(o)) != (s, p, o)]
    for s, p, o in changed:
        g.remove((s, p, o))
        g.add((safe(s), safe(p), safe(o)))

    by_ik = defaultdict(set)
    for s, _, o in g.triples((None, ctx.hasInChIKey, None)):
        by_ik[str(o)].add(s)

    def keep_compound(subs):
        pref = [s for s in subs if "Chemical_ik_" not in str(s)]
        return min(pref or list(subs), key=lambda u: (len(str(u)), str(u)))

    cmerged = 0
    for ik, subs in by_ik.items():
        if len(subs) < 2:
            continue
        keep = keep_compound(subs)
        for d in subs - {keep}:
            for p, o in list(g.predicate_objects(d)):
                g.add((keep, p, o))
                g.remove((d, p, o))
            for s, p in list(g.subject_predicates(d)):
                g.add((s, p, keep))
                g.remove((s, p, d))
            cmerged += 1

    by_lbl = defaultdict(set)
    for s in g.subjects(RDF.type, N.Plant):
        for _, _, lbl in g.triples((s, RDFS.label, None)):
            by_lbl[str(lbl).strip().lower()].add(s)

    def keep_plant(subs):
        pref = [s for s in subs if "/Organism_" in str(s) or "#Organism_" in str(s)]
        return min(pref or list(subs), key=lambda u: (len(str(u)), str(u)))

    pmerged = 0
    for lbl, subs in by_lbl.items():
        if len(subs) < 2:
            continue
        keep = keep_plant(subs)
        for d in subs - {keep}:
            for p, o in list(g.predicate_objects(d)):
                g.add((keep, p, o))
                g.remove((d, p, o))
            for s, p in list(g.subject_predicates(d)):
                g.add((s, p, keep))
                g.remove((s, p, d))
            pmerged += 1
    save_graph(g, ctx.ckpt("16_clean.rdf"))
    return {"sanitized": len(changed), "compound_merges": cmerged, "plant_merges": pmerged}


def stage_chebi(ctx):
    """OPTIONAL ChEBI alignment (notebook Stage 13). Skipped if ontology_ext is absent."""
    try:
        sys.path.insert(0, str(ctx.data_dir))
        sys.path.insert(0, str(REPO))
        import ontology_ext  # noqa: F401
    except Exception:
        log.warning("  ontology_ext package not available — skipping ChEBI alignment (optional).")
        # pass the graph through unchanged so downstream input exists
        g = load_graph(ctx.ckpt("16_clean.rdf"))
        save_graph(g, ctx.ckpt("17_chebi.rdf"))
        return {"skipped": True}
    # If present, the real alignment would run here; left as a hook to avoid guessing its API.
    log.warning("  ontology_ext present but alignment wiring is a TODO — passing graph through.")
    g = load_graph(ctx.ckpt("16_clean.rdf"))
    save_graph(g, ctx.ckpt("17_chebi.rdf"))
    return {"skipped": False, "note": "passthrough"}


def stage_stats(ctx):
    """Verification stats — writes results/ontology_stats.json. THE TARGETS COUNT.

    Reads the latest available checkpoint, so you can get the targets number early (e.g. after
    `--to chembl`) without running enrichment — targets are fully set by the chembl stage (07).
    """
    candidates = [
        "17_chebi.rdf",
        "16_clean.rdf",
        "15b_references.rdf",
        "15_named_coconut.rdf",
        "14_named.rdf",
        "13_npclass.rdf",
        "12_xrefs.rdf",
        "11_names.rdf",
        "10_cleanup.rdf",
        "08_canonical.rdf",
        "07_chembl.rdf",
    ]
    src = next((ctx.ckpt(c) for c in candidates if ctx.ckpt(c).exists()), None)
    if src is None:
        raise FileNotFoundError(
            "No checkpoint to compute stats from — run at least through the 'chembl' stage first."
        )
    if src.name != "16_clean.rdf":
        log.warning("  stats on %s (not the final 16_clean.rdf) — counts are preliminary", src.name)
    g = load_graph(src)
    N = ctx.NS
    classes = set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))
    obj_props = set(g.subjects(RDF.type, OWL.ObjectProperty))
    data_props = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    individuals = set(g.subjects(RDF.type, OWL.NamedIndividual))
    for s, _, c in g.triples((None, RDF.type, None)):
        if isinstance(s, URIRef) and c in classes:
            individuals.add(s)
    individuals -= classes | obj_props | data_props

    instances_by_class = defaultdict(int)
    for s, c in g.subject_objects(RDF.type):
        if c not in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class):
            instances_by_class[c] += 1

    def label(cls):
        return next(
            (str(o) for _, _, o in g.triples((cls, RDFS.label, None))), str(cls).rsplit("#", 1)[-1]
        )

    by_class = {label(c): n for c, n in sorted(instances_by_class.items(), key=lambda x: -x[1])}

    # Targets are modeled as Pathway individuals reached via targetsPathway.
    PathwayClass = find_class_by_label_or_local(g, ["Pathway"]) or N.Pathway
    pathway_individuals = set(g.subjects(RDF.type, PathwayClass))
    distinct_targets = set(g.objects(None, ctx.targetsPathway))
    plant_count = len(set(g.subjects(RDF.type, N.Plant)))
    ChemRoot = find_class_by_label_or_local(g, ["ChemicalConcept", "Chemical Concept"])
    chem_subs = set()
    if ChemRoot:
        for cls in subclass_closure(g, ChemRoot):
            chem_subs |= set(g.subjects(RDF.type, cls))

    stats = {
        "source_checkpoint": src.name,
        "plants_only": ctx.plants_only,
        "triples": len(g),
        "classes": len(classes),
        "object_properties": len(obj_props),
        "datatype_properties": len(data_props),
        "individuals": len(individuals),
        "plants": plant_count,
        "compounds": len(chem_subs),
        "protein_targets_pathway_individuals": len(pathway_individuals),
        "protein_targets_distinct_via_targetsPathway": len(distinct_targets),
        "therapeutic_effects": len(
            set(
                g.subjects(
                    RDF.type,
                    find_class_by_label_or_local(g, ["TherapeuticEffect"]) or N.TherapeuticEffect,
                )
            )
        ),
        "clinical_trials": len(
            set(
                g.subjects(
                    RDF.type, find_class_by_label_or_local(g, ["ClinicalTrial"]) or N.ClinicalTrial
                )
            )
        ),
        "papers": len(
            set(
                g.subjects(
                    RDF.type,
                    find_class_by_label_or_local(g, ["ScientificPaper", "Paper"])
                    or N.ScientificPaper,
                )
            )
        ),
        "top_instances_by_class": dict(list(by_class.items())[:20]),
    }
    STATS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_OUT, "w") as f:
        json.dump(stats, f, indent=2)
    log.info("  ===== ONTOLOGY STATS =====")
    log.info("  triples=%s individuals=%s", f"{stats['triples']:,}", f"{stats['individuals']:,}")
    log.info("  plants=%s compounds=%s", f"{stats['plants']:,}", f"{stats['compounds']:,}")
    log.info(
        "  PROTEIN TARGETS (Pathway individuals)=%s | distinct via targetsPathway=%s",
        stats["protein_targets_pathway_individuals"],
        stats["protein_targets_distinct_via_targetsPathway"],
    )
    log.info(
        "  therapeutic_effects=%s clinical_trials=%s papers=%s",
        stats["therapeutic_effects"],
        stats["clinical_trials"],
        stats["papers"],
    )
    log.info("  wrote %s", STATS_OUT)
    return stats


# ---------------------------------------------------------------------------
# Stage registry (dependency-correct order) + runner
# ---------------------------------------------------------------------------
STAGES = [
    ("base_plants", stage_base_plants, "01_augmented.rdf", "DB+taxdump"),
    ("coconut_chemicals", stage_coconut_chemicals, "02_chemicals.rdf", "DB"),
    ("cmaup", stage_cmaup, "03_cmaup.rdf", "CSV"),
    ("clinical_trials", stage_clinical_trials, "04_trials.rdf", "CSV"),
    ("maccs", stage_maccs, "05_maccs.rdf", "rdkit"),
    ("drugcentral", stage_drugcentral, "06_drugcentral.rdf", "DB(public)"),
    ("chembl", stage_chembl, "07_chembl.rdf", "CSV"),
    ("canonical_inverse", stage_canonical_inverse, "08_canonical.rdf", "local"),
    ("drduke", stage_drduke, "09_drduke.rdf", "CSV"),
    ("cleanup", stage_cleanup, "10_cleanup.rdf", "local"),
    ("enrich_names", stage_enrich_names, "11_names.rdf", "API:PubChem"),
    ("enrich_xrefs", stage_enrich_xrefs, "12_xrefs.rdf", "API:UniChem"),
    ("enrich_npclass", stage_enrich_npclass, "13_npclass.rdf", "API:NPClassifier"),
    ("iupac", stage_iupac, "14_named.rdf", "API:PubChem"),
    ("coconut2_sdf", stage_coconut2_sdf, "15_named_coconut.rdf", "SDF+taxdump"),
    ("references", stage_references, "15b_references.rdf", "DB"),
    ("final_cleanup", stage_final_cleanup, "16_clean.rdf", "local"),
    ("chebi", stage_chebi, "17_chebi.rdf", "optional"),
    ("stats", stage_stats, None, "report"),
]
STAGE_INDEX = {name: i for i, (name, *_rest) in enumerate(STAGES)}


def load_state(work_dir):
    p = work_dir / "state.json"
    return p, (json.load(open(p)) if p.exists() else {"stages": {}})


def select_stages(args):
    names = [s[0] for s in STAGES]
    if args.only:
        bad = [n for n in args.only if n not in STAGE_INDEX]
        if bad:
            sys.exit(f"Unknown stage(s): {bad}. Valid: {names}")
        return [n for n in names if n in set(args.only)]
    start = STAGE_INDEX[args.from_stage] if args.from_stage else 0
    end = STAGE_INDEX[args.to_stage] if args.to_stage else len(STAGES) - 1
    if start > end:
        sys.exit("--from is after --to")
    return names[start : end + 1]


def cmd_list(args, state):
    print(f"\nStages (work-dir: {args.work_dir})\n" + "-" * 64)
    for name, _fn, out, kind in STAGES:
        st = state["stages"].get(name, {})
        done = st.get("status") == "done"
        ckpt_ok = (Path(args.work_dir) / out).exists() if out else (name == "stats")
        mark = "✓" if done and ckpt_ok else ("·" if done else " ")
        extra = ""
        if "counts" in st:
            keys = list(st["counts"].items())[:3]
            extra = "  " + " ".join(f"{k}={v}" for k, v in keys)
        print(f"  [{mark}] {name:<18} ({kind:<16}) → {out or '(stats json)'}{extra}")
    print("\n  ✓ done+checkpoint present   · done but checkpoint missing   (blank) pending\n")


def preflight(ctx):
    """Check env + inputs without running anything."""
    ok = True
    log.info("Preflight checks:")
    # env (ENTREZ_EMAIL is optional now — validation is offline via taxdump)
    for var, val, required in [
        ("PMACS_USER", ctx.pmacs_user, True),
        ("ROMANO_DB_PASSWORD", "***" if ctx.pmacs_pass else "", True),
        ("ENTREZ_EMAIL", ctx.entrez_email, False),
    ]:
        status = "OK" if val else ("MISSING" if required else "unset (optional)")
        if not val and required:
            ok = False
        log.info("  env %-20s %s", var, status)
    # local NCBI taxdump (offline organism validation)
    td_ok = (ctx.taxdump_dir / "names.dmp").exists() and (ctx.taxdump_dir / "nodes.dmp").exists()
    log.info(
        "  taxdump %-18s %s",
        str(ctx.taxdump_dir),
        "OK" if td_ok else "missing (auto-downloads on first run, ~75 MB)",
    )
    # DB reachability
    try:
        with ctx.sql_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM coconut.organisms")
            n = cur.fetchone()[0]
        log.info("  DB opendata.coconut.organisms reachable (%s rows)", f"{n:,}")
    except Exception as e:
        ok = False
        log.warning("  DB unreachable: %s", e)
    # inputs
    inputs = [
        ("CMAUPv2.0_download_Plants.txt",),
        ("CMAUPv2.0_download_Targets.txt",),
        ("CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt",),
        ("CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt",),
        ("CMAUPv2.0_download_Ingredients_All (1).txt", "CMAUPv2.0_download_Ingredients_All.txt"),
        (
            "CMAUPv2.0_download_Plant_Human_Disease_Associations.txt",
            "CMAUPv2.0_download_Plant_Human_Disease_Associations.tsv",
        ),
        ("ChEMBL_drug_mechanisms.csv",),
        ("chebi_lite.owl",),
        ("coconut_sdf_2d-06-2026.sdf",),
        ("ACTIVITIES.csv",),
        ("AGGREGAC.csv",),
        ("CHEMICALS.csv",),
        ("DOSAGE.csv",),
        ("ETHNOBOT.csv",),
        ("REFERENCES.csv",),
    ]
    for names in inputs:
        p = ctx.inp_opt(*names)
        log.info("  input %-62s %s", names[0], "OK" if p else "missing")
    log.info("Preflight %s", "PASSED" if ok else "has WARNINGS (see above)")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Resumable POPPy ontology rebuild.")
    ap.add_argument(
        "--data-dir", default=str(DEFAULT_DATA_DIR), help="Input files dir (default data/raw)."
    )
    ap.add_argument(
        "--work-dir",
        default=str(DEFAULT_WORK_DIR),
        help="Checkpoints/caches/logs (default build/).",
    )
    ap.add_argument(
        "--taxdump-dir",
        default=str(DEFAULT_DATA_DIR / "taxdump"),
        help="Local NCBI taxdump dir (names.dmp/nodes.dmp); auto-downloads if missing.",
    )
    ap.add_argument("--only", nargs="+", help="Run only these stage(s).")
    ap.add_argument("--from", dest="from_stage", help="Start from this stage.")
    ap.add_argument("--to", dest="to_stage", help="Stop after this stage.")
    ap.add_argument("--force", action="store_true", help="Re-run selected stages even if done.")
    ap.add_argument(
        "--no-plants-only",
        dest="plants_only",
        action="store_false",
        help="Reproduce the old contaminated import (no Viridiplantae gate at COCONUT 2.0).",
    )
    ap.add_argument("--plants-only", dest="plants_only", action="store_true", default=True)
    ap.add_argument(
        "--keep-unmatched",
        action="store_true",
        help="Keep organisms whose name doesn't match the taxdump (default: drop them; "
        "the validated-plant count is then a conservative floor).",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Concurrent workers for the parallel enrichment stages (UniChem/NPClassifier). "
        "Default 12. Lower it if a service starts erroring/throttling.",
    )
    ap.add_argument(
        "--npclass-finalize",
        "--npclass_finalize",
        action="store_true",
        help="Finalize the NPClassifier stage from the current cache WITHOUT calling the API — "
        "the escape hatch for a few stuck/pathological SMILES. Unclassified compounds stay "
        "uncached, so a later run (e.g. against a local server) will retry just those.",
    )
    ap.add_argument(
        "--npclassifier-url",
        default=None,
        help="NPClassifier endpoint template, one {} for the URL-encoded SMILES (or set "
        "$NPCLASSIFIER_URL). Default is the public GNPS2 server (throttles). Point at a LOCAL "
        'server for the full run, e.g. "http://localhost:6541/classify?smiles={}", then raise '
        "--workers — localhost is detected and the concurrency cap is lifted.",
    )
    ap.add_argument("--list", action="store_true", help="List stages + status and exit.")
    ap.add_argument("--check", action="store_true", help="Preflight env/inputs and exit.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    Path(args.work_dir).mkdir(parents=True, exist_ok=True)
    logfile = setup_logging(Path(args.work_dir), args.verbose)
    state_path, state = load_state(Path(args.work_dir))

    if args.list:
        cmd_list(args, state)
        return

    _imports()
    ctx = Ctx(args)

    if args.check:
        preflight(ctx)
        return

    todo = select_stages(args)
    log.info("Run plan: %s", " → ".join(todo))
    log.info("Logfile: %s | plants_only=%s", logfile, ctx.plants_only)

    for name in todo:
        idx = STAGE_INDEX[name]
        _n, fn, out, kind = STAGES[idx]
        st = state["stages"].get(name, {})
        ckpt_present = (Path(args.work_dir) / out).exists() if out else False
        if st.get("status") == "done" and ckpt_present and not args.force and not args.only:
            log.info("SKIP  %s (done; checkpoint present)", name)
            continue
        log.info("START %s  [%s]", name, kind)
        t0 = time.time()
        try:
            counts = fn(ctx)
        except Exception as e:
            log.exception("FAIL  %s: %s", name, e)
            state["stages"][name] = {"status": "failed", "error": str(e), "ts": time.time()}
            json.dump(state, open(state_path, "w"), indent=2)
            sys.exit(f"\nStage '{name}' failed — fix and re-run (it resumes here). See {logfile}")
        dt = time.time() - t0
        state["stages"][name] = {
            "status": "done",
            "counts": counts,
            "seconds": round(dt, 1),
            "ts": time.time(),
        }
        json.dump(state, open(state_path, "w"), indent=2)
        log.info("DONE  %s in %.1fs — %s", name, dt, counts)

    log.info("All requested stages complete.")


if __name__ == "__main__":
    main()
