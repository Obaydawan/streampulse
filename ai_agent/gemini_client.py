import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


class GeminiClient:
    """
    Thin wrapper around the Gemini API.

    This class is responsible only for communicating with Gemini.
    It does not validate SQL or execute database queries.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found.")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-3.5-flash-lite"

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return response.text.strip()
