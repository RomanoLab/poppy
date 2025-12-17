#!/usr/bin/env python
# coding: utf-8

# # Pipeline Work

# ### Step 1: Connect to SQL + Prepare RDF Enviornment

# In[1]:


# Imports and global setup
import psycopg2
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from Bio import Entrez
import re
import time

Entrez.email = "email"  # Set your Entrez email

# SQL connection
conn = psycopg2.connect(
    host="romanodb1.pmacs.upenn.edu",
    port="5432",
    dbname="opendata",
    user="user", # Replace with username
    password="password", # Replace with password
    sslmode="prefer",
    gssencmode="disable"
)
cur = conn.cursor()

# Namespace
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Utility for safe URIs
def sanitize_for_uri(text):
    return re.sub(r'\W|^(?=\d)', '_', text)


# ### Step 2: Load Ontology and Ensure 'Plant' Subclass Exists

# In[3]:


g = Graph()
g.parse("poppystructure.rdf", format="xml")

# Ensure Plant subclass exists under PlantTaxonomy
if (NS.Plant, RDF.type, OWL.Class) not in g:
    g.add((NS.Plant, RDF.type, OWL.Class))
    g.add((NS.Plant, RDFS.subClassOf, NS.PlantTaxonomy))
    g.add((NS.Plant, RDFS.label, Literal("Plant")))

print("Plant class ready in ontology.")


# ### Step 3: Add Organism Individuals to Ontology

# In[5]:


import pickle
import time
from tqdm import tqdm
import requests
from rdflib import Literal

# Normalize names
def normalize_scientific_name(name):
    name = name.strip()
    parts = name.split()
    if len(parts) >= 2:
        parts[0] = parts[0].capitalize()
        parts[1] = parts[1].lower()
        return f"{parts[0]} {parts[1]}"
    elif len(parts) == 1:
        return parts[0].capitalize()
    else:
        return ""

# Plant validation via POWO
def is_powo_plant(scientific_name):
    query = scientific_name.strip()
    url = f"https://powo.science.kew.org/api/2/search?q={query.replace(' ', '%20')}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                for result in data["results"]:
                    if result["name"].lower() == query.lower():
                        return True
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        return False

# Plant validation via NCBI 
def is_plantae(scientific_name):
    from Bio import Entrez
    Entrez.email = "email" # Replace with email
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
            if rank["Rank"].lower() == "kingdom" and (
                "plantae" in rank["ScientificName"].lower() or
                "viridiplantae" in rank["ScientificName"].lower()
            ):
                return True
        lineage_str = rec.get("Lineage", "").lower()
        if "plantae" in lineage_str or "viridiplantae" in lineage_str:
            return True
        return False
    except Exception as e:
        return False

# Load initialize cache
try:
    with open("plant_validation_cache.pkl", "rb") as f:
        validation_cache = pickle.load(f)
except FileNotFoundError:
    validation_cache = {}

# Query for all organisms
cur.execute("SELECT id, name FROM coconut.organisms")
organisms = cur.fetchall()

added_orgs = 0

for org_id, name in tqdm(organisms):
    if not name:
        continue
    clean_name = normalize_scientific_name(name)
    cache_hit = clean_name in validation_cache
    if cache_hit:
        is_plant = validation_cache[clean_name]
    else:
        # Try NCBI first (it's faster), only POWO if needed
        is_plant = is_plantae(clean_name)
        if not is_plant:
            is_plant = is_powo_plant(clean_name)
        validation_cache[clean_name] = is_plant
        # Save progress every 100 new queries
        if len(validation_cache) % 100 == 0:
            with open("plant_validation_cache.pkl", "wb") as f:
                pickle.dump(validation_cache, f)
        time.sleep(0.2)  # Only sleep after API requests

    if is_plant:
        organism_uri = NS[f"Organism_{org_id}"]
        g.add((organism_uri, RDF.type, OWL.NamedIndividual))
        g.add((organism_uri, RDF.type, NS.Plant))
        g.add((organism_uri, RDFS.label, Literal(name)))
        added_orgs += 1

print(f"Total organisms added: {added_orgs}")

# Save final cache and ontology
with open("plant_validation_cache.pkl", "wb") as f:
    pickle.dump(validation_cache, f)
g.serialize("phytotherapies_augmented.rdf", format="xml")
print("Step 1 complete: Organisms added and ontology saved.")


# In[7]:


import copy

# Duplicate the ontology in memory
g_copy = copy.deepcopy(g)
print("Ontology duplicated in memory.")

# Save the duplicate as a new file (keeps from having to start full process again if something goes wrong)
g_copy.serialize("phytotherapies_augmented_duplicate.rdf", format="xml")
print("Duplicate ontology file saved as 'phytotherapies_augmented_duplicate.rdf'.")


# ### Step 4: Load Augmented Ontology and Prepare Organism IDs

# In[9]:


from rdflib import Graph, Namespace, RDF

# Load ontology (has schema + plant instances)
g = Graph()
g.parse("phytotherapies_augmented.rdf", format="xml")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Extract Organism IDs
loaded_organism_ids = set()
for s, p, o in g.triples((None, RDF.type, NS.Plant)):
    if str(s).startswith(str(NS["Organism_"])):
        try:
            loaded_organism_ids.add(int(str(s).split("_")[-1]))
        except ValueError:
            pass

print(f"Loaded organism IDs in ontology: {list(loaded_organism_ids)[:5]}")
print(f"Total loaded organism IDs: {len(loaded_organism_ids)}")


# ## Step 5: Query Chemicals and All Needed Properties

# In[11]:


# Re-open SQL, has a lot of overlap with previous code but for clarity we re-import and re-connect

import psycopg2

conn = psycopg2.connect(
    host="romanodb1.pmacs.upenn.edu",
    port="5432",
    dbname="opendata",
    user="user", # Replace with username
    password="password", # Replace with password
    sslmode="prefer",
    gssencmode="disable"
)
cur = conn.cursor()

cur.execute("""
    SELECT p.molecule_id, p.chemical_class, mo.organism_id, p.molecular_weight, p.molecular_formula,
           m.name AS molecule_name, m.iupac_name, e.canonical_smiles
    FROM coconut.properties p
    JOIN coconut.molecule_organism mo ON p.molecule_id = mo.molecule_id
    JOIN coconut.molecules m ON p.molecule_id = m.id
    JOIN coconut.entries e ON p.molecule_id = e.molecule_id
""")
property_links = cur.fetchall()
print(f"Total candidate chemical-organism links: {len(property_links)}")


# ### Step 6: Add Chemical Instances and Properties without Duplicates

# In[12]:


# Enrich ontology with chemical individuals & links (no new classes minted)
import re
import pandas as pd
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef, BNode
from rdflib.namespace import XSD

# Configuration
ONT_IN  = "phytotherapies_augmented.rdf"              # input ontology
ONT_OUT = "phytotherapies_augmented_enriched.rdf"     # output ontology
BASE_NS = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"
RESTRICT_TO_EXISTING_ORGANISMS = False  # set True to skip links to organisms not already in the graph

# Load ontology
g = Graph()
g.parse(ONT_IN, format="xml")
NS = Namespace(BASE_NS)

# Reuse existing properties
isDerivedFrom        = NS.isDerivedFrom
hasMolecularWeight   = NS.hasMolecularWeight
hasMolecularFormula  = NS.hasMolecularFormula
hasCommonName        = NS.hasCommonName
hasIUPACName         = NS.hasIUPACName
hasSMILES            = NS.hasSMILES

