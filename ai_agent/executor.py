import duckdb

from ai_agent.sql_generator import SQLGenerator
from ai_agent.guardrails import validate_sql

DB_PATH = "data/orders.duckdb"


def execute_question(question: str, generator: SQLGenerator | None = None) -> dict:
    """
    Generate SQL from a natural-language question, validate it, execute
    it, and return the results.

    `generator` can be injected (e.g. a mock) for testing without hitting
    the real Gemini API. If not provided, a real SQLGenerator is created
    lazily — only when this function actually runs, not at import time.
    """
    if generator is None:
        generator = SQLGenerator()

    sql = generator.generate_sql(question)

    # Security checks — use the validated/normalized SQL, not the raw output.
    sql = validate_sql(sql)

    con = duckdb.connect(DB_PATH, read_only=True)
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
