from ai_agent.sql_generator import SQLGenerator

generator = SQLGenerator()

sql = generator.generate_sql(
    "Show everything from bronze_orders."
)

print("\nGenerated SQL:")
print(sql)