# Helpers -
def sanitize_for_uri(text: str) -> str:
    """Make a safe fragment for IRIs: spaces/odd chars → _, collapse repeats, trim, cap length."""
    s = re.sub(r"\s+", "_", str(text).strip())
    s = re.sub(r"[^\w\-\.]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:200] or "unknown"

def make_uri(kind: str, value: str) -> URIRef:
    """Create a stable IRI under BASE_NS with sanitized tail."""
    return URIRef(f"{BASE_NS}{kind}_{sanitize_for_uri(value)}")

# Allow xsd:float OR xsd:double for hasMolecularWeight
def set_range_union_float_double(graph, prop):
    if (prop, RDF.type, OWL.DatatypeProperty) not in graph:
        graph.add((prop, RDF.type, OWL.DatatypeProperty))
        graph.add((prop, RDFS.label, Literal("hasMolecularWeight")))
    for o in list(graph.objects(prop, RDFS.range)):
        graph.remove((prop, RDFS.range, o))
    union = BNode(); head = BNode(); tail = BNode()
    graph.add((union, RDF.type, OWL.DataRange))
    graph.add((union, OWL.unionOf, head))
    graph.add((head,  RDF.first, XSD.float));  graph.add((head,  RDF.rest,  tail))
    graph.add((tail,  RDF.first, XSD.double)); graph.add((tail,  RDF.rest,  RDF.nil))
    graph.add((prop, RDFS.range, union))

set_range_union_float_double(g, hasMolecularWeight)

# Existing phytochemical subclasses (must already exist as OWL classes in the ontology)
phytochemical_classes = {
    "Carotenoid":     NS.Carotenoid,
    "DietaryFiber":   NS.DietaryFiber,
    "Isoprenoid":     NS.Isoprenoid,
    "Phytosterol":    NS.Phytosterol,
    "Polyphenol":     NS.Polyphenol,
    "Polysaccharide": NS.Polysaccharide,
    "Saponin":        NS.Saponin,
    "Unknown":        NS.Unknown,  # used only if this class exists
}

# SMILES classifier, placing into phytochemical classes based on simple rules
def classify_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ["Unknown"]
    classes = []
    mw = Descriptors.MolWt(mol)
    num_rings = Descriptors.RingCount(mol)
    num_oh = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[OH]")))
    num_c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    num_o = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")
    num_double_bonds = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C=C")))
    if num_rings >= 2 and num_oh >= 2: classes.append("Polyphenol")
    if num_c >= 30 and num_double_bonds >= 5: classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1: classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5: classes.append("Saponin")
    if mw > 500 and num_o > 10: classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15: classes.append("DietaryFiber")
    if "C=C" in smiles and num_c % 5 == 0: classes.append("Isoprenoid")
    return classes if classes else ["Unknown"]

# Load properties CSV → DataFrame 
def pick_col(df, options):
    for c in options:
        if c in df.columns: return c
    return None

def load_properties_df():
    # Use an already-loaded DF if it’s already in memory, otherwise load the first matching CSV from a short list, otherwise error: change as needed/if you know the name of the DF
    if "DF" in globals() and isinstance(globals()["DF"], pd.DataFrame):
        return globals()["DF"]
    # Try common filenames
    CANDIDATE_CSVS = [
        "activity_chem_taxon_dosage_refs_with_doi.csv",
        "properties.csv",
        "sancdb_master_plus_props.csv",
        "sancdb_master.csv",
    ]
    for p in CANDIDATE_CSVS:
        if Path(p).exists():
            print(f"Loaded properties from: {p}")
            return pd.read_csv(p, dtype=str).fillna("")
    raise FileNotFoundError("No properties CSV found. Provide DF or place one of the expected files.")

DF = load_properties_df()

ALIASES_REQ = {
    "molecule_id": ["molecule_id","id","chem_id","MoleculeID","ID","CHEMID","ChemID"],
    "organism_id": ["organism_id","Organism_id","organism","plant_id","Organism","TAXON","taxon","GENUS_SPECIES","GENUS SPECIES"],
}
ALIASES_OPT = {
    "db_class":         ["db_class","class","Classification","CHEM_CLASS"],
    "molecular_weight": ["molecular_weight","MolWt","molecular_mass","ExactMass","MolWeight","Mol_wt"],
    "molecular_formula":["molecular_formula","Molecular_formula","Formula","formula"],
    "molecule_name":    ["molecule_name","Common_name","name","Name","CHEM","Chem"],
    "iupac_name":       ["iupac_name","IUPAC_name","IUPAC"],
    "canonical_smiles": ["canonical_smiles","Canonical_smiles","SMILES","smiles"],
}

req_cols = {k: pick_col(DF, v) for k, v in ALIASES_REQ.items()}
missing_req = [k for k,v in req_cols.items() if v is None]
if missing_req:
    raise KeyError("Missing required column(s): " + ", ".join(missing_req) + f"\nAvailable: {list(DF.columns)}")
opt_cols = {k: pick_col(DF, v) for k, v in ALIASES_OPT.items()}

# Optional: only link to organism individuals already present
existing_orgs = set()
if RESTRICT_TO_EXISTING_ORGANISMS:
    existing_orgs = { str(s).split("_", 1)[-1] for s in g.subjects(RDF.type, NS.Organism) }

# Populate RDF
added_chemicals = set()
added_chems_count = 0
total_links = 0

for _, row in DF.iterrows():
    molecule_id = row[req_cols["molecule_id"]]
    organism_id = row[req_cols["organism_id"]]

    # Skip if restricting and organism not in graph
    if RESTRICT_TO_EXISTING_ORGANISMS and sanitize_for_uri(organism_id) not in {sanitize_for_uri(x) for x in existing_orgs}:
        continue

    molecular_weight  = (row[opt_cols["molecular_weight"]]  if opt_cols["molecular_weight"]  else "")
    molecular_formula = (row[opt_cols["molecular_formula"]] if opt_cols["molecular_formula"] else "")
    molecule_name     = (row[opt_cols["molecule_name"]]     if opt_cols["molecule_name"]     else "")
    iupac_name        = (row[opt_cols["iupac_name"]]        if opt_cols["iupac_name"]        else "")
    canonical_smiles  = (row[opt_cols["canonical_smiles"]]  if opt_cols["canonical_smiles"]  else "")

    chem_uri = make_uri("Chemical", molecule_id)
    org_uri  = make_uri("Organism", organism_id)

    if chem_uri not in added_chemicals:
        g.add((chem_uri, RDF.type, OWL.NamedIndividual))  # do NOT type to a new NS.Chemical class

        predicted = classify_smiles(canonical_smiles) if canonical_smiles else ["Unknown"]
        for cls in predicted:
            cls_uri = phytochemical_classes.get(cls)
            if cls_uri and (cls_uri, RDF.type, OWL.Class) in g:
                g.add((chem_uri, RDF.type, cls_uri))

        # typed numeric MW (defaults to xsd:double; allowed by union)
        if molecular_weight not in ("", None):
            try:
                mw_val = float(str(molecular_weight).strip())
                g.add((chem_uri, hasMolecularWeight, Literal(mw_val)))
            except ValueError:
                pass  # ignore non-numeric weights

        if molecular_formula:
            g.add((chem_uri, hasMolecularFormula, Literal(molecular_formula)))
        if molecule_name:
            g.add((chem_uri, hasCommonName, Literal(molecule_name)))
        if iupac_name:
            g.add((chem_uri, hasIUPACName, Literal(iupac_name)))
        if canonical_smiles:
            g.add((chem_uri, hasSMILES, Literal(canonical_smiles)))
            g.add((chem_uri, RDFS.label, Literal(canonical_smiles)))

        added_chemicals.add(chem_uri)
        added_chems_count += 1

    # link chemical → organism (safe even if organism individual not pre-declared)
    g.add((chem_uri, isDerivedFrom, org_uri))
    total_links += 1

# Save
g.serialize(ONT_OUT, format="xml")
print(f"Total unique chemicals added: {added_chems_count}")
print(f"Total chemical-organism links added: {total_links}")
print(f"Enriched ontology saved to {ONT_OUT}")


# ### Step 7: Add DOI

# In[15]:


# Link chemicals & organisms to papers using DOI (no DB required)
from rdflib import RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD
from pathlib import Path
import pandas as pd
import re
from collections import deque

# helpers
# reuse existing sanitize_for_uri if present; otherwise define a safe one
try:
    sanitize_for_uri
except NameError:
    def sanitize_for_uri(text: str) -> str:
        s = re.sub(r"\s+", "_", str(text).strip())
        s = re.sub(r"[^\w\-\.]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s[:200] or "unknown"

def make_uri(kind: str, value: str) -> URIRef:
    return URIRef(str(NS) + f"{kind}_{sanitize_for_uri(value)}")

def normalize_doi(doi: str) -> str:
    d = str(doi).strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d, flags=re.I)
    d = re.sub(r'^(doi|dois)\s*:?\s*', '', d, flags=re.I)
    return d.rstrip(").,;]")

def is_subclass_of(graph, child, root):
    if child == root:
        return True
    seen = {child}; q = deque([child])
    while q:
        c = q.popleft()
        for sup in graph.objects(c, RDFS.subClassOf):
            if sup == root: return True
            if sup not in seen:
                seen.add(sup); q.append(sup)
    return False

def find_class_by_label_or_local(graph, names):
    names = list(names)
    # label matches
    for n in names:
        for s in graph.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in graph:
                return s
    # local-name matches
    for s in graph.subjects(RDF.type, OWL.Class):
        local = str(s).split("#")[-1].split("/")[-1]
        if local in names:
            return s
    return None

# resolve ResearchConcept and align a ScientificPaper class
RESEARCH_ROOT = find_class_by_label_or_local(g, ["ResearchConcept", "Research Concept"])
if RESEARCH_ROOT is None:
    print("[WARN] ResearchConcept not found; papers will be created without subclass alignment.")

paper_candidates = []
for nm in ["ScientificPaper", "Paper"]:
    c = find_class_by_label_or_local(g, [nm])
    if c is not None:
        paper_candidates.append(c)

PAPER_CLASS = None
for c in paper_candidates:
    if RESEARCH_ROOT and is_subclass_of(g, c, RESEARCH_ROOT):
        PAPER_CLASS = c; break
if PAPER_CLASS is None and paper_candidates:
    PAPER_CLASS = paper_candidates[0]
    if RESEARCH_ROOT and not is_subclass_of(g, PAPER_CLASS, RESEARCH_ROOT):
        g.add((PAPER_CLASS, RDFS.subClassOf, RESEARCH_ROOT))
if PAPER_CLASS is None and RESEARCH_ROOT is not None:
    PAPER_CLASS = RESEARCH_ROOT  # safe fallback

# retire stray default-IRI ScientificPaper class if present and not selected
ns_scipaper = URIRef(str(NS) + "ScientificPaper")
if PAPER_CLASS and ns_scipaper != PAPER_CLASS and (ns_scipaper, RDF.type, OWL.Class) in g:
    for s in list(g.subjects(RDF.type, ns_scipaper)):
        g.remove((s, RDF.type, ns_scipaper)); g.add((s, RDF.type, PAPER_CLASS))
    if not any(g.triples((ns_scipaper, RDFS.subClassOf, None))) and not any(g.triples((None, RDFS.subClassOf, ns_scipaper))):
        g.remove((ns_scipaper, RDF.type, OWL.Class))

# ensure hasPaper object property and set its range
hasPaper = NS.hasPaper
if (hasPaper, RDF.type, OWL.ObjectProperty) not in g:
    g.add((hasPaper, RDF.type, OWL.ObjectProperty))
    g.add((hasPaper, RDFS.label, Literal("hasPaper")))
# set/replace range to chosen PAPER_CLASS when available
for old in list(g.objects(hasPaper, RDFS.range)):
    g.remove((hasPaper, RDFS.range, old))
if PAPER_CLASS:
    g.add((hasPaper, RDFS.range, PAPER_CLASS))

# load a table with DOI + IDs (use existing DF or auto-load CSV)
def pick_col(df, options):
    for c in options:
        if c in df.columns: return c
    return None

if "DF" in globals() and isinstance(DF, pd.DataFrame):
    _df = DF.copy()
else:
    CANDS = [
        "activity_chem_taxon_dosage_refs_with_doi.csv",
        "properties.csv",
        "citations.csv",
    ]
    path = next((p for p in CANDS if Path(p).exists()), None)
    if path is None:
        raise FileNotFoundError("Could not find a CSV with DOIs. Looked for: " + ", ".join(CANDS))
    print(f"Loaded DOI data from: {path}")
    _df = pd.read_csv(path, dtype=str)

_df = _df.fillna("")

# map columns
COL_DOI  = pick_col(_df, ["DOI","doi","paper_doi"])
COL_CHEM = pick_col(_df, ["CHEMID","ChemID","molecule_id","chem_id","ID"])
COL_ORG  = pick_col(_df, ["TAXON","taxon","organism_id","Organism_id","GENUS_SPECIES","GENUS SPECIES","organism"])
if COL_DOI is None:
    raise KeyError("No DOI column found (try one of DOI/doi/paper_doi).")

# create new, unique identifiers (URIs/IRIs) for Paper entitie & link
doi_to_uri = {}
papers_added = 0
chem_links = 0
plant_links = 0

for _, row in _df.iterrows():
    doi_raw = row[COL_DOI]
    if not doi_raw or not str(doi_raw).strip():
        continue
    doi_norm = normalize_doi(doi_raw)

    # one paper per DOI
    paper_uri = doi_to_uri.get(doi_norm)
    if paper_uri is None:
        paper_uri = make_uri("Paper", doi_norm)
        if not any(g.triples((paper_uri, None, None))):
            g.add((paper_uri, RDF.type, OWL.NamedIndividual))
            if PAPER_CLASS:
                g.add((paper_uri, RDF.type, PAPER_CLASS))
            g.add((paper_uri, RDFS.label, Literal(doi_norm)))
            papers_added += 1
        doi_to_uri[doi_norm] = paper_uri

    # link chemical (if chem individual exists)
    if COL_CHEM:
        chem_id = row[COL_CHEM]
        if chem_id and str(chem_id).strip():
            chem_uri = make_uri("Chemical", chem_id)
            if any(g.triples((chem_uri, None, None))):
                g.add((chem_uri, hasPaper, paper_uri)); chem_links += 1

    # link organism (if organism individual exists)
    if COL_ORG:
        org_id = row[COL_ORG]
        if org_id and str(org_id).strip():
            org_uri = make_uri("Organism", org_id)
            if any(g.triples((org_uri, None, None))):
                g.add((org_uri, hasPaper, paper_uri)); plant_links += 1

print(f"Added {papers_added} paper individuals (class={PAPER_CLASS if PAPER_CLASS else 'None'})")
print(f"Linked chemicals via hasPaper: {chem_links}")
print(f"Linked organisms via hasPaper: {plant_links}")


# ### Step 8: Save Final Ontology

# In[16]:


g.serialize("phytotherapies_augmented_with_chemicals.rdf", format="xml")
print("Final ontology saved as phytotherapies_augmented_with_chemicals.rdf")


# ### Step 9: Review, Print Sample Triples (Optional)

# In[19]:


from rdflib import RDF, RDFS

print("Sample chemical triples (by hasSMILES):")
for s, _, _ in g.triples((None, NS.hasSMILES, None)):
    for pp, oo in g.predicate_objects(s):
        print(f"{s} -- {pp} -- {oo}")
    print("---")
    break  # just the first one


# # Loading CMAUP data into Ontology

# In[21]:


# Turn CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt into a .csv
import pandas as pd

# Load the tab-delimited file with no headers
df = pd.read_csv("CMAUPv2.0_download_Plant_Ingredient_Associations_allIngredients.txt", 
                 sep='\t', 
                 header=None,  # Treat the first row as data, not header
                 names=["Plant_ID", "Ingredient_ID"])  # Set column names

# Save as CSV
df.to_csv("step1.csv", index=False)


# In[23]:


#add plant names
import pandas as pd

# Read your step1.csv (which has Plant_ID, Ingredient_ID)
step1 = pd.read_csv("step1.csv")

# Read the plants file, assuming it's tab-delimited and has headers
plants = pd.read_csv("CMAUPv2.0_download_Plants.txt", sep='\t')

# Merge on 'Plant_ID'
merged = pd.merge(step1, plants[['Plant_ID', 'Plant_Name']], on='Plant_ID', how='left')

# Save to new CSV
merged.to_csv("step2.csv", index=False)


# In[25]:


#add targeted pathway (target_ID)
import pandas as pd

# Load step2.csv
step2 = pd.read_csv("step2.csv")

# Load Ingredient-Target file (assuming tab-delimited and has Ingredient_ID, Target_ID columns)
ingredient_target = pd.read_csv("CMAUPv2.0_download_Ingredient_Target_Associations_ActivityValues_References.txt", sep='\t')

# Merge on Ingredient_ID
merged = pd.merge(step2, ingredient_target[['Ingredient_ID', 'Target_ID']], on='Ingredient_ID', how='left')

# Save as step3.csv
merged.to_csv("step3.csv", index=False)


# In[27]:


#add common name (pref_name), molecular weight (MW), SMILES, and iupac_name
import pandas as pd

# Load step3.csv
step3 = pd.read_csv("step3.csv")

# Load the ingredients file (assuming tab-delimited and with headers)
ingredients = pd.read_csv("CMAUPv2.0_download_Ingredients_All (1).txt", sep='\t')

# Rename 'np_id' to 'Ingredient_ID' to enable merging
ingredients = ingredients.rename(columns={'np_id': 'Ingredient_ID'})

# Merge on Ingredient_ID, keeping only needed columns from ingredients
merged = pd.merge(
    step3,
    ingredients[['Ingredient_ID', 'pref_name', 'MW', 'SMILES', 'iupac_name']],
    on='Ingredient_ID',
    how='left'
)

# Save as step4.csv
merged.to_csv("step4.csv", index=False)


# In[29]:


#drop all duplicate rows

import pandas as pd

# Load the CSV
df = pd.read_csv("step4.csv")

# Remove duplicate rows (across all columns)
df_cleaned = df.drop_duplicates()

# Save the result
df_cleaned.to_csv("step5.csv", index=False)


# In[30]:


# replace Target_ID with TargetedPathway using CMAUP target names
# Build step6.csv by replacing Target_ID with Protein_Name → TargetedPathway
import pandas as pd
from pathlib import Path
import re

# Load inputs
df = pd.read_csv("step5.csv", dtype=str)
df.columns = [c.strip() for c in df.columns]

targets_path = Path("CMAUPv2.0_download_Targets.txt")
if not targets_path.exists():
    raise FileNotFoundError("CMAUPv2.0_download_Targets.txt not found in working directory.")

targets = pd.read_csv(targets_path, sep="\t", dtype=str, low_memory=False)
targets.columns = [c.strip() for c in targets.columns]

# Case-insensitive column resolution
tcols = {c.lower(): c for c in targets.columns}
tid_col = tcols.get("target_id")
pname_col = tcols.get("protein_name")

if tid_col is None or pname_col is None:
    raise KeyError(f"'Target_ID' and/or 'Protein_Name' not found in {targets_path}. "
                   f"Available columns: {list(targets.columns)}")

# Build mapping: Target_ID -> Protein_Name (dedup by Target_ID)
tmap_df = (targets[[tid_col, pname_col]]
           .dropna(subset=[tid_col, pname_col])
           .drop_duplicates(subset=[tid_col]))
tmap = dict(zip(tmap_df[tid_col].astype(str).str.strip(),
                tmap_df[pname_col].astype(str).str.strip()))

if "Target_ID" not in df.columns:
    raise KeyError("step5.csv must contain a 'Target_ID' column.")

# Map and insert 'TargetedPathway' at the same position where 'Target_ID' was
pos = df.columns.get_loc("Target_ID")
mapped = df["Target_ID"].astype(str).str.strip().map(tmap)

# If a Target_ID has no match, keep the ID (or use '' if you prefer blanks)
mapped = mapped.fillna(df["Target_ID"])

df.insert(pos, "TargetedPathway", mapped)
df = df.drop(columns=["Target_ID"])

# Save
df.to_csv("step6.csv", index=False)

# Coverage report
total = len(mapped)
hits = int((mapped != df.get("TargetedPathway", mapped)).sum())  # (not used here since we replaced in-place)
resolved = int((mapped != "").sum())
print(f"Wrote step6.csv — resolved names for {mapped.notna().sum()}/{total} rows.")


# In[31]:


#add molecular formula

import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

# Load your file
df = pd.read_csv("step6.csv")

# Function to compute molecular formula from SMILES
def smiles_to_formula(smiles):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            return rdMolDescriptors.CalcMolFormula(mol)
    except:
        return None
    return None

# Create new column with formula
df['Molecular_Formula'] = df['SMILES'].apply(smiles_to_formula)

# Save result
df.to_csv("step7.csv", index=False)


# In[33]:


# Sorting compounds into phytochemical classes:

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

def classify_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "Unknown"

    classes = []

    mw = Descriptors.MolWt(mol)
    num_rings = Descriptors.RingCount(mol)
    num_oh = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[OH]")))
    num_c = len([atom for atom in mol.GetAtoms() if atom.GetSymbol() == 'C'])
    num_o = len([atom for atom in mol.GetAtoms() if atom.GetSymbol() == 'O'])
    num_double_bonds = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C=C")))

    # Heuristic rules (non-exclusive)
    if num_rings >= 2 and num_oh >= 2:
        classes.append("Polyphenol")
    if num_c >= 30 and num_double_bonds >= 5:
        classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1:
        classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5:
        classes.append("Saponin")
    if mw > 500 and num_o > 10:
        classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15:
        classes.append("DietaryFiber")
    if "C=C" in smiles and num_c % 5 == 0:
        classes.append("Isoprenoid")

    if not classes:
        classes.append("Unknown")

    return ";".join(classes)

# Load input
df = pd.read_csv("step7.csv")
df = df.drop_duplicates(subset="SMILES")
df = df.dropna(subset=["SMILES"])
df["SMILES"] = df["SMILES"].astype(str)

# Multi-label classification
df['Phytochemical_Class'] = df['SMILES'].apply(classify_smiles)

# Save to new file
df.to_csv("step8.csv", index=False)


# In[35]:


# drop Plant_ID and Ingredient_ID from file and replace n.a. with blanks:

import pandas as pd

# Load the CSV
df = pd.read_csv("step8.csv")

# Drop the specified columns
df = df.drop(columns=["Plant_ID", "Ingredient_ID"], errors='ignore')

# Replace 'n.a.' strings with empty strings
df = df.replace("n.a.", "")

# Save to new CSV
df.to_csv("step9.csv", index=False)


# ### Loading all of this CMAUP data into the ontology

# In[37]:


# Step 1: Load Existing Ontology
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal

g = Graph()
g.parse("phytotherapies_augmented_with_chemicals.rdf", format="xml")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Object and data properties
isDerivedFrom = NS.isDerivedFrom
hasMolecularWeight = NS.hasMolecularWeight
hasMolecularFormula = NS.hasMolecularFormula
hasCommonName = NS.hasCommonName
hasIUPACName = NS.hasIUPACName
hasSMILES = NS.hasSMILES

# Subclasses of ChemicalConcept
phytochemical_classes = {
    "Carotenoid": NS.Carotenoid,
    "DietaryFiber": NS.DietaryFiber,
    "Isoprenoid": NS.Isoprenoid,
    "Phytosterol": NS.Phytosterol,
    "Polyphenol": NS.Polyphenol,
    "Polysaccharide": NS.Polysaccharide,
    "Saponin": NS.Saponin,
    "Unknown": NS.Unknown,
}


# In[38]:


# Step 2: Load and Clean CSV
import pandas as pd

na_values = ["", "nan", "NaN", "NAN"]
df9 = pd.read_csv("step9.csv", na_values=na_values)
df9 = df9.dropna(subset=["SMILES", "Phytochemical_Class", "Plant_Name"])
df9["SMILES"] = df9["SMILES"].astype(str).str.strip()
df9["Phytochemical_Class"] = df9["Phytochemical_Class"].astype(str).str.strip()
df9["Plant_Name"] = df9["Plant_Name"].astype(str).str.strip()
df9["Molecular_Formula"] = df9["Molecular_Formula"].astype(str).str.strip()
df9["iupac_name"] = df9["iupac_name"].astype(str).str.strip()
df9["pref_name"] = df9["pref_name"].astype(str).str.strip()
df9["MW"] = pd.to_numeric(df9["MW"], errors="coerce")

df9 = df9.drop_duplicates(subset=["SMILES"])


# In[39]:


# Step 3: Add Plant Instances
existing_plant_names = {
    str(o).strip().lower()
    for s, p, o in g.triples((None, RDF.type, NS.Plant))
    if isinstance(s, Namespace)
}

added_plants = 0
for plant_name in df9["Plant_Name"].dropna().drop_duplicates():
    norm_name = plant_name.strip()
    if norm_name.lower() in existing_plant_names:
        continue

    plant_uri = NS[f"Plant_{norm_name.replace(' ', '_')}"]
    g.add((plant_uri, RDF.type, OWL.NamedIndividual))
    g.add((plant_uri, RDF.type, NS.Plant))
    g.add((plant_uri, RDFS.label, Literal(norm_name)))
    added_plants += 1

print(f"New plants added: {added_plants}")


# In[40]:


# Step 4: Add Chemical Instances and Data Properties
existing_smiles = {
    str(o).strip() for s, p, o in g.triples((None, hasSMILES, None))
}

added_chemicals = 0
for _, row in df9.iterrows():
    smiles = row["SMILES"]
    if smiles in existing_smiles:
        continue

    chem_uri = NS[f"Chemical_{abs(hash(smiles))}"]
    g.add((chem_uri, RDF.type, OWL.NamedIndividual))

    for cls in row["Phytochemical_Class"].split(";"):
        class_uri = phytochemical_classes.get(cls.strip())
        if class_uri:
            g.add((chem_uri, RDF.type, class_uri))

    g.add((chem_uri, hasSMILES, Literal(smiles)))
    g.add((chem_uri, RDFS.label, Literal(smiles)))

    if pd.notna(row["MW"]):
        g.add((chem_uri, hasMolecularWeight, Literal(row["MW"])))
    if pd.notna(row["Molecular_Formula"]):
        g.add((chem_uri, hasMolecularFormula, Literal(row["Molecular_Formula"])))
    if pd.notna(row["iupac_name"]):
        g.add((chem_uri, hasIUPACName, Literal(row["iupac_name"])))
    if pd.notna(row["pref_name"]):
        g.add((chem_uri, hasCommonName, Literal(row["pref_name"])))

    added_chemicals += 1
    existing_smiles.add(smiles)

print(f"New chemical instances added: {added_chemicals}")


# In[41]:


# Step 5: Add isDerivedFrom Links
existing_links = {
    (str(s), str(o))
    for s, p, o in g.triples((None, isDerivedFrom, None))
}

new_links = 0
for _, row in df9.iterrows():
    smiles = row["SMILES"]
    plant_name = row["Plant_Name"]
    chem_uri = NS[f"Chemical_{abs(hash(smiles))}"]
    plant_uri = NS[f"Plant_{plant_name.replace(' ', '_')}"]

    if (str(chem_uri), str(plant_uri)) not in existing_links:
        g.add((chem_uri, isDerivedFrom, plant_uri))
        existing_links.add((str(chem_uri), str(plant_uri)))
        new_links += 1

print(f"New isDerivedFrom links added: {new_links}")


# In[42]:


# Step 6: Save Updated Ontology
g.serialize("phytotherapies_augmented_COCONUT_CMAUP.rdf", format="xml")
print("Ontology saved to phytotherapies_augmented_enriched.rdf")


# Add clinical trial data

# In[44]:


# Step 7: Add ClinicalTrial instances from CMAUP PHDA and link via hasClinicalStudy
# Fix ALL hasMolecularWeight ranges/restrictions to (xsd:float ⊔ xsd:double)
import re, hashlib
import pandas as pd
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef, BNode
from rdflib.namespace import XSD

# Load the ontology you just saved in Step 6
g = Graph()
g.parse("phytotherapies_augmented_COCONUT_CMAUP.rdf", format="xml")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")
isDerivedFrom = NS.isDerivedFrom

# Fix hasMolecularWeight (float ⊔ double) EVERYWHERE
def _localname(u: URIRef) -> str:
    s = str(u); return s.rsplit('#',1)[-1].rsplit('/',1)[-1]

def _build_union_float_double(graph):
    u = BNode(); a = BNode(); b = BNode()
    graph.add((u, RDF.type, OWL.DataRange))
    graph.add((u, OWL.unionOf, a))
    graph.add((a, RDF.first, XSD.float));  graph.add((a, RDF.rest,  b))
    graph.add((b, RDF.first, XSD.double)); graph.add((b, RDF.rest,  RDF.nil))
    return u

def _find_all_hmw_props(graph):
    props = set()
    for p in graph.subjects(RDFS.label, Literal("hasMolecularWeight")):
        if (p, RDF.type, OWL.DatatypeProperty) in graph: props.add(p)
    for p in graph.subjects(RDF.type, OWL.DatatypeProperty):
        if _localname(p).lower() == "hasmolecularweight": props.add(p)
    for p in graph.predicates(None, None):
        if isinstance(p, URIRef) and _localname(p).lower() == "hasmolecularweight":
            props.add(p)
    return sorted(props, key=str)

def _replace_range_and_restrictions(graph, p):
    removed = list(graph.objects(p, RDFS.range))
    for o in removed: graph.remove((p, RDFS.range, o))
    u = _build_union_float_double(graph)
    graph.add((p, RDFS.range, u))
    fixed = 0
    for r in graph.subjects(RDF.type, OWL.Restriction):
        if (r, OWL.onProperty, p) in graph:
            for pred in (OWL.allValuesFrom, OWL.someValuesFrom):
                for o in list(graph.objects(r, pred)):
                    if o == XSD.float:
                        graph.remove((r, pred, o)); graph.add((r, pred, u)); fixed += 1
    return len(removed), fixed

hmw_props = _find_all_hmw_props(g)
if not hmw_props:
    # ensure at least the namespaced property exists
    hmw = NS.hasMolecularWeight
    g.add((hmw, RDF.type, OWL.DatatypeProperty))
    g.add((hmw, RDFS.label, Literal("hasMolecularWeight")))
    hmw_props = [hmw]

canonical_hmw = next((p for p in hmw_props if str(p).startswith(str(NS))), hmw_props[0])
rng_removed = restr_fixed = 0
for p in hmw_props:
    r, f = _replace_range_and_restrictions(g, p); rng_removed += r; restr_fixed += f

# move literal assertions to the canonical property if multiples exist
moved_vals = 0
for p in hmw_props:
    if p == canonical_hmw: continue
    for s, _, v in list(g.triples((None, p, None))):
        g.add((s, canonical_hmw, v)); g.remove((s, p, v)); moved_vals += 1

print(f"[MW fix] ranges removed={rng_removed}, restrictions fixed={restr_fixed}, values moved={moved_vals}")

# 1) ClinicalTrial schema (aligned under ResearchConcept if present)
def sanitize_for_uri(text: str) -> str:
    s = re.sub(r"\s+", "_", str(text).strip())
    s = re.sub(r"[^\w\-\.]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:200] or "unknown"

def _find_class_by_label_or_local(names):
    names = list(names)
    for n in names:
        for s in g.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in g:
                return s
    for s in g.subjects(RDF.type, OWL.Class):
        if _localname(s) in names:
            return s
    return None

# Ensure ClinicalTrial exists and is optionally a subclass of ResearchConcept
RESEARCH_ROOT = _find_class_by_label_or_local(["ResearchConcept","Research Concept"])
TRIAL_CLASS = _find_class_by_label_or_local(["ClinicalTrial","Clinical Trial"]) or NS.ClinicalTrial
if (TRIAL_CLASS, RDF.type, OWL.Class) not in g:
    g.add((TRIAL_CLASS, RDF.type, OWL.Class))
    g.add((TRIAL_CLASS, RDFS.label, Literal("ClinicalTrial")))
if RESEARCH_ROOT and (TRIAL_CLASS, RDFS.subClassOf, RESEARCH_ROOT) not in g:
    g.add((TRIAL_CLASS, RDFS.subClassOf, RESEARCH_ROOT))

# Ensure hasClinicalStudy exists and has range ClinicalTrial
hasClinicalStudy = NS.hasClinicalStudy
if (hasClinicalStudy, RDF.type, OWL.ObjectProperty) not in g:
    g.add((hasClinicalStudy, RDF.type, OWL.ObjectProperty))
    g.add((hasClinicalStudy, RDFS.label, Literal("hasClinicalStudy")))
for o in list(g.objects(hasClinicalStudy, RDFS.range)):
    g.remove((hasClinicalStudy, RDFS.range, o))
g.add((hasClinicalStudy, RDFS.range, TRIAL_CLASS))

# Optional data props
hasEvidenceText = NS.hasEvidenceText
hasNCTId       = NS.hasNCTId
for prop, lbl in [(hasEvidenceText, "hasEvidenceText"), (hasNCTId, "hasNCTId")]:
    if (prop, RDF.type, OWL.DatatypeProperty) not in g:
        g.add((prop, RDF.type, OWL.DatatypeProperty))
        g.add((prop, RDFS.label, Literal(lbl)))

# 2) Helpers for trial minting/linking
_SPLIT_RE = re.compile(r"\s*(?:\|\||\||;;|;|\/\/|,|\n|\r)\s*")
def split_multi(val):
    if val is None: return []
    s = str(val).strip()
    if not s or s.lower() in {"na","n/a","none"}: return []
    parts = [p.strip() for p in _SPLIT_RE.split(s) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            out.append(p); seen.add(p)
    return out

def mint_trial_uri(plant_id, ev_text):
    ncts = sorted(set(re.findall(r"NCT\d{8}", ev_text)))
    if ncts:
        local = f"CT_{ncts[0]}"
    else:
        h = hashlib.sha1(f"{plant_id}|{ev_text}".encode("utf-8")).hexdigest()[:12]
        local = f"CT_p{sanitize_for_uri(plant_id)}_{h}"
    return NS[f"ClinicalTrial_{local}"], ncts

def add_trial_individual(plant_id, ev_text, source_tag):
    trial_uri, ncts = mint_trial_uri(plant_id, ev_text)
    if (trial_uri, RDF.type, TRIAL_CLASS) not in g:
        g.add((trial_uri, RDF.type, OWL.NamedIndividual))
        g.add((trial_uri, RDF.type, TRIAL_CLASS))
        label = (ncts[0] if ncts else ev_text[:120] + ("…" if len(ev_text) > 120 else ""))
        g.add((trial_uri, RDFS.label, Literal(label)))
        g.add((trial_uri, hasEvidenceText, Literal(ev_text, datatype=XSD.string)))
        for n in ncts:
            g.add((trial_uri, hasNCTId, Literal(n)))
        g.add((trial_uri, NS.sourceColumn, Literal(source_tag)))
    return trial_uri

def plant_uri_from_name(plant_name: str):
    return NS[f"Plant_{sanitize_for_uri(plant_name)}"]

def existing_node(uri):
    return next(g.triples((uri, None, None)), None) is not None

# 3) Load CMAUP PHDA + Plants (for Plant_ID -> Plant_Name)
phda_path = next((p for p in [
    "CMAUPv2.0_download_Plant_Human_Disease_Associations.txt",
    "CMAUPv2.0_download_Plant_Human_Disease_Associations.tsv",
    "CMAUPv2.0_download_Plant_Human_Disease_Associations.csv",
] if Path(p).exists()), None)
if phda_path is None:
    raise FileNotFoundError("Cannot find CMAUP Plant_Human_Disease_Associations (txt/tsv/csv) in working directory.")

sep = "\t" if Path(phda_path).suffix.lower() in {".txt", ".tsv"} else ","
phda = pd.read_csv(phda_path, sep=sep, dtype=str, low_memory=False).fillna("")
phda.columns = [c.strip() for c in phda.columns]

PLANT_ID_COL   = "Plant_ID"
PLANT_TRIALCOL = "Association_by_Clinical_Trials_of_Plant"
INGR_TRIALCOL  = "Association_by_Clinical_Trials_of_Plant_Ingredients"
for col in [PLANT_ID_COL, PLANT_TRIALCOL, INGR_TRIALCOL]:
    if col not in phda.columns:
        raise KeyError(f"Missing required column in PHDA file: {col}")

plants_df = pd.read_csv("CMAUPv2.0_download_Plants.txt", sep="\t", dtype=str).fillna("")
plants_df.columns = [c.strip() for c in plants_df.columns]
if "Plant_ID" not in plants_df.columns or "Plant_Name" not in plants_df.columns:
    raise KeyError("Plants file must contain columns 'Plant_ID' and 'Plant_Name'.")

pid_to_pname = dict(zip(plants_df["Plant_ID"].astype(str), plants_df["Plant_Name"].astype(str)))

# 4) Precompute chem → plant map (per your Step 5 links)
plant_key_to_chems = {}
for chem_uri, _, plant_uri in g.triples((None, isDerivedFrom, None)):
    pl_local = _localname(plant_uri)
    if pl_local.startswith("Plant_"):
        key = pl_local[len("Plant_"):]   # already sanitized in earlier steps
        plant_key_to_chems.setdefault(key, set()).add(chem_uri)

# 5) Create trials and link
trial_count = plant_links = chem_links = 0

for _, row in phda.iterrows():
    pid = str(row.get(PLANT_ID_COL, "")).strip()
    if not pid:
        continue
    plant_name = pid_to_pname.get(pid)
    if not plant_name:
        continue

    p_uri = plant_uri_from_name(plant_name)
    if not existing_node(p_uri):
        continue

    plant_key = sanitize_for_uri(plant_name)

    # Trials “of Plant”
    for ev in split_multi(row.get(PLANT_TRIALCOL)):
        t_uri = add_trial_individual(pid, ev, PLANT_TRIALCOL)
        g.add((p_uri, hasClinicalStudy, t_uri))
        trial_count += 1; plant_links += 1

    # Trials “of Plant_Ingredients”: link plant + all derived chemicals
    for ev in split_multi(row.get(INGR_TRIALCOL)):
        t_uri = add_trial_individual(pid, ev, INGR_TRIALCOL)
        g.add((p_uri, hasClinicalStudy, t_uri))
        trial_count += 1; plant_links += 1
        for chem_uri in plant_key_to_chems.get(plant_key, []):
            g.add((chem_uri, hasClinicalStudy, t_uri)); chem_links += 1

print(
    f"Step 6.8: created/updated {trial_count} ClinicalTrial instances; "
    f"added {plant_links} plant→trial and {chem_links} chemical→trial links."
)

# overwrite the same file so later steps (MACCS, DrugCentral) pick up trials
g.serialize("phytotherapies_augmented_COCONUT_CMAUP.rdf", format="xml")
print("Trials added. Updated ontology saved to phytotherapies_augmented_COCONUT_CMAUP.rdf")


# ### Adding MACCs Keys to Ontology

# In[55]:


from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdkit import Chem
from rdkit.Chem import MACCSkeys

# Load existing ontology
g = Graph()
g.parse("phytotherapies_augmented_COCONUT_CMAUP.rdf", format="xml")

# Define namespace
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Data properties
hasSMILES = NS.hasSMILES
hasMACCs = NS.hasMACCs

# Subclasses of ChemicalConcept (manually listed since they’re not queried dynamically)
phytochemical_classes = {
    "Carotenoid": NS.Carotenoid,
    "DietaryFiber": NS.DietaryFiber,
    "Isoprenoid": NS.Isoprenoid,
    "Phytosterol": NS.Phytosterol,
    "Polyphenol": NS.Polyphenol,
    "Polysaccharide": NS.Polysaccharide,
    "Saponin": NS.Saponin,
    "Unknown": NS.Unknown,
}
chemical_classes = set(phytochemical_classes.values())

# Add MACCS to each relevant chemical individual
added_maccs = 0
for s, p, o in g.triples((None, RDF.type, None)):
    if o in chemical_classes:
        chem_uri = s

        # Skip if MACCS already exists
        if (chem_uri, hasMACCs, None) in g:
            continue

        # Get SMILES
        smiles = None
        for _, _, smile_obj in g.triples((chem_uri, hasSMILES, None)):
            smiles = str(smile_obj).strip()
            break

        if not smiles:
            continue

        mol = Chem.MolFromSmiles(smiles)
        if mol:
            maccs_fp = MACCSkeys.GenMACCSKeys(mol)
            maccs_str = maccs_fp.ToBitString()
            g.add((chem_uri, hasMACCs, Literal(maccs_str)))
            added_maccs += 1

print(f"MACCS keys added for {added_maccs} chemical instances.")

# Save updated ontology
g.serialize("phytotherapies_COCONUT_CMAUP_MACCS.rdf", format="xml")
print("Updated ontology saved to phytotherapies_COCONUT_CMAUP_MACCS.rdf")


# Takes SMILES strings in my ontology run through drug central SQL and their respective 'target name' to be added as an instance in ontology under 'TargetedPathway'.

# In[57]:


# DrugCentral enrichment (force-load MACCS.rdf and enforce ScientificPaper is a subclass of ResearchConcept)
import re
import pandas as pd
import psycopg2
from rdkit import Chem
try:
    from rdkit.Chem import inchi as RDInchi
    _HAS_INCHI = True
except Exception:
    _HAS_INCHI = False
from tqdm import tqdm
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD

def uri_safe(s):
    s = re.sub(r'\W+', '_', str(s))
    s = re.sub(r'_+', '_', s)
    return s.strip('_')[:200] or "unknown"

def localname(u: URIRef) -> str:
    s = str(u); return s.rsplit('#',1)[-1].rsplit('/',1)[-1]

def find_class_by_label_or_local(g: Graph, names):
    names = list(names)
    # by rdfs:label
    for n in names:
        for s in g.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in g:
                return s
    # by local name
    for s in g.subjects(RDF.type, OWL.Class):
        if localname(s) in names:
            return s
    return None

# Load specified file (name might need to be changed based on prior step)
ONT_IN = "phytotherapies_COCONUT_CMAUP_MACCS.rdf"
if not Path(ONT_IN).exists():
    raise FileNotFoundError(f"{ONT_IN} not found in working directory.")
g = Graph(); g.parse(ONT_IN, format="xml")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Enforce: ScientificPaper is a subclass of ResearchConcept (+ hasPaper range)
RESEARCH_ROOT = find_class_by_label_or_local(g, ["ResearchConcept","Research Concept"])
SCIPAPER      = find_class_by_label_or_local(g, ["ScientificPaper","Paper"]) or NS.ScientificPaper

# Ensure the class exists
if (SCIPAPER, RDF.type, OWL.Class) not in g:
    g.add((SCIPAPER, RDF.type, OWL.Class))
    g.add((SCIPAPER, RDFS.label, Literal("ScientificPaper")))
# Ensure the subclass axiom if ResearchConcept is present
if RESEARCH_ROOT and (SCIPAPER, RDFS.subClassOf, RESEARCH_ROOT) not in g:
    g.add((SCIPAPER, RDFS.subClassOf, RESEARCH_ROOT))

# Ensure hasPaper object property and set its range to ScientificPaper
hasPaper = NS.hasPaper
if (hasPaper, RDF.type, OWL.ObjectProperty) not in g:
    g.add((hasPaper, RDF.type, OWL.ObjectProperty))
    g.add((hasPaper, RDFS.label, Literal("hasPaper")))
for o in list(g.objects(hasPaper, RDFS.range)):
    g.remove((hasPaper, RDFS.range, o))
g.add((hasPaper, RDFS.range, SCIPAPER))

# (Optional) quick verification prints
print("[TBox] ResearchConcept:", RESEARCH_ROOT)
print("[TBox] ScientificPaper:", SCIPAPER)
print("[TBox] hasPaper ranges:", list(g.objects(hasPaper, RDFS.range)))

# Ensure other schema we’ll use (add-only)
hasSMILES            = NS.hasSMILES
hasInChIKey          = NS.hasInChIKey
hasTherapeuticEffect = NS.hasTherapeuticEffect
targetsPathway       = NS.targetsPathway
hasValue             = NS.hasValue
TherapeuticEffectCls = NS.TherapeuticEffect
TargetedPathwayCls   = NS.TargetedPathway

for prop, ptype, lbl in [
    (hasSMILES,           OWL.DatatypeProperty, "hasSMILES"),
    (hasInChIKey,         OWL.DatatypeProperty, "hasInChIKey"),
    (hasTherapeuticEffect,OWL.ObjectProperty,   "hasTherapeuticEffect"),
    (targetsPathway,      OWL.ObjectProperty,   "targetsPathway"),
    (hasValue,            OWL.DatatypeProperty, "hasValue"),
]:
    if (prop, RDF.type, ptype) not in g:
        g.add((prop, RDF.type, ptype)); g.add((prop, RDFS.label, Literal(lbl)))

def class_exists(cls): return (cls, RDF.type, OWL.Class) in g

# SMILES → InChIKey, attach to chemicals
chemical_smiles = []
smiles_to_subject = {}
for subj, _, obj in g.triples((None, hasSMILES, None)):
    s = str(obj); chemical_smiles.append(s); smiles_to_subject[s] = subj

def smiles_to_inchikey(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None
    if _HAS_INCHI:
        try: return RDInchi.MolToInchiKey(mol)
        except Exception: return None
    return None

smiles_inchikey = {}
for s in tqdm(chemical_smiles, desc="SMILES → InChIKey"):
    ik = smiles_to_inchikey(s)
    if ik: smiles_inchikey[s] = ik

for smiles, subj in smiles_to_subject.items():
    ik = smiles_inchikey.get(smiles)
    if ik and (subj, hasInChIKey, Literal(ik)) not in g:
        g.add((subj, hasInChIKey, Literal(ik)))

# Build InChIKey → subject map
inchikey_to_subject = {str(obj): subj for subj, _, obj in g.triples((None, hasInChIKey, None))}
inchis = list(inchikey_to_subject.keys())

# DrugCentral queries
action_type_df = pd.DataFrame(); target_df = pd.DataFrame()
if inchis:
    try:
        with psycopg2.connect(
            host="unmtid-dbs.net", port=5433, dbname="drugcentral",
            user="drugman", password="dosage"
        ) as conn:
            action_type_query = """
                SELECT s.inchikey, atf.action_type
                FROM structures s
                JOIN act_table_full atf ON s.id = atf.struct_id
                WHERE s.inchikey = ANY(%s) AND atf.action_type IS NOT NULL
            """
            target_query = """
                SELECT s.inchikey, td.name AS target
                FROM structures s
                JOIN act_table_full atf ON s.id = atf.struct_id
                JOIN target_dictionary td ON atf.target_id = td.id
                WHERE s.inchikey = ANY(%s)
            """
            action_type_df = pd.read_sql(action_type_query, conn, params=(inchis,))
            target_df      = pd.read_sql(target_query, conn, params=(inchis,))
    except Exception as e:
        print(f"[WARN] DrugCentral query failed: {e}; continuing without DC enrichment.")

print(f"TherapeuticEffect/action_type rows: {len(action_type_df)}")
print(f"Target rows: {len(target_df)}")

# Mint/link TherapeuticEffect & TargetedPathway individuals
def effect_uri(label: str) -> URIRef:
    return NS[f"TherapeuticEffect_{uri_safe(label)}"]

def target_uri(label: str) -> URIRef:
    return NS[f"TargetedPathway_{uri_safe(label)}"]

effect_nodes = {}
target_nodes = {}

def ensure_effect(label: str) -> URIRef:
    if label in effect_nodes: return effect_nodes[label]
    uri = effect_uri(label)
    if not any(g.triples((uri, None, None))):
        g.add((uri, RDF.type, OWL.NamedIndividual))
        if class_exists(TherapeuticEffectCls): g.add((uri, RDF.type, TherapeuticEffectCls))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, hasValue, Literal(label, datatype=XSD.string)))
    effect_nodes[label] = uri
    return uri

def ensure_target(label: str) -> URIRef:
    if label in target_nodes: return target_nodes[label]
    uri = target_uri(label)
    if not any(g.triples((uri, None, None))):
        g.add((uri, RDF.type, OWL.NamedIndividual))
        if class_exists(TargetedPathwayCls): g.add((uri, RDF.type, TargetedPathwayCls))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, hasValue, Literal(label, datatype=XSD.string)))
    target_nodes[label] = uri
    return uri

