import os

import duckdb

from ai_agent.sql_generator import SQLGenerator
from ai_agent.guardrails import validate_sql

DB_PATH = os.getenv("DUCKDB_PATH", "data/orders.duckdb")
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN")


def get_connection(read_only: bool = True):
    """
    Prefer MotherDuck (cloud) if a token is available — this is what the
    deployed Streamlit Cloud app uses, since it has no access to the
    local pipeline's DuckDB file. Falls back to the local file for local
    development, where the live pipeline actually writes. Streamlit Cloud
    injects secrets as environment variables, so os.getenv works there too.
    """
    if MOTHERDUCK_TOKEN:
        return duckdb.connect(f"md:my_db?motherduck_token={MOTHERDUCK_TOKEN}", read_only=read_only)
    return duckdb.connect(DB_PATH, read_only=read_only)


def execute_question(
    question: str,
    generator: SQLGenerator | None = None,
    connection_factory=None,
) -> dict:
    """
    Generate SQL from a natural-language question, validate it, execute
    it, and return the results.

    `generator` can be injected (e.g. a mock) for testing without hitting
    the real Gemini API. `connection_factory` can be injected (e.g. to
    force the local file) so unit tests stay fast and offline regardless
    of whether MOTHERDUCK_TOKEN happens to be set in the environment. If
    not provided, both default to the real, lazy implementations.
    """
    if generator is None:
        generator = SQLGenerator()
    if connection_factory is None:
        connection_factory = get_connection

    sql = generator.generate_sql(question)

    # Security checks — use the validated/normalized SQL, not the raw output.
    sql = validate_sql(sql)

    con = connection_factory()
    try:
        result = con.execute(sql)
        columns = [col[0] for col in result.description]
        rows = result.fetchall()
    finally:
        con.close()

    return {
        "question": question,
        "sql": sql,
        "columns": columns,
        "rows": rows,
    }
