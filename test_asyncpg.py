import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="operan_user",
        password="operan_password",
        dbname="operan_db"
    )
    print("SUCCESS: Connected to PostgreSQL on port 5433!")
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