linked_effects = linked_targets = 0

if not action_type_df.empty:
    for _, row in tqdm(action_type_df.iterrows(), total=len(action_type_df), desc="Linking action_type"):
        ik = row["inchikey"]; eff = str(row["action_type"]).strip()
        subj = inchikey_to_subject.get(ik)
        if not subj or not eff: continue
        e_uri = ensure_effect(eff)
        g.add((subj, hasTherapeuticEffect, e_uri)); linked_effects += 1

if not target_df.empty:
    for _, row in tqdm(target_df.iterrows(), total=len(target_df), desc="Linking targets"):
        ik = row["inchikey"]; tgt = str(row["target"]).strip()
        subj = inchikey_to_subject.get(ik)
        if not subj or not tgt: continue
        t_uri = ensure_target(tgt)
        g.add((subj, targetsPathway, t_uri)); linked_targets += 1

print(f"Linked Chemical→TherapeuticEffect: {linked_effects}")
print(f"Linked Chemical→TargetedPathway:   {linked_targets}")

# Save (don’t overwrite your base MACCS unless you want to, but I suggest against that)
ONT_OUT = "phytotherapies_COCONUT_CMAUP_MACCS_enriched.rdf"
g.serialize(ONT_OUT, format="xml")
print(f"Saved → {ONT_OUT} (ScientificPaper ⊑ ResearchConcept enforced)")


