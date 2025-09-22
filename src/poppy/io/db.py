from typing import Iterable, Dict, Any
import psycopg2
import psycopg2.extras


def connect_postgres(host: str, port: int, dbname: str, user: str, password: str):
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode="prefer",
        gssencmode="disable",
    )


def fetch_rows(conn, query: str) -> Iterable[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query)
        for row in cur:
            yield dict(row)
