from ai_agent.gemini_client import GeminiClient

client = GeminiClient()

response = client.generate(
    "Reply with exactly: Gemini wrapper works"
)

print(response)