# Add ATC codes to drug central data in ontology

# In[61]:


import pandas as pd
import psycopg2
from rdflib import Graph, Namespace, Literal

# Load the ontology you want to enrich
g = Graph()
g.parse("phytotherapies_COCONUT_CMAUP_MACCS_enriched.rdf")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")
hasATC = NS.hasATC
hasTherapeuticEffect = NS.hasTherapeuticEffect
targetsPathway = NS.targetsPathway
hasInChIKey = NS.hasInChIKey

# Find chemicals with a therapeutic effect or targeted pathway
chem_with_moa_or_target = set()
for subj, pred, obj in g.triples((None, hasTherapeuticEffect, None)):
    chem_with_moa_or_target.add(subj)
for subj, pred, obj in g.triples((None, targetsPathway, None)):
    chem_with_moa_or_target.add(subj)

# Get their InChIKeys
inchikeys_to_query = []
for subj in chem_with_moa_or_target:
    for s, p, o in g.triples((subj, hasInChIKey, None)):
        inchikeys_to_query.append(str(o))
inchikeys_to_query = list(set(inchikeys_to_query))

# Query DrugCentral for ATC codes
with psycopg2.connect(
    host="unmtid-dbs.net",
    port=5433,
    dbname="drugcentral",
    user="drugman",
    password="dosage"
) as conn:
    atc_query = """
        SELECT s.inchikey, a.code AS atc_code
        FROM structures s
        JOIN struct2atc s2a ON s.id = s2a.struct_id
        JOIN atc a ON s2a.atc_code = a.code
        WHERE s.inchikey = ANY(%s)
    """
    atc_df = pd.read_sql(atc_query, conn, params=(inchikeys_to_query,))

# Map InChIKey to ontology subject
inchikey_to_subject = {}
for subj, pred, obj in g.triples((None, hasInChIKey, None)):
    inchikey_to_subject[str(obj)] = subj

# Add ATC code(s) as data property
for idx, row in atc_df.iterrows():
    ikey = row['inchikey']
    atc = row['atc_code']
    subj = inchikey_to_subject.get(ikey)
    if subj and atc:
        g.add((subj, hasATC, Literal(atc)))

# Save ontology
g.serialize(destination="phytotherapies_enriched_with_actiontype_targets_ATC.rdf", format="xml")
print("Ontology with ATC codes saved to phytotherapies_enriched_with_actiontype_targets_ATC.rdf")


# ## Adding more mechanisms of action from ChEMBL data

# Download .csv file from ChEMBL Drug Mechanisms page (https://www.ebi.ac.uk/chembl/explore/drug_mechanisms/), use it to find mechanism of action for more compounds in ontology.

# In[63]:


from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF
import pandas as pd
import psycopg2
from rdkit import Chem
from tqdm import tqdm


# In[70]:


df = pd.read_csv("ChEMBL_drug_mechanisms.csv", sep=';')

print(df.head(5))


# **Adding instances of TargetedPathway and TherapeuticEffect**

# In[72]:


# Classify chemicals into subclasses, ensure no root-only instances, and save
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdkit import Chem
from rdkit.Chem import Descriptors
from collections import defaultdict

# input/output
ONT_IN  = "phytotherapies_enriched_with_actiontype_targets_ATC.rdf"
ONT_OUT = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_typed_clean.rdf"

# Behavior flags
MULTI_LABEL         = True   # allow multiple subclass types per chemical
FALLBACK_TO_UNKNOWN = True   # if no rule matches, assign NS.Unknown (must exist as owl:Class)
DROP_ASSERTED_ROOT  = True   # remove (s, rdf:type, ChemicalConcept) when a subclass is present
TAG_ROOT_BASELINE   = False  # set True only if you WANT to keep a baseline root type (will be removed anyway if DROP_ASSERTED_ROOT=True)

g = Graph(); g.parse(ONT_IN, format="xml")
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

hasSMILES       = NS.hasSMILES
CHEM_ROOT       = NS.ChemicalConcept

# Mapping (exact URIs)
phytochemical_classes = {
    "Carotenoid":     NS.Carotenoid,
    "DietaryFiber":   NS.DietaryFiber,
    "Isoprenoid":     NS.Isoprenoid,
    "Phytosterol":    NS.Phytosterol,
    "Polyphenol":     NS.Polyphenol,
    "Polysaccharide": NS.Polysaccharide,
    "Saponin":        NS.Saponin,
    "Unknown":        NS.Unknown,  # used only if this class exists
}

def class_exists(u: URIRef) -> bool:
    return (u, RDF.type, OWL.Class) in g

AVAILABLE = {k: u for k, u in phytochemical_classes.items() if u and class_exists(u)}
UNKNOWN_EXISTS = ("Unknown" in AVAILABLE)

