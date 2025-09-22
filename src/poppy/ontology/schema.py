from rdflib import Graph


def load_schema(path: str, fmt: str = "xml") -> Graph:
    g = Graph()
    g.parse(path, format=fmt)
    return g
