from ai_agent.gemini_client import GeminiClient
from ai_agent.prompt import SYSTEM_PROMPT
from ai_agent.schemas import DATABASE_SCHEMA


class SQLGenerator:
    """
    Converts natural-language questions into SQL.
    """

    def __init__(self):
        self.client = GeminiClient()

    def generate_sql(self, question: str) -> str:
        prompt = f"""
{SYSTEM_PROMPT}

Database Schema:

{DATABASE_SCHEMA}

User Question:
{question}
"""

        return self.client.generate(prompt)
