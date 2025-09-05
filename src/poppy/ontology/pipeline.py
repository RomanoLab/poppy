import yaml
from typing import Dict, Any
from rdflib import Graph

from .schema import load_schema
from .namespaces import get_namespace
from .enrich import (
    add_plants, add_compounds, add_genes, add_pathways,
    link_compound_to_plant, link_gene_to_pathway, link_compound_to_pathway
)
from ..io.db import connect_postgres, fetch_rows
from ..io.csvs import load_csv_rows

def _rows_from_db(conn, query: str):
    return list(fetch_rows(conn, query))

def _rows_from_csv(file_cfg: Dict[str, Any]):
    return list(load_csv_rows(
        path=file_cfg["path"],
        sep=file_cfg.get("sep", ","),
        columns=file_cfg.get("columns"),
        rename=file_cfg.get("rename")
    ))

def _merge_rows(*iterables):
    out = []
    for it in iterables:
        if not it: continue
        out.extend(list(it))
    return out

def build_from_config(cfg: Dict[str, Any]) -> Graph:
    ont = cfg["ontology"]
    g = load_schema(ont["schema_path"], ont.get("schema_format", "xml"))
    ns = get_namespace(ont["base_namespace"])

    # DB connection
    db_conn = None
    if cfg.get("sources", {}).get("db", {}).get("enabled"):
        db = cfg["sources"]["db"]
        db_conn = connect_postgres(db["host"], db["port"], db["dbname"], db["user"], db["password"])

    # CSV files
    csv_files = cfg.get("sources", {}).get("csv", {}).get("files", {}) if cfg.get("sources", {}).get("csv", {}).get("enabled") else {}

    def get_rows_for(key: str):
        rows_db = []
        if db_conn and key in cfg["sources"]["db"]["queries"]:
            rows_db = _rows_from_db(db_conn, cfg["sources"]["db"]["queries"][key])
        rows_csv = []
        if key == "plants" and "cmap_plants" in csv_files:
            rows_csv = _rows_from_csv(csv_files["cmap_plants"])
        elif key == "compounds":
            rows_csv = []
        elif key == "genes" and "npass_targets" in csv_files:
            rows_csv = _rows_from_csv(csv_files["npass_targets"])
        elif key == "pathways":
            rows_csv = []
        return _merge_rows(rows_db, rows_csv)

    steps = cfg.get("steps", {})
    # Entities
    if steps.get("add_plants", False):
        add_plants(g, ns, get_rows_for("plants"))

    if steps.get("add_compounds", False):
        add_compounds(g, ns, get_rows_for("compounds"))

    if steps.get("add_genes", False):
        add_genes(g, ns, get_rows_for("genes"))

    if steps.get("add_pathways", False):
        add_pathways(g, ns, get_rows_for("pathways"))

    # Relationships
    if steps.get("link_compound_to_plant", False):
        if "cmap_plant_ingredient" in csv_files:
            rel_rows = _rows_from_csv(csv_files["cmap_plant_ingredient"])
            link_compound_to_plant(g, ns, rel_rows, compound_id_key="compound_id", plant_id_key="plant_id")
        else:
            comp_rows = get_rows_for("compounds")
            link_compound_to_plant(g, ns, comp_rows, compound_id_key="compound_id", plant_id_key="plant_id")

    if db_conn:
        db_conn.close()
    return g

def build_and_export(cfg_path: str):
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    g = build_from_config(cfg)
    out_path = cfg["export"]["out_path"]
    fmt = cfg["export"].get("format", "turtle")
    g.serialize(destination=out_path, format=fmt)

    if cfg.get("provenance", {}).get("write_stats_json", False):
        stats_path = cfg["provenance"]["stats_path"]
        stats = {"triples": len(g), "out_path": out_path, "format": fmt}
        import json, os
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2)
    return out_path
