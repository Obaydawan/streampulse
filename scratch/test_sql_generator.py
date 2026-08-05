from ai_agent.sql_generator import SQLGenerator

generator = SQLGenerator()

sql = generator.generate_sql(
    "Show all orders."
)

print(sql)
