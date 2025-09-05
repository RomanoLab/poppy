from typing import Optional
from Bio import Entrez

def set_email(email: str):
    Entrez.email = email

def get_class_from_taxid(tax_id: str) -> Optional[str]:
    """Return the scientific name at rank 'class' for a taxonomy ID, or None."""
    try:
        with Entrez.efetch(db="taxonomy", id=tax_id, retmode="xml") as handle:
            records = Entrez.read(handle)
        if records:
            lineage = records[0].get("LineageEx", [])
            for rank in lineage:
                if rank.get("Rank", "").lower() == "class":
                    return rank.get("ScientificName")
    except Exception:
        return None
    return None

def is_plantae_by_name(scientific_name: str, email: Optional[str] = None) -> bool:
    """Return True if the scientific_name is in Plantae/Viridiplantae (NCBI)."""
    if email:
        Entrez.email = email
    try:
        search = Entrez.esearch(db="taxonomy", term=scientific_name)
        search_result = Entrez.read(search)
        search.close()
        if not search_result["IdList"]:
            return False
        tax_id = search_result["IdList"][0]
        fetch = Entrez.efetch(db="taxonomy", id=tax_id, retmode="xml")
        records = Entrez.read(fetch)
        fetch.close()
        rec = records[0]
        for rank in rec.get("LineageEx", []):
            if rank["Rank"].lower() == "kingdom" and ("plantae" in rank["ScientificName"].lower() or "viridiplantae" in rank["ScientificName"].lower()):
                return True
        lineage_str = rec.get("Lineage", "").lower()
        if "plantae" in lineage_str or "viridiplantae" in lineage_str:
            return True
        return False
    except Exception:
        return False
