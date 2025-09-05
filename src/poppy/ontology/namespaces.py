from rdflib import Namespace
def get_namespace(base: str):
    if not base.endswith(('#', '/')):
        base = base.rstrip('/') + '#'
    return Namespace(base)
