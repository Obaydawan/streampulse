"""
StreamPulse — AI Query Agent Guardrails

Enforces SELECT-only queries against an explicit table allowlist, using
sqlglot's syntax-tree parsing rather than naive string matching. This is
the layer that makes the agent trustworthy: it runs BEFORE any query is
shown to the user or executed, and does not rely on the LLM "behaving."
"""

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"silver_orders", "alerts"}


class GuardrailViolation(Exception):
    """Raised when a generated query fails a safety check."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validates that `sql` is a single, pure SELECT statement touching only
    tables in ALLOWED_TABLES. Returns the validated SQL if it passes.
    Raises GuardrailViolation with a specific reason if it doesn't.
    """
    sql = sql.strip().rstrip(";")

    if not sql:
        raise GuardrailViolation("Empty query.")

    try:
        parsed_statements = sqlglot.parse(sql, dialect="duckdb")
    except Exception as e:
        raise GuardrailViolation(f"SQL could not be parsed: {e}")

    if len(parsed_statements) != 1:
        raise GuardrailViolation("Only a single SQL statement is allowed.")

    statement = parsed_statements[0]

    if not isinstance(statement, exp.Select):
        raise GuardrailViolation(
            f"Only SELECT statements are allowed — got {type(statement).__name__}."
        )

    forbidden_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)
    for node in statement.walk():
        if isinstance(node[0], forbidden_types):
            raise GuardrailViolation(
                f"Query contains a forbidden operation: {type(node[0]).__name__}."
            )

    referenced_tables = {table.name for table in statement.find_all(exp.Table)}
    disallowed = referenced_tables - ALLOWED_TABLES
    if disallowed:
        raise GuardrailViolation(
            f"Query references disallowed table(s): {', '.join(disallowed)}. "
            f"Only {', '.join(ALLOWED_TABLES)} are queryable."
        )


    return sql
