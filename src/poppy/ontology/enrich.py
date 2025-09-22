from typing import Iterable, Dict, Any, Optional
from rdflib import Graph, URIRef, Literal, RDF, RDFS, Namespace

from .utils import sanitize_for_uri

OWL_CLASS = URIRef("http://www.w3.org/2002/07/owl#Class")


def ensure_class(g: Graph, ns: Namespace, class_name: str, label: Optional[str] = None):
    c = URIRef(ns + class_name)
    if (c, RDF.type, None) not in g:
        g.add((c, RDF.type, OWL_CLASS))
    if label:
        g.add((c, RDFS.label, Literal(label)))
    return c


def add_plants(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    id_key: str = "plant_id",
    name_key: str = "scientific_name",
):
    plant_cls = ensure_class(g, ns, "Plant", "Plant")
    for r in rows:
        pid = sanitize_for_uri(r.get(id_key) or r.get(name_key))
        if not pid:
            continue
        subj = URIRef(ns + f"Plant_{pid}")
        g.add((subj, RDF.type, plant_cls))
        if r.get(name_key):
            g.add((subj, RDFS.label, Literal(r[name_key])))


def add_compounds(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    id_key: str = "compound_id",
    name_key: str = "name",
    smiles_key: str = "smiles",
):
    cmpd_cls = ensure_class(g, ns, "Compound", "Compound")
    has_smiles = URIRef(ns + "hasSMILES")
    for r in rows:
        cid = sanitize_for_uri(r.get(id_key) or r.get(name_key))
        if not cid:
            continue
        subj = URIRef(ns + f"Compound_{cid}")
        g.add((subj, RDF.type, cmpd_cls))
        if r.get(name_key):
            g.add((subj, RDFS.label, Literal(r[name_key])))
        if r.get(smiles_key):
            g.add((subj, has_smiles, Literal(r[smiles_key])))


def add_genes(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    id_key: str = "gene_id",
    sym_key: str = "symbol",
):
    gene_cls = ensure_class(g, ns, "Gene", "Gene")
    for r in rows:
        gid = sanitize_for_uri(r.get(id_key) or r.get(sym_key))
        if not gid:
            continue
        subj = URIRef(ns + f"Gene_{gid}")
        g.add((subj, RDF.type, gene_cls))
        if r.get(sym_key):
            g.add((subj, RDFS.label, Literal(r[sym_key])))


def add_pathways(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    id_key: str = "pathway_id",
    name_key: str = "name",
):
    pwy_cls = ensure_class(g, ns, "Pathway", "Pathway")
    for r in rows:
        pid = sanitize_for_uri(r.get(id_key) or r.get(name_key))
        if not pid:
            continue
        subj = URIRef(ns + f"Pathway_{pid}")
        g.add((subj, RDF.type, pwy_cls))
        if r.get(name_key):
            g.add((subj, RDFS.label, Literal(r[name_key])))


def link_compound_to_plant(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    compound_id_key: str = "compound_id",
    plant_id_key: str = "plant_id",
):
    pred = URIRef(ns + "isDerivedFrom")
    for r in rows:
        cid = sanitize_for_uri(r.get(compound_id_key))
        pid = sanitize_for_uri(r.get(plant_id_key))
        if not cid or not pid:
            continue
        cmpd = URIRef(ns + f"Compound_{cid}")
        plant = URIRef(ns + f"Plant_{pid}")
        g.add((cmpd, pred, plant))


def link_gene_to_pathway(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    gene_id_key: str = "gene_id",
    pathway_id_key: str = "pathway_id",
):
    pred = URIRef(ns + "geneInPathway")
    for r in rows:
        gid = sanitize_for_uri(r.get(gene_id_key))
        pid = sanitize_for_uri(r.get(pathway_id_key))
        if not gid or not pid:
            continue
        gene = URIRef(ns + f"Gene_{gid}")
        pwy = URIRef(ns + f"Pathway_{pid}")
        g.add((gene, pred, pwy))


def link_compound_to_pathway(
    g: Graph,
    ns: Namespace,
    rows: Iterable[Dict[str, Any]],
    compound_id_key: str = "compound_id",
    pathway_id_key: str = "pathway_id",
):
    pred = URIRef(ns + "targetsPathway")
    for r in rows:
        cid = sanitize_for_uri(r.get(compound_id_key))
        pid = sanitize_for_uri(r.get(pathway_id_key))
        if not cid or not pid:
            continue
        cmpd = URIRef(ns + f"Compound_{cid}")
        pwy = URIRef(ns + f"Pathway_{pid}")
        g.add((cmpd, pred, pwy))