# SMILES classifier (unchanged)
def classify_smiles(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ["Unknown"]
    classes = []
    mw = Descriptors.MolWt(mol)
    num_rings = Descriptors.RingCount(mol)
    num_oh = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[OH]")))
    num_c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    num_o = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")
    num_double_bonds = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C=C")))
    if num_rings >= 2 and num_oh >= 2: classes.append("Polyphenol")
    if num_c >= 30 and num_double_bonds >= 5: classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1: classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5: classes.append("Saponin")
    if mw > 500 and num_o > 10: classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15: classes.append("DietaryFiber")
    if "C=C" in smiles and num_c % 5 == 0: classes.append("Isoprenoid")
    return classes if classes else ["Unknown"]

# Candidate chemicals
chemicals = set(s for s,_,_ in g.triples((None, hasSMILES, None)))
chemicals |= set(s for s,_,_ in g.triples((None, RDF.type, CHEM_ROOT)))

# Optionally tag root baseline (often not needed if you’re removing it later)
root_tagged = 0
if TAG_ROOT_BASELINE and class_exists(CHEM_ROOT):
    for s in list(chemicals):
        if (s, RDF.type, CHEM_ROOT) not in g:
            g.add((s, RDF.type, CHEM_ROOT)); root_tagged += 1

typed_counts = defaultdict(int)
no_subclass_before = 0

def has_any_subclass(s):
    # considers only classes declared as owl:Class and that are subclasses of CHEM_ROOT
    for _,_,cls in g.triples((s, RDF.type, None)):
        if cls != CHEM_ROOT and (cls, RDFS.subClassOf, CHEM_ROOT) in g and (cls, RDF.type, OWL.Class) in g:
            return True
    return False

for subj in chemicals:
    had_sub = has_any_subclass(subj)
    if not had_sub:
        no_subclass_before += 1
        smiles = next((str(o) for _,_,o in g.triples((subj, hasSMILES, None))), "").strip()
        labels = classify_smiles(smiles) if smiles else ["Unknown"]

        added_any = False
        if MULTI_LABEL:
            for lbl in labels:
                cls = AVAILABLE.get(lbl)
                if cls and (subj, RDF.type, cls) not in g:
                    g.add((subj, RDF.type, cls)); typed_counts[lbl] += 1; added_any = True
        else:
            # single best label: first available in this order
            for lbl in ["Polyphenol","Carotenoid","Phytosterol","Saponin","Polysaccharide","DietaryFiber","Isoprenoid","Unknown"]:
                if lbl in labels and lbl in AVAILABLE:
                    cls = AVAILABLE[lbl]
                    if (subj, RDF.type, cls) not in g:
                        g.add((subj, RDF.type, cls)); typed_counts[lbl] += 1
                    added_any = True
                    break

        # Fallback to Unknown if still none and allowed
        if not added_any and FALLBACK_TO_UNKNOWN and UNKNOWN_EXISTS:
            cls = AVAILABLE["Unknown"]
            if (subj, RDF.type, cls) not in g:
                g.add((subj, RDF.type, cls)); typed_counts["Unknown"] += 1

# Remove asserted root type where a subclass exists
removed_root = 0
if DROP_ASSERTED_ROOT and class_exists(CHEM_ROOT):
    for s in chemicals:
        if (s, RDF.type, CHEM_ROOT) in g and has_any_subclass(s):
            g.remove((s, RDF.type, CHEM_ROOT)); removed_root += 1

# Remaining root-only (should be 0 if Unknown exists) 
root_only = 0
if class_exists(CHEM_ROOT):
    for s in chemicals:
        if (s, RDF.type, CHEM_ROOT) in g and not has_any_subclass(s):
            root_only += 1

# Report & save
print(f"Chemicals considered: {len(chemicals)}")
print(f"Originally with NO subclass: {no_subclass_before}")
if TAG_ROOT_BASELINE:
    print(f"Baseline rdf:type ChemicalConcept added: {root_tagged}")
if typed_counts:
    print("Subclass typings added:")
    for k in ["Polyphenol","Carotenoid","Phytosterol","Saponin","Polysaccharide","DietaryFiber","Isoprenoid","Unknown"]:
        if typed_counts[k]:
            print(f"  {k:14} {typed_counts[k]}")
if DROP_ASSERTED_ROOT:
    print(f"Removed asserted rdf:type ChemicalConcept: {removed_root}")
print(f"Remaining root-only chemicals: {root_only}")

g.serialize(ONT_OUT, format="xml")
print(f"Saved → {ONT_OUT}")


# In[78]:


# Classify chemicals into subclasses, ensure no root-only instances, then build SMILES map + CSV matches
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.rdmolops import GetMolFrags
from collections import defaultdict
import pandas as pd
import re

ONT_IN   = "phytotherapies_enriched_with_actiontype_targets_ATC.rdf"
ONT_OUT  = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_typed_clean.rdf"
CSV_PATH = "ChEMBL_drug_mechanisms.csv"

# Behavior flags for typing
MULTI_LABEL         = True
FALLBACK_TO_UNKNOWN = True
DROP_ASSERTED_ROOT  = True
TAG_ROOT_BASELINE   = False

g = Graph(); g.parse(ONT_IN, format="xml")
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

hasSMILES  = NS.hasSMILES
CHEM_ROOT  = NS.ChemicalConcept

# Exact subclass URIs that already exist in the ontology
phytochemical_classes = {
    "Carotenoid":     NS.Carotenoid,
    "DietaryFiber":   NS.DietaryFiber,
    "Isoprenoid":     NS.Isoprenoid,
    "Phytosterol":    NS.Phytosterol,
    "Polyphenol":     NS.Polyphenol,
    "Polysaccharide": NS.Polysaccharide,
    "Saponin":        NS.Saponin,
    "Unknown":        NS.Unknown,  # used only if present
}
def class_exists(u: URIRef) -> bool:
    return (u, RDF.type, OWL.Class) in g
AVAILABLE = {k: u for k, u in phytochemical_classes.items() if u and class_exists(u)}
UNKNOWN_EXISTS = ("Unknown" in AVAILABLE)

# SMILES classifier (unchanged)
def classify_smiles(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ["Unknown"]
    classes = []
    mw = Descriptors.MolWt(mol)
    num_rings = Descriptors.RingCount(mol)
    num_oh = len(mol.GetSubstructMatches(Chem.MolFromSmarts("[OH]")))
    num_c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    num_o = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")
    num_double_bonds = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C=C")))
    if num_rings >= 2 and num_oh >= 2: classes.append("Polyphenol")
    if num_c >= 30 and num_double_bonds >= 5: classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1: classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5: classes.append("Saponin")
    if mw > 500 and num_o > 10: classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15: classes.append("DietaryFiber")
    if "C=C" in smiles and num_c % 5 == 0: classes.append("Isoprenoid")
    return classes if classes else ["Unknown"]

# Classify & ensure no root-only chemicals
chemicals = set(s for s,_,_ in g.triples((None, hasSMILES, None)))
chemicals |= set(s for s,_,_ in g.triples((None, RDF.type, CHEM_ROOT)))

root_tagged = 0
if TAG_ROOT_BASELINE and class_exists(CHEM_ROOT):
    for s in list(chemicals):
        if (s, RDF.type, CHEM_ROOT) not in g:
            g.add((s, RDF.type, CHEM_ROOT)); root_tagged += 1

typed_counts = defaultdict(int)
no_subclass_before = 0

def is_sub_of(cls, root):
    return (cls, RDFS.subClassOf, root) in g

def has_any_subclass(s):
    for _,_,cls in g.triples((s, RDF.type, None)):
        if cls != CHEM_ROOT and (cls, RDF.type, OWL.Class) in g and is_sub_of(cls, CHEM_ROOT):
            return True
    return False

for subj in chemicals:
    if not has_any_subclass(subj):
        no_subclass_before += 1
        smi = next((str(o) for _,_,o in g.triples((subj, hasSMILES, None))), "").strip()
        labels = classify_smiles(smi) if smi else ["Unknown"]
        added_any = False

        if MULTI_LABEL:
            for lbl in labels:
                cls = AVAILABLE.get(lbl)
                if cls and (subj, RDF.type, cls) not in g:
                    g.add((subj, RDF.type, cls)); typed_counts[lbl] += 1; added_any = True
        else:
            for lbl in ["Polyphenol","Carotenoid","Phytosterol","Saponin","Polysaccharide","DietaryFiber","Isoprenoid","Unknown"]:
                if lbl in labels and lbl in AVAILABLE:
                    cls = AVAILABLE[lbl]
                    if (subj, RDF.type, cls) not in g:
                        g.add((subj, RDF.type, cls)); typed_counts[lbl] += 1
                    added_any = True
                    break

        if not added_any and FALLBACK_TO_UNKNOWN and UNKNOWN_EXISTS:
            cls = AVAILABLE["Unknown"]
            if (subj, RDF.type, cls) not in g:
                g.add((subj, RDF.type, cls)); typed_counts["Unknown"] += 1

removed_root = 0
if DROP_ASSERTED_ROOT and class_exists(CHEM_ROOT):
    for s in chemicals:
        if (s, RDF.type, CHEM_ROOT) in g and has_any_subclass(s):
            g.remove((s, RDF.type, CHEM_ROOT)); removed_root += 1

root_only = 0
if class_exists(CHEM_ROOT):
    for s in chemicals:
        if (s, RDF.type, CHEM_ROOT) in g and not has_any_subclass(s):
            root_only += 1

print(f"Chemicals considered: {len(chemicals)}")
print(f"Originally with NO subclass: {no_subclass_before}")
if TAG_ROOT_BASELINE: print(f"Baseline rdf:type ChemicalConcept added: {root_tagged}")
if typed_counts:
    print("Subclass typings added:")
    for k in ["Polyphenol","Carotenoid","Phytosterol","Saponin","Polysaccharide","DietaryFiber","Isoprenoid","Unknown"]:
        if typed_counts[k]:
            print(f"  {k:14} {typed_counts[k]}")
if DROP_ASSERTED_ROOT:
    print(f"Removed asserted rdf:type ChemicalConcept: {removed_root}")
print(f"Remaining root-only chemicals: {root_only}")

# Save the typed graph (and keep it in memory for the mapping below)
g.serialize(ONT_OUT, format="xml")
print(f"Saved → {ONT_OUT}")

# Build SMILES→subject map (restricted to ChemicalConcept tree)
def subclass_closure(graph, root):
    out = set([root])
    stack = [root]
    while stack:
        c = stack.pop()
        for sub in graph.subjects(RDFS.subClassOf, c):
            if (sub, RDF.type, OWL.Class) in graph and sub not in out:
                out.add(sub); stack.append(sub)
    return out

chemicalconcept_smiles_to_subject = {}
chem_classes = subclass_closure(g, CHEM_ROOT) if class_exists(CHEM_ROOT) else set()
chem_subjects = set()
for cls in chem_classes:
    for s in g.subjects(RDF.type, cls):
        chem_subjects.add(s)
for s in chem_subjects:
    for _, _, smi in g.triples((s, hasSMILES, None)):
        if isinstance(smi, Literal) and str(smi).strip():
            chemicalconcept_smiles_to_subject[str(smi)] = s

# Load ChEMBL CSV and canonicalize/match
# detect SMILES column
df = pd.read_csv(CSV_PATH, sep=";").fillna("")
smiles_col = next((c for c in ["Smiles","SMILES","Canonical_smiles","CANONICAL_SMILES","smiles"] if c in df.columns), None)
if not smiles_col:
    raise KeyError("No SMILES column in CSV (looked for Smiles/SMILES/Canonical_smiles/CANONICAL_SMILES/smiles)")

def canon_smiles(smi, isomeric=True):
    if not smi or str(smi).strip().lower() in {"na","n/a","n.a.","none"}:
        return None
    smi = str(smi).strip()
    mol = Chem.MolFromSmiles(smi)
    if not mol:
        return None
    # If multi-component, keep largest fragment
    if "." in smi:
        frags = GetMolFrags(mol, asMols=True, sanitizeFrags=True)
        if frags:
            mol = max(frags, key=lambda m: m.GetNumHeavyAtoms())
    try:
        return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=isomeric)
    except Exception:
        return None

def to_inchikey_from_smiles(smi):
    if not smi: return None
    mol = Chem.MolFromSmiles(smi)
    if not mol: return None
    try:
        return Chem.MolToInchiKey(mol)
    except Exception:
        return None

# Ontology canonical + IK maps
onto_can_to_subj = {}
onto_ik_to_subj  = {}
for raw, subj in chemicalconcept_smiles_to_subject.items():
    can = canon_smiles(raw)
    if can:
        onto_can_to_subj.setdefault(can, subj)
        ik = to_inchikey_from_smiles(can)
        if ik:
            onto_ik_to_subj.setdefault(ik, subj)

# CSV canonicalization & matching
df["_SMI_CAN"] = df[smiles_col].astype(str).map(canon_smiles)
row_to_subject = {}
unmatched = []

# pass 1: by canonical SMILES
for i, can in df["_SMI_CAN"].items():
    if can and can in onto_can_to_subj:
        row_to_subject[i] = onto_can_to_subj[can]
    else:
        unmatched.append(i)

# pass 2: fallback by InChIKey
if unmatched:
    df.loc[unmatched, "_IK"] = df.loc[unmatched, "_SMI_CAN"].map(to_inchikey_from_smiles)
    still = []
    for i in unmatched:
        ik = df.at[i, "_IK"] if "_IK" in df.columns else None
        subj = onto_ik_to_subj.get(ik) if ik else None
        if subj is not None:
            row_to_subject[i] = subj
        else:
            still.append(i)
    unmatched = still

# Diagnostics and summary
print("Ontology SMILES examples:", list(chemicalconcept_smiles_to_subject.keys())[:5])
print("ChEMBL CSV SMILES examples:", df[smiles_col].astype(str).unique()[:5])

onto_set = set(onto_can_to_subj.keys())
csv_set  = set(df["_SMI_CAN"].dropna())
print("\n=== Matching summary ===")
print(f"CSV rows: {len(df)} | With canonical SMILES: {len(csv_set)}")
print(f"Canonical overlap (CSV ∩ Ontology): {len(csv_set & onto_set)}")
print(f"Rows mapped to ontology subject: {len(row_to_subject)}")
if unmatched[:8]:
    print("\nExamples of CSV rows that didn't match any ontology subject:")
    for i in unmatched[:8]:
        print(" - raw:", df.at[i, smiles_col], "| canonical:", df.at[i, "_SMI_CAN"], "| IK:", (df.at[i, "_IK"] if "_IK" in df.columns else None))


# In[80]:


print("Ontology SMILES examples:", list(chemicalconcept_smiles_to_subject.keys())[:5])
print("ChEMBL CSV SMILES examples:", df['Smiles'].unique()[:5])


# In[82]:


# Use 'Pathway' (under HumanConcept) for targets instead of creating TargetedPathway
import pandas as pd
import re
from pathlib import Path
from collections import defaultdict

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD
from rdkit import Chem

IN_RDF   = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_typed_clean.rdf"
MECH_CSV = "ChEMBL_drug_mechanisms.csv"
OUT_RDF  = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_PATHWAY.rdf"

# Helpers
def uri_safe(s: str) -> str:
    s = re.sub(r"\W+", "_", str(s))
    s = re.sub(r"_+", "_", s)
    return s.strip("_")[:200] or "unknown"

def canon_smiles(smiles: str) -> str:
    s = (smiles or "").strip()
    if not s: return ""
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m, canonical=True) if m else ""

def find_class_by_label_or_local(g: Graph, names):
    names = list(names)
    # rdfs:label
    for n in names:
        for s in g.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in g:
                return s
    # local name
    for s in g.subjects(RDF.type, OWL.Class):
        local = str(s).split("#")[-1].split("/")[-1]
        if local in names:
            return s
    return None

g = Graph(); g.parse(IN_RDF, format="xml")
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Terms (must already exist as classes/properties in ontology)
hasSMILES            = NS.hasSMILES
targetsPathway       = NS.targetsPathway
hasTherapeuticEffect = NS.hasTherapeuticEffect
hasValue             = NS.hasValue  # safe if absent; we'll add as DatatypeProperty if needed
TherapeuticEffect    = find_class_by_label_or_local(g, ["TherapeuticEffect"]) or NS.TherapeuticEffect

# Find the *existing* Pathway class under HumanConcept
PATHWAY_CLASS = find_class_by_label_or_local(g, ["Pathway"])
if PATHWAY_CLASS is None or (PATHWAY_CLASS, RDF.type, OWL.Class) not in g:
    raise RuntimeError("Could not find existing 'Pathway' owl:Class in the ontology.")

# (Optional sanity) locate HumanConcept (not required to proceed)
HUMAN_CONCEPT = find_class_by_label_or_local(g, ["HumanConcept","Human Concept"])

# Ensure properties exist (ADD-ONLY)
if (targetsPathway, RDF.type, OWL.ObjectProperty) not in g:
    g.add((targetsPathway, RDF.type, OWL.ObjectProperty)); g.add((targetsPathway, RDFS.label, Literal("targetsPathway")))
if (hasTherapeuticEffect, RDF.type, OWL.ObjectProperty) not in g:
    g.add((hasTherapeuticEffect, RDF.type, OWL.ObjectProperty)); g.add((hasTherapeuticEffect, RDFS.label, Literal("hasTherapeuticEffect")))
if (hasValue, RDF.type, OWL.DatatypeProperty) not in g:
    g.add((hasValue, RDF.type, OWL.DatatypeProperty)); g.add((hasValue, RDFS.label, Literal("hasValue")))

# Set range of targetsPathway to Pathway (replace any previous range)
for old in list(g.objects(targetsPathway, RDFS.range)):
    g.remove((targetsPathway, RDFS.range, old))
g.add((targetsPathway, RDFS.range, PATHWAY_CLASS))

# Migrate any previously minted TargetedPathway individuals to Pathway
TARGETED_PATHWAY_CLASS = URIRef(str(NS) + "TargetedPathway")
migrated = 0
if (TARGETED_PATHWAY_CLASS, RDF.type, OWL.Class) in g:
    for s in list(g.subjects(RDF.type, TARGETED_PATHWAY_CLASS)):
        g.remove((s, RDF.type, TARGETED_PATHWAY_CLASS))
        if (s, RDF.type, PATHWAY_CLASS) not in g:
            g.add((s, RDF.type, PATHWAY_CLASS)); migrated += 1
    # Do NOT delete the class itself; harmless to keep. Comment next line to preserve entirely.
    # g.remove((TARGETED_PATHWAY_CLASS, RDF.type, OWL.Class))

# Build SMILES → subjects from ontology (canonicalized)
smiles_to_subjects = defaultdict(set)
for subj, _, lit in g.triples((None, hasSMILES, None)):
    can = canon_smiles(str(lit))
    if can:
        smiles_to_subjects[can].add(subj)

# Read mechanisms CSV
if not Path(MECH_CSV).exists():
    raise FileNotFoundError(f"{MECH_CSV} not found")

def read_mech_csv(path):
    try:
        df = pd.read_csv(path, sep=";")
        if df.shape[1] == 1:  # wrong sep → try comma
            df = pd.read_csv(path)
    except Exception:
        df = pd.read_csv(path)
    return df

df = read_mech_csv(MECH_CSV).fillna("")
# choose columns
def pick(df, cands):
    for c in cands:
        if c in df.columns: return c
    return None

COL_SMILES = pick(df, ["Smiles","SMILES","smiles","Canonical_smiles"])
COL_TNAME  = pick(df, ["Target Name","TargetName","Target"])
COL_ATYPE  = pick(df, ["Action Type","ActionType","Action"])
if not COL_SMILES:
    raise KeyError("No SMILES column found in mechanisms CSV (Smiles/SMILES/smiles/Canonical_smiles).")

# canonicalize CSV SMILES
df[COL_SMILES] = df[COL_SMILES].astype(str).map(canon_smiles)

# Dedup caches by rdfs:label
def find_individual_by_label(cls: URIRef, label: str):
    for s in g.subjects(RDFS.label, Literal(label)):
        if (s, RDF.type, cls) in g:
            return s
    return None

pathway_cache = {}
effect_cache  = {}

def ensure_pathway(label: str) -> URIRef:
    if not label: return None
    if label in pathway_cache: return pathway_cache[label]
    s = find_individual_by_label(PATHWAY_CLASS, label)
    if s is None:
        s = NS[f"Pathway_{uri_safe(label)}"]
        if not any(g.triples((s, None, None))):
            g.add((s, RDF.type, OWL.NamedIndividual))
            g.add((s, RDF.type, PATHWAY_CLASS))
            g.add((s, RDFS.label, Literal(label)))
            g.add((s, hasValue, Literal(label)))
    pathway_cache[label] = s
    return s

