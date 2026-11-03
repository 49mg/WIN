from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from app.config import settings

SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    conn = psycopg.connect(settings.database_url)
    register_vector(conn)
    return conn


def init_schema() -> None:
    """Create tables if they don't exist. Safe to run many times."""
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text())
