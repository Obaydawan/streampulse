from ai_agent.gemini_client import GeminiClient
from ai_agent.explain_prompt import EXPLAIN_SYSTEM_PROMPT

MAX_ROWS_IN_PROMPT = 30


def explain_results(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[tuple],
    client: GeminiClient | None = None,
) -> str:
    """
    Generates a plain-English explanation of query results, strictly
    grounded in the returned data. `client` can be injected for testing
    without hitting the real Gemini API.
    """
    if client is None:
        client = GeminiClient()

    if not rows:
        return "The query ran successfully but returned no results."

    total_rows = len(rows)
    display_rows = rows[:MAX_ROWS_IN_PROMPT]

    rows_text = "\n".join(
        ", ".join(f"{col}={val}" for col, val in zip(columns, row))
        for row in display_rows
    )

    truncation_note = ""
    if total_rows > MAX_ROWS_IN_PROMPT:
        truncation_note = f"\n(showing first {MAX_ROWS_IN_PROMPT} of {total_rows} total rows)"

    prompt = f"""
{EXPLAIN_SYSTEM_PROMPT}

User question: {question}

Columns: {', '.join(columns)}

Results:
{rows_text}
{truncation_note}

Write a 1-3 sentence plain-English summary of these results.
"""

    return client.generate(prompt).strip()
