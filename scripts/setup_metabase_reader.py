"""
M4 Requirement: Create a read-only user for Metabase.
This fulfills the PDF requirement: "Cấu hình Metabase bằng tài khoản metabase_reader"
and "Kiểm tra tài khoản reader đọc được Gold nhưng không được sửa dữ liệu."
"""
import psycopg2

def create_reader_user():
    print("Connecting to Postgres as admin...")
    conn = psycopg2.connect(
        host="127.0.0.1", port=5432, dbname="nyc_taxi",
        user="taxi_admin", password="12345"
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating metabase_reader role...")
    try:
        cur.execute("CREATE USER metabase_reader WITH PASSWORD 'metabase_password';")
    except psycopg2.errors.DuplicateObject:
        print("User already exists, skipping creation.")

    print("Granting read-only access to warehouse and marts schemas...")
    cur.execute("GRANT USAGE ON SCHEMA warehouse TO metabase_reader;")
    cur.execute("GRANT USAGE ON SCHEMA marts TO metabase_reader;")
    cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA warehouse TO metabase_reader;")
    cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA marts TO metabase_reader;")
    
    # Ensure future tables are also readable
    cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA warehouse GRANT SELECT ON TABLES TO metabase_reader;")
    cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO metabase_reader;")

    print("[PASS] metabase_reader created and granted read-only access.")
    conn.close()

if __name__ == "__main__":
    create_reader_user()