def ensure_effect(label: str) -> URIRef:
    if not label: return None
    if (TherapeuticEffect, RDF.type, OWL.Class) not in g:
        # if TherapeuticEffect class is missing, create it add-only (safe)
        g.add((TherapeuticEffect, RDF.type, OWL.Class)); g.add((TherapeuticEffect, RDFS.label, Literal("TherapeuticEffect")))
    if label in effect_cache: return effect_cache[label]
    s = find_individual_by_label(TherapeuticEffect, label)
    if s is None:
        s = NS[f"TherapeuticEffect_{uri_safe(label)}"]
        if not any(g.triples((s, None, None))):
            g.add((s, RDF.type, OWL.NamedIndividual))
            g.add((s, RDF.type, TherapeuticEffect))
            g.add((s, RDFS.label, Literal(label)))
            g.add((s, hasValue, Literal(label)))
    effect_cache[label] = s
    return s

# Link chemicals to Pathway/TherapeuticEffect
links_tp = links_te = 0
created_pw = created_te = 0

for _, row in df.iterrows():
    smi = row[COL_SMILES]
    if not smi: 
        continue
    subjects = smiles_to_subjects.get(smi)
    if not subjects:
        continue

    if COL_TNAME:
        tname = str(row[COL_TNAME]).strip()
        if tname and tname.lower() != "nan":
            pw = ensure_pathway(tname)
            for s in subjects:
                if (s, targetsPathway, pw) not in g:
                    g.add((s, targetsPathway, pw)); links_tp += 1

    if COL_ATYPE:
        aname = str(row[COL_ATYPE]).strip()
        if aname and aname.lower() != "nan":
            te = ensure_effect(aname)
            for s in subjects:
                if (s, hasTherapeuticEffect, te) not in g:
                    g.add((s, hasTherapeuticEffect, te)); links_te += 1

print(f"Retyped TargetedPathway → Pathway individuals: {migrated}")
print(f"Linked targetsPathway edges: {links_tp}")
print(f"Linked hasTherapeuticEffect edges: {links_te}")
print(f"Unique Pathway nodes cached this run: {len(pathway_cache)}")
print(f"Unique TherapeuticEffect nodes cached this run: {len(effect_cache)}")

g.serialize(OUT_RDF, format="xml")
print(f"Saved → {OUT_RDF}")


# Adding ATC codes to ChEMBL-enriched data

# In[84]:


from rdflib import Graph, Namespace, Literal

# 1. Load ontology (update filename as needed)
g = Graph()
g.parse("phytotherapies_final_enriched_with_ChEMBL_mechanisms_PATHWAY.rdf")

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")
hasInChIKey = NS.hasInChIKey
hasATC = NS.hasATC
targetsPathway = NS.targetsPathway
hasTherapeuticEffect = NS.hasTherapeuticEffect

# 2. Get subjects enriched with ChEMBL
enriched_subjects = set()
for s, p, o in g.triples((None, targetsPathway, None)):
    enriched_subjects.add(s)
for s, p, o in g.triples((None, hasTherapeuticEffect, None)):
    enriched_subjects.add(s)

# 3. Map those subjects to their InChIKeys
enriched_subjects_inchikeys = {}
for s in enriched_subjects:
    for _, _, o in g.triples((s, hasInChIKey, None)):
        enriched_subjects_inchikeys[s] = str(o)

# 4. Build InChIKey → subject map for enrichment
inchikey_to_enriched_subject = {v: k for k, v in enriched_subjects_inchikeys.items()}

# 5. Add ATC codes **only to ChEMBL-enriched subjects**
added = 0
for idx, row in atc_df.iterrows():
    subj = inchikey_to_enriched_subject.get(row['inchikey'])
    if subj and row['atc_code']:
        g.add((subj, hasATC, Literal(row['atc_code'])))
        added += 1

print(f"Added {added} hasATC data properties (ChEMBL-enriched only).")

# 6. Save result
g.serialize(destination="phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered.rdf", format="xml")
print("Saved ontology with filtered ATC codes.")


# Creating a dataframe from Drug Central including target names, action types, Smiles, and ATC codes for basic ML, binding, and prediction:

# In[85]:


import psycopg2
import pandas as pd

# Connect to the DrugCentral database
conn = psycopg2.connect(
    host="unmtid-dbs.net",
    port=5433,
    dbname="drugcentral",
    user="drugman",
    password="dosage"
)

# Define the SQL query to join and select all relevant data (no LIMIT)
query = """
SELECT a.target_name, a.action_type, p.smiles, s2a.atc_code
FROM act_table_full a
JOIN parentmol p ON a.struct_id = p.cd_id
LEFT JOIN struct2atc s2a ON a.struct_id = s2a.struct_id
"""

# Read all results into a DataFrame
Drug_Central_data = pd.read_sql(query, conn)

# Optionally, drop duplicate rows if needed:
# Drug_Central_data = Drug_Central_data.drop_duplicates()

# Save DataFrame to CSV
Drug_Central_data.to_csv("Drug_Central_data.csv", index=False)

# Show the first few rows to confirm
print(Drug_Central_data.head())

# Close the connection
conn.close()


# In[88]:


# Persist canonical SMILES and inverse plant->chemical edges into the ontology (add-only)
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdkit import Chem

IN_RDF  = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered.rdf"
OUT_RDF = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched.rdf"

g = Graph(); g.parse(IN_RDF, format="xml")
NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

# Properties/classes we use
isDerivedFrom        = NS.isDerivedFrom
hasCompound          = NS.hasCompound
hasSMILES            = NS.hasSMILES
hasCanonicalSMILES   = NS.hasCanonicalSMILES
hasGenus             = NS.hasGenus
hasSpecies           = NS.hasSpecies

# Ensure properties exist (add-only)
if (hasCompound, RDF.type, OWL.ObjectProperty) not in g:
    g.add((hasCompound, RDF.type, OWL.ObjectProperty)); g.add((hasCompound, RDFS.label, Literal("hasCompound")))
if (hasCanonicalSMILES, RDF.type, OWL.DatatypeProperty) not in g:
    g.add((hasCanonicalSMILES, RDF.type, OWL.DatatypeProperty)); g.add((hasCanonicalSMILES, RDFS.label, Literal("hasCanonicalSMILES")))

def canon_smiles(s: str) -> str:
    s = (s or "").strip()
    if not s: return ""
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m, canonical=True) if m else ""

def ensure_plant_label(p):
    if any(True for _ in g.triples((p, RDFS.label, None))):
        return
    genus   = next((str(o).strip() for _,_,o in g.triples((p, hasGenus, None)) if str(o).strip()), "")
    species = next((str(o).strip() for _,_,o in g.triples((p, hasSpecies, None)) if str(o).strip()), "")
    lab = (genus + " " + species).strip()
    if lab:
        g.add((p, RDFS.label, Literal(lab)))

added_inv = added_cansmi = added_labels = 0

for chem, _, plant in g.triples((None, isDerivedFrom, None)):
    # inverse edge: plant --hasCompound--> chem
    if (plant, hasCompound, chem) not in g:
        g.add((plant, hasCompound, chem)); added_inv += 1

    # canonical SMILES data
    for _, _, smi in g.triples((chem, hasSMILES, None)):
        can = canon_smiles(str(smi))
        if can and (chem, hasCanonicalSMILES, Literal(can)) not in g:
            g.add((chem, hasCanonicalSMILES, Literal(can))); added_cansmi += 1

    # ensure plant label exists
    before = any(True for _ in g.triples((plant, RDFS.label, None)))
    ensure_plant_label(plant)
    after = any(True for _ in g.triples((plant, RDFS.label, None)))
    if (not before) and after:
        added_labels += 1

print(f"Added inverse hasCompound edges: {added_inv}")
print(f"Added hasCanonicalSMILES literals: {added_cansmi}")
print(f"Plants newly given rdfs:label: {added_labels}")

g.serialize(OUT_RDF, format="xml")
print(f"Saved → {OUT_RDF}")


# ### Adding unstructured data from papers

# See notebook Scientific_Paper_data for how this data was extracted

# In[91]:


#Fix: scientific paper becomes own subclass, bring it under ResearchConcept


# In[92]:


# Fix mis-typed SMILES-as-Plant individuals (add chemical types; optionally remove Plant type)
# Input : phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched.rdf
# Output: *_plants_smiles_fixed.rdf

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal
from rdkit import Chem
from rdkit.Chem import Descriptors
from collections import deque

ONT_IN  = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched.rdf"
ONT_OUT = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched_plants_smiles_fixed.rdf"

REMOVE_PLANT_TYPE = True   # set False to keep Plant typing
TAG_CHEM_ROOT     = True   # also add rdf:type ChemicalConcept

# Helpers
def default_ns(graph):
    for pref, ns in graph.namespaces():
        if pref in ("", None):
            return Namespace(str(ns))
    return Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

def find_class_by_label_or_local(g, names):
    names = set(names)
    for n in names:
        for s in g.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in g:
                return s
    for s in g.subjects(RDF.type, OWL.Class):
        local = str(s).rsplit("#",1)[-1].rsplit("/",1)[-1]
        if local in names:
            return s
    return None

def subclass_closure(g, root):
    out = set(); q = deque([root])
    while q:
        r = q.popleft()
        for c in g.subjects(RDFS.subClassOf, r):
            if (c, RDF.type, OWL.Class) in g and c not in out:
                out.add(c); q.append(c)
    return out

# SMILES classifier rules
def classify_smiles(smiles: str):
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
    if num_rings >= 2 and num_oh >= 2: classes.append("Polyphenol")
    if num_c >= 30 and num_double >= 5: classes.append("Carotenoid")
    if num_rings >= 4 and num_oh >= 1: classes.append("Phytosterol")
    if num_c >= 40 and num_o >= 5: classes.append("Saponin")
    if mw > 500 and num_o > 10: classes.append("Polysaccharide")
    if num_c > 20 and num_o > 15: classes.append("DietaryFiber")
    if "C=C" in smiles and num_c % 5 == 0: classes.append("Isoprenoid")
    return classes or ["Unknown"]

# Load graph
g = Graph(); g.parse(ONT_IN, format="xml")
NS = default_ns(g)

# Key terms
hasSMILES        = NS.hasSMILES
Plant            = find_class_by_label_or_local(g, ["Plant"]) or NS.Plant
ChemicalConcept  = find_class_by_label_or_local(g, ["ChemicalConcept","Chemical Concept","ChemicalEntity","Chemical Entity"]) or NS.ChemicalConcept

# Target subclasses (must already exist as classes in ontology)
label_to_class = {
    "Carotenoid":     getattr(NS, "Carotenoid", None),
    "DietaryFiber":   getattr(NS, "DietaryFiber", None),
    "Isoprenoid":     getattr(NS, "Isoprenoid", None),
    "Phytosterol":    getattr(NS, "Phytosterol", None),
    "Polyphenol":     getattr(NS, "Polyphenol", None),
    "Polysaccharide": getattr(NS, "Polysaccharide", None),
    "Saponin":        getattr(NS, "Saponin", None),
    "Unknown":        getattr(NS, "Unknown", None),  # optional, if present
}
label_to_class = {k:v for k,v in label_to_class.items() if v and (v, RDF.type, OWL.Class) in g}

# Plant family: Plant + subclasses
plant_family = {Plant} | subclass_closure(g, Plant)

# Find mis-typed individuals: have SMILES and are typed as Plant/Plant-subclass
mistyped = set()
for subj, _, smi in g.triples((None, hasSMILES, None)):
    if any((subj, RDF.type, pc) in g for pc in plant_family):
        mistyped.add((subj, str(smi)))

print(f"Found {len(mistyped)} individuals with hasSMILES typed as Plant/Plant-subclass.")

retagged = 0
removed_plant_types = 0
root_tagged = 0
subclass_counts = {k:0 for k in label_to_class.keys()}

for subj, smi in mistyped:
    # Baseline ChemicalConcept (optional)
    if TAG_CHEM_ROOT and (ChemicalConcept, RDF.type, OWL.Class) in g and (subj, RDF.type, ChemicalConcept) not in g:
        g.add((subj, RDF.type, ChemicalConcept)); root_tagged += 1

    # Add subclass types from classifier
    for lbl in classify_smiles(smi):
        cls = label_to_class.get(lbl)
        if cls and (subj, RDF.type, cls) not in g:
            g.add((subj, RDF.type, cls))
            subclass_counts[lbl] += 1

    # Remove wrong Plant typing (optional)
    if REMOVE_PLANT_TYPE:
        for pc in list(plant_family):
            if (subj, RDF.type, pc) in g:
                g.remove((subj, RDF.type, pc))
                removed_plant_types += 1

    retagged += 1

# Save
g.serialize(ONT_OUT, format="xml")

# Report
print(f"Retagged individuals: {retagged}")
print(f"Removed Plant-type assertions: {removed_plant_types} (toggle REMOVE_PLANT_TYPE to keep them)")
if TAG_CHEM_ROOT:
    print(f"Added baseline rdf:type ChemicalConcept: {root_tagged}")
print("Subclass typings added:")
for k,v in subclass_counts.items():
    if v:
        print(f"  {k:14} {v}")
print("Saved →", ONT_OUT)


# ### Merging data from Dr. Duke's Phytochemical & Ethnobotanical Database

# In[94]:


# Merge requested columns into one table
# Columns: ACTIVITY (from ACTIVITIES), CHEM (from AGGREGAC), CHEMID (from CHEMICALS),
#          DOSAGE (from DOSAGE), GENUS/SPECIES/FAMILY/COUNTRY/TAXON (from ETHNOBOT),
#          LONGREF (expanded via REFERENCES).
#
# Join logic:
#  - Backbone: AGGREGAC provides CHEM ↔ ACTIVITY relationships (+ its REFERENCE)
#  - ACTIVITIES joins on ACTIVITY (normalized) to validate/standardize labels
#  - CHEMICALS joins on CHEM (normalized) to bring CHEMID
#  - DOSAGE joins on CHEM (normalized) to bring DOSAGE and its REFERENCE
#  - ETHNOBOT joins on ACTIVITY (normalized) to bring plant info (one row per
#    matching plant+activity, cross-joined with every chemical that has that activity)
#  - REFERENCES maps all reference keys (AGGREGAC/DOSAGE/ETHNOBOT) to LONGREF
#
# Result can be 1-to-many due to ETHNOBOT reporting many plants per activity.

import pandas as pd

