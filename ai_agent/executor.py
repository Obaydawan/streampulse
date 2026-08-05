import duckdb

from ai_agent.sql_generator import SQLGenerator
from ai_agent.guardrails import validate_sql

DB_PATH = "data/orders.duckdb"

generator = SQLGenerator()


def execute_question(question: str) -> dict:
    """
    Generate SQL from a natural-language question,
    validate it, execute it, and return the results.
    """

    sql = generator.generate_sql(question)

    # Security checks
    validate_sql(sql)

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
