from ai_agent.guardrails import validate_sql, GuardrailViolation

queries = [
    "SELECT * FROM silver_orders;",
    "SELECT * FROM alerts;",
    "SELECT * FROM bronze_orders;",
]

for query in queries:
    print("=" * 60)
    print(query)

    try:
        validate_sql(query)
        print("✅ ALLOWED")
    except GuardrailViolation as e:
        print("❌ BLOCKED:", e)