# Helpers
def read_csv_any(path):
    try:
        df = pd.read_csv(path, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    return df

def norm_act(s):
    return s.astype(str).str.strip().str.lower()

def norm_chem(s):
    return s.astype(str).str.strip() 

# Load source files
ACTIVITIES   = read_csv_any("ACTIVITIES.csv")     # expect: ACTIVITY, ...
AGGREGAC     = read_csv_any("AGGREGAC.csv")       # expect: CHEM, ACTIVITY, REFERENCE, ...
CHEMICALS    = read_csv_any("CHEMICALS.csv")      # expect: CHEM, CHEMID, ...
DOSAGE       = read_csv_any("DOSAGE.csv")         # expect: CHEM, DOSAGE, REFERENCE, ...
ETHNOBOT     = read_csv_any("ETHNOBOT.csv")       # expect: GENUS, SPECIES, FAMILY, COUNTRY, TAXON, ACTIVITY, REFERENCE, ...
REFERENCES   = read_csv_any("REFERENCES.csv")     # expect: REFERENCE, LONGREF

# Normalize keys to join on
# AGGREGAC backbone
agg = AGGREGAC.copy()
agg = agg.rename(columns={c:c.strip() for c in agg.columns})
if "CHEM" not in agg or "ACTIVITY" not in agg:
    raise ValueError("AGGREGAC must contain CHEM and ACTIVITY columns.")

agg["chem_key"] = norm_chem(agg["CHEM"])
agg["act_key"]  = norm_act(agg["ACTIVITY"])

# ACTIVITIES (for canonical activity labels)
act = ACTIVITIES.copy()
if "ACTIVITY" not in act:
    raise ValueError("ACTIVITIES must contain ACTIVITY column.")
act["act_key"] = norm_act(act["ACTIVITY"])
act = act[["act_key", "ACTIVITY"]].drop_duplicates()

# CHEMICALS (for CHEMID)
chem = CHEMICALS.copy()
if "CHEM" not in chem or "CHEMID" not in chem:
    raise ValueError("CHEMICALS must contain CHEM and CHEMID columns.")
chem["chem_key"] = norm_chem(chem["CHEM"])
chem = chem[["chem_key", "CHEMID"]].drop_duplicates()

# DOSAGE (by CHEM)
dos = DOSAGE.copy()
if "CHEM" in dos:  # tolerate missing file/cols
    dos["chem_key"] = norm_chem(dos["CHEM"])
else:
    dos["chem_key"] = ""
if "DOSAGE" not in dos:
    dos["DOSAGE"] = ""
if "REFERENCE" not in dos:
    dos["REFERENCE"] = ""
dos = dos[["chem_key", "DOSAGE", "REFERENCE"]].drop_duplicates()

# ETHNOBOT (by ACTIVITY)
eth = ETHNOBOT.copy()
for col in ["GENUS","SPECIES","FAMILY","COUNTRY","TAXON"]:
    if col not in eth: eth[col] = ""
if "ACTIVITY" in eth:
    eth["act_key"] = norm_act(eth["ACTIVITY"])
else:
    eth["act_key"] = ""
if "REFERENCE" not in eth:
    eth["REFERENCE"] = ""
eth = eth[["act_key","GENUS","SPECIES","FAMILY","COUNTRY","TAXON","REFERENCE"]].drop_duplicates()

# REFERENCES map
refs = REFERENCES.copy()
if "REFERENCE" not in refs or "LONGREF" not in refs:
    raise ValueError("REFERENCES must contain REFERENCE and LONGREF columns.")
ref_map = refs.dropna(subset=["REFERENCE"]).drop_duplicates().set_index("REFERENCE")["LONGREF"].to_dict()

# Assemble final table step-by-step
# 1) backbone: CHEM ↔ ACTIVITY from AGGREGAC (keep AGGREGAC reference as agg_ref)
backbone = agg[["chem_key","act_key","CHEM","ACTIVITY"]].copy()
if "REFERENCE" in agg:
    backbone["agg_ref"] = agg["REFERENCE"].fillna("").astype(str).str.strip()
else:
    backbone["agg_ref"] = ""

# 2) Add canonical ACTIVITY label from ACTIVITIES (optional but requested source-of-truth)
backbone = backbone.merge(act, on="act_key", how="left", suffixes=("", "_ACTIVITIES"))
# Prefer ACTIVITIES.ACTIVITY if present, else original
backbone["ACTIVITY"] = backbone["ACTIVITY_ACTIVITIES"].where(backbone["ACTIVITY_ACTIVITIES"].notna() & (backbone["ACTIVITY_ACTIVITIES"].astype(str)!=""), backbone["ACTIVITY"])
backbone = backbone.drop(columns=[c for c in backbone.columns if c.endswith("_ACTIVITIES")])

# 3) Add CHEMID from CHEMICALS
backbone = backbone.merge(chem, on="chem_key", how="left")

# 4) Add DOSAGE (and its reference) from DOSAGE (by CHEM)
backbone = backbone.merge(dos, on="chem_key", how="left", suffixes=("", "_DOS"))
backbone = backbone.rename(columns={"REFERENCE":"dos_ref"})

# 5) Cross-join plants that have the same ACTIVITY via ETHNOBOT
merged = backbone.merge(
    eth,
    on="act_key",
    how="left",
    suffixes=("", "_ETH")
)

# 6) Build LONGREF by expanding all present reference keys through REFERENCES
def collect_longref(row):
    keys = []
    for k in ["agg_ref", "dos_ref", "REFERENCE"]:  # ETHNOBOT's REFERENCE column kept as "REFERENCE"
        v = str(row.get(k,"")).strip()
        if v:
            # Split on common delimiters if present
            for token in [t.strip() for t in v.replace("|",";").replace(",",";").split(";")]:
                if token:
                    keys.append(token)
    if not keys:
        return ""
    keys = sorted(set(keys))
    longs = [ref_map.get(k, "") for k in keys if ref_map.get(k, "")]
    # Prefer long refs; if none found, fall back to keys
    return "; ".join(sorted(set(longs))) if any(longs) else "; ".join(keys)

merged["LONGREF"] = merged.apply(collect_longref, axis=1)

# 7) Final selection in the order you specified
out = merged[[
    "ACTIVITY",        # from ACTIVITIES (preferred) / AGGREGAC
    "CHEM",            # from AGGREGAC
    "CHEMID",          # from CHEMICALS
    "DOSAGE",          # from DOSAGE
    "GENUS", "SPECIES","FAMILY","COUNTRY","TAXON",  # from ETHNOBOT
    "LONGREF"          # expanded via REFERENCES
]].copy()

# Clean up whitespace / duplicates
for c in out.columns:
    out[c] = out[c].fillna("").astype(str).str.strip()
out = out.drop_duplicates().reset_index(drop=True)

OUT_CSV = "activity_chem_taxon_dosage_refs.csv"  # name it whatever you like
out.to_csv(OUT_CSV, index=False)
print("Saved:", OUT_CSV)

print(f"Rows: {len(out):,}")
out.head(20)


# getting dois

# In[96]:


import pandas as pd, json, re, hashlib
from pathlib import Path

IN_CSV  = "activity_chem_taxon_dosage_refs.csv"
OUT_CSV = "activity_chem_taxon_dosage_refs_with_doi.csv"
CACHE_FILE = Path("longref2doi_cache.json")
CHUNK = 200_000                                
WRITE_COMPRESSION = None                       

_DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)

def normalize_doi(doi: str) -> str:
    d = str(doi).strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d, flags=re.I)
    d = re.sub(r'^(doi|dois)\s*:?\s*', '', d, flags=re.I)
    return d.rstrip(").,;]")

def extract_doi_inline(text: str):
    if not text:
        return None
    m = _DOI_RE.search(str(text))
    return normalize_doi(m.group(1)) if m else None

def lr_norm(s: str) -> str:
    return re.sub(r"\s+"," ", str(s).strip())

def lr_key(s: str) -> str:
    return hashlib.sha1(lr_norm(s).encode("utf-8")).hexdigest()

try:
    CACHE = json.loads(CACHE_FILE.read_text())
except Exception:
    CACHE = {}

def doi_from_longref(longref: str):
    d_inline = extract_doi_inline(longref)
    if d_inline:
        return d_inline, "inline"
    k = lr_key(longref or "")
    d_cache = CACHE.get(k, "")
    if d_cache:
        return d_cache, "cache"
    return "", ""

first = True
reader = pd.read_csv(IN_CSV, dtype=str, low_memory=False, chunksize=CHUNK)

for chunk in reader:
    chunk = chunk.fillna("")
    if "LONGREF" not in chunk.columns:
        raise KeyError("Expected a 'LONGREF' column in the input CSV.")
    dois, sources = [], []
    for lr in chunk["LONGREF"].astype(str):
        d, src = doi_from_longref(lr)
        dois.append(d); sources.append(src)
    chunk["DOI"] = dois
    chunk["DOI_source"] = sources

    mode   = "w" if first else "a"
    header = first
    chunk.to_csv(OUT_CSV, index=False, mode=mode, header=header,
                 compression=WRITE_COMPRESSION)
    first = False

print("Wrote:", OUT_CSV, "(compression:", WRITE_COMPRESSION or "none", ")")


# In[97]:


# Retarget Plant individuals from PlantConcept → Plant (no new classes created)
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal
from collections import deque
from pathlib import Path

# Configure: choose ontology file(s)
CANDIDATES = [
    # Your preferred file first (edit if needed):
    "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched_plants_smiles_fixed.rdf",
    "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched.rdf",
    "phytotherapies_final_enriched_with_ChEMBL_mechanisms_typed_clean.rdf",
    "phytotherapies_final_enriched_with_ChEMBL_mechanisms_typed.rdf",
    "phytotherapies_final_enriched_with_ChEMBL_mechanisms.rdf",
]
def find_first(paths):
    for p in paths:
        if Path(p).exists():
            return p
    raise FileNotFoundError("None of these ontology files were found:\n  - " + "\n  - ".join(paths))

ONT_IN  = find_first(CANDIDATES)
ONT_OUT = Path(ONT_IN).with_suffix("").as_posix() + "_plants_retarg.rdf"

print(f"Loading → {ONT_IN}")

g = Graph(); g.parse(ONT_IN, format="xml")

def default_ns(graph):
    for prefix, ns in graph.namespaces():
        if prefix in ("", None):
            return Namespace(str(ns))
    # Fallback to usual base
    return Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

NS = default_ns(g)

# Helpers
def find_class_by_label_or_local(graph, names):
    names = list(names)
    # Label match
    for n in names:
        for s in graph.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in graph:
                return s
    # Local-name match under default NS
    base = str(NS)
    for n in names:
        candidate = URIRef(base + n)
        if (candidate, RDF.type, OWL.Class) in graph:
            return candidate
    return None

def is_subclass_of(graph, child, root):
    if not child or not root:
        return False
    if child == root:
        return True
    seen = {child}; q = deque([child])
    while q:
        cur = q.popleft()
        for sup in graph.objects(cur, RDFS.subClassOf):
            if sup == root:
                return True
            if sup not in seen:
                seen.add(sup); q.append(sup)
    return False

# Resolve classes (no creation)
PLANT_ROOT = find_class_by_label_or_local(g, ["PlantConcept","Plant Concept"])
PLANT_LEAF = find_class_by_label_or_local(g, ["Plant"])

if PLANT_ROOT is None:
    raise RuntimeError("Could not find the class 'PlantConcept' in the ontology.")

if PLANT_LEAF is None:
    print("[WARN] No subclass named 'Plant' found; nothing will be retargeted.")
else:
    # Ensure Plant is actually under PlantConcept (not required to retag, but good to know)
    if not is_subclass_of(g, PLANT_LEAF, PLANT_ROOT):
        print("[WARN] 'Plant' is not modeled as a subclass of 'PlantConcept' in this file.")

# Retarget individuals
moved = 0
skipped_schema = 0
both_had_types = 0

if PLANT_LEAF is not None:
    for s in list(g.subjects(RDF.type, PLANT_ROOT)):
        # Skip schema objects (classes / properties / restrictions)
        if (s, RDF.type, OWL.Class) in g or (s, RDF.type, OWL.ObjectProperty) in g or (s, RDF.type, OWL.DatatypeProperty) in g:
            skipped_schema += 1
            continue
        # If it already also has Plant, just drop the root type
        if (s, RDF.type, PLANT_LEAF) in g:
            both_had_types += 1
            g.remove((s, RDF.type, PLANT_ROOT))
            moved += 1
            continue
        # Otherwise: add Plant and remove PlantConcept
        g.add((s, RDF.type, PLANT_LEAF))
        g.remove((s, RDF.type, PLANT_ROOT))
        moved += 1

# Export PLANT_CLASS for later ingest cells
# Prefer 'Plant' subclass for future minting; fall back to root if missing
PLANT_CLASS = PLANT_LEAF or PLANT_ROOT

print(f"Retag summary:")
print(f"  • moved PlantConcept → Plant: {moved}")
print(f"  • skipped schema nodes:      {skipped_schema}")
print(f"  • already had both types:    {both_had_types}")
print(f"  • PLANT_CLASS for later use: {PLANT_CLASS}")

g.serialize(ONT_OUT, format="xml")
print(f"Saved → {ONT_OUT}")


# **Getting ontology stats**

# In[99]:


# Ontology stats + PlantConcept/Plant verification (read-only)
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from collections import defaultdict
from pathlib import Path

# Point this at the file you want to inspect
ONT = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched_plants_smiles_fixed_plants_retarg.rdf"

fmt = "turtle" if ONT.lower().endswith((".ttl", ".turtle")) else "xml"
g = Graph(); g.parse(ONT, format=fmt)

NS = Namespace("http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#")

def get_label(graph, uri):
    for _, _, label in graph.triples((uri, RDFS.label, None)):
        return str(label)
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.rsplit("/", 1)[-1]

# Buckets
classes = set()
object_properties = set()
data_properties = set()
individuals = set()
instances_by_class = defaultdict(int)

# Count by explicit rdf:type
for s, o in g.subject_objects(RDF.type):
    if o in (OWL.Class, RDFS.Class):
        classes.add(s)
    elif o == OWL.ObjectProperty:
        object_properties.add(s)
    elif o == OWL.DatatypeProperty:
        data_properties.add(s)
    else:
        instances_by_class[o] += 1
        individuals.add(s)

print("Total RDF Triples:", len(g))
print("Total Classes:", len(classes))
print("Total Object Properties:", len(object_properties))
print("Total Data Properties:", len(data_properties))
print("Total Individuals (typed):", len(individuals))
print("\nTop instance counts by class:")
for cls_uri, count in sorted(instances_by_class.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"  {get_label(g, cls_uri)}: {count}")

# Verification: PlantConcept vs Plant
PlantConcept = URIRef(str(NS) + "PlantConcept")
Plant        = URIRef(str(NS) + "Plant")

root_only = {
    s for s in g.subjects(RDF.type, PlantConcept)
    if (s, RDF.type, Plant) not in g and (s, RDF.type, OWL.Class) not in g
}

n_plant = sum(1 for _ in g.subjects(RDF.type, Plant))
n_root  = sum(1 for _ in g.subjects(RDF.type, PlantConcept))
n_root_only = len(root_only)

print("\nVerification:")
print("  Individuals typed Plant:         ", n_plant)
print("  Individuals typed PlantConcept:  ", n_root)
print("  Root-only (PlantConcept w/o Plant):", n_root_only)
if n_root_only:
    print("  Sample of root-only individuals:")
    for i, s in enumerate(sorted(root_only, key=str)[:5]):
        print("   •", s)


# In[101]:


# Ontology Deduper & NA Cleaner (ADD-ONLY to canonical, deletes only dup nodes & NA literals)
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal
from rdflib.namespace import XSD
from pathlib import Path
from collections import defaultdict, deque
import re

ONT_IN  = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched_plants_smiles_fixed.rdf"
ONT_OUT = Path(ONT_IN).with_suffix("").as_posix() + "_dedup_clean.rdf"

NS_DEFAULT = "http://www.semanticweb.org/orestah/ontologies/2024/9/phytotherapies#"

# Ensure you have RDKIT
USE_RDKIT = True
try:
    from rdkit import Chem
except Exception:
    USE_RDKIT = False

# Load graph and NS
fmt = "turtle" if ONT_IN.lower().endswith((".ttl",".turtle")) else "xml"
g = Graph(); g.parse(ONT_IN, format=fmt)

def default_ns(graph):
    for prefix, ns in graph.namespaces():
        if prefix in ("", None):
            return Namespace(str(ns))
    return Namespace(NS_DEFAULT)

NS = default_ns(g)

# Common properties used below
hasSMILES   = URIRef(str(NS)+"hasSMILES")
hasInChIKey = URIRef(str(NS)+"hasInChIKey")
hasGenus    = URIRef(str(NS)+"hasGenus")
hasSpecies  = URIRef(str(NS)+"hasSpecies")
hasTaxon    = URIRef(str(NS)+"hasTaxon")
hasDOI      = URIRef(str(NS)+"hasDOI")  # optional; your data may or may not use it

# Class resolution
def find_class_by_label_or_local(graph, names):
    names = list(names)
    # By exact rdfs:label
    for n in names:
        for s in graph.subjects(RDFS.label, Literal(n)):
            if (s, RDF.type, OWL.Class) in graph:
                return s
    # By localname under default NS
    base = str(NS)
    for n in names:
        c = URIRef(base + n)
        if (c, RDF.type, OWL.Class) in graph:
            return c
    return None

def is_subclass_of(graph, child, root):
    if not child or not root:
        return False
    if child == root:
        return True
    seen = {child}; q = deque([child])
    while q:
        cur = q.popleft()
        for sup in graph.objects(cur, RDFS.subClassOf):
            if sup == root:
                return True
            if sup not in seen:
                seen.add(sup); q.append(sup)
    return False

# Key anchors in your schema (must exist)
CHEM_ROOT      = find_class_by_label_or_local(g, ["ChemicalConcept","Chemical Concept","ChemicalEntity","Chemical Entity"])
PLANT_ROOT     = find_class_by_label_or_local(g, ["PlantConcept","Plant Concept"])
PLANT_LEAF     = find_class_by_label_or_local(g, ["Plant"])
THER_CLASS     = find_class_by_label_or_local(g, ["TherapeuticEffect","Therapeutic Concept","TherapeuticConcept"])
RESEARCH_ROOT  = find_class_by_label_or_local(g, ["ResearchConcept","Research Concept"])
PAPER_CLASS    = find_class_by_label_or_local(g, ["ScientificPaper","Paper"])  # We'll leave as-is if present
PATHWAY_CLASS  = find_class_by_label_or_local(g, ["Pathway"])  # under HumanConcept in your schema

missing = [n for n,v in {"CHEM_ROOT":CHEM_ROOT,"PLANT_ROOT":PLANT_ROOT,"THER_CLASS":THER_CLASS}.items() if v is None]
if missing:
    raise RuntimeError("Missing required anchors in the ontology: " + ", ".join(missing))

# If ScientificPaper class exists but is not under ResearchConcept, leave it—this script only dedupes.
if RESEARCH_ROOT and PAPER_CLASS and not is_subclass_of(g, PAPER_CLASS, RESEARCH_ROOT):
    # We won't change schema; your other cell already aligns ScientificPaper under ResearchConcept
    pass

# Helpers
def norm_text(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip().lower()
    # strip quotes and punctuation around
    s = re.sub(r"^[\"'`]+|[\"'`]+$", "", s)
    return s

NA_TOKENS = {"na","n/a","n.a","n.a.","nan","none","null","not available","not_applicable","not applicable"}
def is_na_like(lit: Literal) -> bool:
    if not isinstance(lit, Literal):
        return False
    s = str(lit).strip().lower()
    # Remove punctuation/spaces
    s2 = re.sub(r"[^a-z0-9]+", "", s)
    base = {
        "na","na", "na", "na", "nan", "none", "null",
        "notavailable","notapplicable"
    }
    return s in NA_TOKENS or s2 in base

def label_of(node):
    for o in g.objects(node, RDFS.label):
        return str(o)
    return None

def canonical_smiles(smi):
    if not USE_RDKIT or not smi:
        return None
    try:
        m = Chem.MolFromSmiles(str(smi))
        if not m: return None
        return Chem.MolToSmiles(m, canonical=True)
    except Exception:
        return None

def normalize_doi(s):
    d = str(s).strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d, flags=re.I)
    d = re.sub(r'^(doi|dois)\s*:?\s*', '', d, flags=re.I)
    d = d.rstrip(").,; ]")
    return d.lower()

def types_of(node):
    return set(g.objects(node, RDF.type))

def instance_of(node, root):
    ts = types_of(node)
    for t in ts:
        if t == OWL.NamedIndividual:  # skip marker
            continue
        if t == root or is_subclass_of(g, t, root):
            return True
    return False

def data_values(node, prop):
    return [o for o in g.objects(node, prop) if isinstance(o, Literal)]

def first_value(node, prop):
    for o in g.objects(node, prop):
        return o
    return None

# Core merging
def merge_nodes(target, duplicate):
    """Move all triples from/to `duplicate` to `target`; then delete `duplicate`."""
    if target == duplicate:
        return 0,0
    added = 0; removed = 0
    # Outgoing
    for _, p, o in list(g.triples((duplicate, None, None))):
        if (target, p, o) not in g:
            g.add((target, p, o)); added += 1
        g.remove((duplicate, p, o)); removed += 1
    # Incoming
    for s, p, _ in list(g.triples((None, None, duplicate))):
        if (s, p, target) not in g:
            g.add((s, p, target)); added += 1
        g.remove((s, p, duplicate)); removed += 1
    return added, removed

# Pick canonical URI in a bucket
def pick_canonical(uris):
    # Prefer one with a label; tiebreaker: shortest IRI
    labeled = [u for u in uris if label_of(u)]
    if labeled:
        return min(labeled, key=lambda u: (len(str(u)), str(u)))
    return min(uris, key=lambda u: (len(str(u)), str(u)))

# 1) Remove NA-like literals
na_removed = 0
for s, p, o in list(g.triples((None, None, None))):
    if isinstance(o, Literal) and is_na_like(o):
        g.remove((s, p, o)); na_removed += 1

print(f"[NA cleanup] Removed {na_removed} NA-like literal assertions.")

# Build buckets for deduplication
buckets = {
    "chemical": defaultdict(list),
    "plant":    defaultdict(list),
    "paper":    defaultdict(list),
    "pathway":  defaultdict(list),
    "effect":   defaultdict(list),
}

# Chemicals
for subj, _, _ in g.triples((None, RDF.type, None)):
    if not instance_of(subj, CHEM_ROOT):
        continue
    key = None
    # By InChIKey
    ik = first_value(subj, hasInChIKey)
    if isinstance(ik, Literal) and str(ik).strip():
        key = ("chem:ikey", norm_text(str(ik)))
    # Else by canonical SMILES
    if key is None:
        smi = first_value(subj, hasSMILES)
        smi = str(smi) if isinstance(smi, Literal) else None
        can = canonical_smiles(smi) if smi else None
        if can:
            key = ("chem:smi", can)
    # eElse by label
    if key is None:
        lbl = label_of(subj)
        if lbl:
            key = ("chem:label", norm_text(lbl))
    if key:
        buckets["chemical"][key].append(subj)

# PLANTS (prefer taxon, else label, else genus+species)
for subj, _, _ in g.triples((None, RDF.type, None)):
    if not (instance_of(subj, PLANT_LEAF) or instance_of(subj, PLANT_ROOT)):
        continue
    key = None
    tx = first_value(subj, hasTaxon)
    if isinstance(tx, Literal) and str(tx).strip():
        key = ("plant:taxon", norm_text(str(tx)))
    if key is None:
        lbl = label_of(subj)
        if lbl:
            key = ("plant:label", norm_text(lbl))
    if key is None:
        gval = first_value(subj, hasGenus)
        sval = first_value(subj, hasSpecies)
        if isinstance(gval, Literal) and isinstance(sval, Literal):
            gs = f"{str(gval).strip()} {str(sval).strip()}".strip()
            if gs:
                key = ("plant:genus_species", norm_text(gs))
    if key:
        buckets["plant"][key].append(subj)

# PAPERS (by DOI in label or hasDOI)
for subj, _, _ in g.triples((None, RDF.type, None)):
    if PAPER_CLASS and not instance_of(subj, PAPER_CLASS):
        continue
    # try hasDOI
    d = first_value(subj, hasDOI)
    doi_key = None
    if isinstance(d, Literal) and str(d).strip():
        doi_key = normalize_doi(str(d))
    # else try label
    if not doi_key:
        lbl = label_of(subj)
        if lbl:
            doi_key = normalize_doi(lbl)
    if doi_key:
        buckets["paper"][("paper:doi", doi_key)].append(subj)

# PATHWAYS (by label)
if PATHWAY_CLASS:
    for subj, _, _ in g.triples((None, RDF.type, None)):
        if not instance_of(subj, PATHWAY_CLASS):
            continue
        lbl = label_of(subj)
        if lbl:
            buckets["pathway"][("path:label", norm_text(lbl))].append(subj)

# THERAPEUTIC EFFECTS (by label)
if THER_CLASS:
    for subj, _, _ in g.triples((None, RDF.type, None)):
        if not instance_of(subj, THER_CLASS):
            continue
        lbl = label_of(subj)
        if lbl:
            buckets["effect"][("eff:label", norm_text(lbl))].append(subj)

# Merge duplicates per category
report = {}
total_added = 0
total_removed = 0
total_merged_nodes = 0

def dedupe_category(name, bucket):
    global total_added, total_removed, total_merged_nodes
    merges = 0; adds = 0; rems = 0; groups = 0
    for key, uris in bucket.items():
        if len(uris) < 2:
            continue
        groups += 1
        target = pick_canonical(uris)
        # Merge every other into target
        for dup in sorted(set(uris) - {target}, key=str):
            a, r = merge_nodes(target, dup)
            adds += a; rems += r; merges += 1
    report[name] = {"groups": groups, "merges": merges, "added": adds, "removed": rems}
    total_added  += adds
    total_removed += rems
    total_merged_nodes += merges

for cat in ["chemical","plant","paper","pathway","effect"]:
    dedupe_category(cat, buckets[cat])

# Summary and save
print("\n[Dedup summary]")
for cat, stats in report.items():
    print(f"  {cat:8} → groups={stats['groups']:4d}, merged_nodes={stats['merges']:5d}, triples+={stats['added']:6d}, triples-={stats['removed']:6d}")
print(f"\nTOTAL merged nodes: {total_merged_nodes}")
print(f"TOTAL triples added: {total_added}")
print(f"TOTAL triples removed: {total_removed}")
print(f"[INFO] Graph now has {len(g)} triples.")

g.serialize(ONT_OUT, format="xml")
print(f"Saved → {ONT_OUT}")


# ### Making sure inverse object properties are loaded.

# In[119]:


# Inverse object-property sync (triples + domain/range + optional typing) ===
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# If you've already loaded your graph as `g`, this will use it.
# Otherwise, set ONT_IN to a file to load, and optionally SAVE_OUT to write back.
USE_PRELOADED_GRAPH = 'g' in globals()
ONT_IN   = "phytotherapies_final_enriched_with_ChEMBL_mechanisms_ATC_filtered_enriched_plants_smiles_fixed.rdf"
SAVE_OUT = None  # e.g., "ontology_with_inverse_sync.rdf" or None to skip saving

ADD_MISSING_INVERSE_TRIPLES   = True   # add (o Q s) for each (s P o), and vice versa
SYNC_DOMAIN_RANGE              = True   # propagate domain/range across inverse properties
INFER_TYPES_FROM_DOMAIN_RANGE  = True   # assert rdf:type from domain/range for instances

# Load (if needed)
if not USE_PRELOADED_GRAPH:
    g = Graph()
    fmt = "turtle" if ONT_IN.lower().endswith((".ttl", ".turtle")) else "xml"
    g.parse(ONT_IN, format=fmt)

def localname(u: URIRef) -> str:
    s = str(u)
    return s.rsplit('#',1)[-1].rsplit('/',1)[-1]

# Gather inverse pairs P <-> Q
def gather_inverse_pairs(graph: Graph):
    pairs = {}
    # (P owl:inverseOf Q)
    for p, q in graph.subject_objects(OWL.inverseOf):
        if isinstance(p, URIRef) and isinstance(q, URIRef) and p != q:
            pairs[p] = q
            pairs[q] = p
    # also catch (Q owl:inverseOf P)
    for q, p in graph.subject_objects(OWL.inverseOf):
        if isinstance(p, URIRef) and isinstance(q, URIRef) and p != q:
            pairs[p] = q
            pairs[q] = p
    return pairs

inverse_pairs = gather_inverse_pairs(g)
symmetric_props = {p for p in g.subjects(RDF.type, OWL.SymmetricProperty) if isinstance(p, URIRef)}

added_inverse_triples = 0
added_types_from_domain = 0
added_types_from_range  = 0
added_domain_sync = 0
added_range_sync  = 0

# Domain/range sync helper
def sync_domain_range_for_pair(graph: Graph, p: URIRef, q: URIRef):
    global added_domain_sync, added_range_sync
    # dom(P) -> rng(Q) ; rng(P) -> dom(Q)
    domP = set(graph.objects(p, RDFS.domain))
    rngP = set(graph.objects(p, RDFS.range))
    domQ = set(graph.objects(q, RDFS.domain))
    rngQ = set(graph.objects(q, RDFS.range))

    for d in domP:
        if (q, RDFS.range, d) not in graph:
            graph.add((q, RDFS.range, d)); added_range_sync += 1
    for r in rngP:
        if (q, RDFS.domain, r) not in graph:
            graph.add((q, RDFS.domain, r)); added_domain_sync += 1

    # Also the other direction to fill any missing info
    for d in domQ:
        if (p, RDFS.range, d) not in graph:
            graph.add((p, RDFS.range, d)); added_range_sync += 1
    for r in rngQ:
        if (p, RDFS.domain, r) not in graph:
            graph.add((p, RDFS.domain, r)); added_domain_sync += 1

# Typing helper from domain/range (conservative)
def infer_types_for_triple(graph: Graph, s: URIRef, p: URIRef, o: URIRef):
    global added_types_from_domain, added_types_from_range
    # add rdf:type s dom(P) and o rng(P) if not already present
    for d in graph.objects(p, RDFS.domain):
        if (s, RDF.type, d) not in graph:
            graph.add((s, RDF.type, d)); added_types_from_domain += 1
    for r in graph.objects(p, RDFS.range):
        if (o, RDF.type, r) not in graph:
            graph.add((o, RDF.type, r)); added_types_from_range += 1

# 1) Sync domain/range for all inverse pairs (optional)
if SYNC_DOMAIN_RANGE:
    for p, q in sorted(inverse_pairs.items(), key=lambda kv: (localname(kv[0]), localname(kv[1]))):
        if str(p) < str(q):  # do each pair once
            sync_domain_range_for_pair(g, p, q)

# 2) Add inverse triples and infer types from domain/range (optional)
if ADD_MISSING_INVERSE_TRIPLES or INFER_TYPES_FROM_DOMAIN_RANGE:
    # Build quick map from property to its inverse for O(1) lookup
    inv_of = dict(inverse_pairs)  # both directions included

    # For each triple (s p o) where o is not Literal:
    for s, p, o in g.triples((None, None, None)):
        if not isinstance(p, URIRef) or isinstance(o, Literal):
            continue

        # Infer types from p's domain/range
        if INFER_TYPES_FROM_DOMAIN_RANGE:
            infer_types_for_triple(g, s, p, o)

        # Add inverse triple if we know the inverse
        if ADD_MISSING_INVERSE_TRIPLES and p in inv_of:
            q = inv_of[p]
            if (o, q, s) not in g:
                g.add((o, q, s))
                added_inverse_triples += 1

# 3) Symmetric properties: add (o P s) for each (s P o) (non-literals)
for p in symmetric_props:
    for s, _, o in g.triples((None, p, None)):
        if not isinstance(o, Literal) and (o, p, s) not in g:
            g.add((o, p, s))
            added_inverse_triples += 1

# Report 
print("Inverse sync complete.")
print(f"  Inverse property pairs found: {len({tuple(sorted((str(p), str(q)))) for p,q in inverse_pairs.items() if str(p)<str(q)})}")
print(f"  Symmetric properties found: {len(symmetric_props)}")
print(f"  Inverse triples added: {added_inverse_triples}")
if SYNC_DOMAIN_RANGE:
    print(f"  Domain assertions synced (added): {added_domain_sync}")
    print(f"  Range assertions synced (added):  {added_range_sync}")
if INFER_TYPES_FROM_DOMAIN_RANGE:
    print(f"  Types inferred from domains: {added_types_from_domain}")
    print(f"  Types inferred from ranges:  {added_types_from_range}")

# Save (optional)
OUT_PATH = "phytotherapies_inverse_synced.rdf"  # pick any new name, you don't want to over-write an existing file
g.serialize(OUT_PATH, format="xml")
print(f"Saved inverse-synced ontology → {OUT_PATH}")


# In[1]:


# Ontology stats
from rdflib import Graph, URIRef, RDF, RDFS, OWL, Literal
from pathlib import Path

# Set file
ONT = "phytotherapies_inverse_synced.rdf"

# Auto format
fmt = "turtle" if ONT.lower().endswith((".ttl", ".turtle")) else "xml"

g = Graph()
g.parse(ONT, format=fmt)

# Classes (named only)
class_uris = set()
for s in g.subjects(RDF.type, OWL.Class):
    if isinstance(s, URIRef):
        class_uris.add(s)
for s in g.subjects(RDF.type, RDFS.Class):
    if isinstance(s, URIRef):
        class_uris.add(s)

# Individuals (named only)
# 1) Anything typed as owl:NamedIndividual
ind_uris = {s for s in g.subjects(RDF.type, OWL.NamedIndividual) if isinstance(s, URIRef)}

# 2) Anything typed to a class (where that class is declared as a Class)
for s, _, c in g.triples((None, RDF.type, None)):
    if isinstance(s, URIRef) and c in class_uris:
        ind_uris.add(s)

# Remove resources that are actually classes or properties
prop_like = {
    *{s for s in g.subjects(RDF.type, RDF.Property)},
    *{s for s in g.subjects(RDF.type, OWL.ObjectProperty)},
    *{s for s in g.subjects(RDF.type, OWL.DatatypeProperty)},
    *{s for s in g.subjects(RDF.type, OWL.AnnotationProperty)},
    *{s for s in g.subjects(RDF.type, OWL.OntologyProperty)},
}
ind_uris.difference_update(class_uris)
ind_uris.difference_update(prop_like)

# Properties (used) by usage pattern
# Object properties (used): predicates that appear with a non-literal object at least once
obj_props_used = set()
data_props_used = set()
for s, p, o in g:
    if isinstance(o, Literal):
        data_props_used.add(p)
    else:
        obj_props_used.add(p)

# (optional) restrict to "named" predicates only
obj_props_used = {p for p in obj_props_used if isinstance(p, URIRef)}
data_props_used = {p for p in data_props_used if isinstance(p, URIRef)}

# Print
print(f"File: {ONT}")
print(f"Total RDF triples: {len(g)}")
print(f"Total named classes: {len(class_uris)}")
print(f"Total individuals (instances): {len(ind_uris)}")
print(f"Object properties (used): {len(obj_props_used)}")
print(f"Data properties (used): {len(data_props_used)}")

