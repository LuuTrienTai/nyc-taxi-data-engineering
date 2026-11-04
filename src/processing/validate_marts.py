import pandas as pd
import psycopg2

def validate_aggregations():
    print("--- Validating Gold Aggregations against Source Data ---")
    
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="nyc_taxi",
        user="taxi_admin", password="12345"
    )
    
    # 1. Get ALL raw data for Zone 132 from the database
    print("Fetching raw source data for Zone 132...")
    query_raw = "SELECT total_amount FROM staging.taxi_2026_01 WHERE pickup_location_id = 132"
    df = pd.read_sql(query_raw, con=conn)
    
    # 2. Calculate metric in Pandas
    pandas_revenue = df['total_amount'].sum()
    print(f"Pandas Source Revenue (All Zone 132 trips): ${pandas_revenue:,.2f}")
    
    # 3. Calculate metric using SQL aggregation
    # Notice we are using the exact same filter, but letting the database do the math
    query_sql = "SELECT SUM(total_amount) FROM staging.taxi_2026_01 WHERE pickup_location_id = 132"
    sql_revenue = pd.read_sql(query_sql, con=conn).iloc[0, 0]
        
    print(f"SQL Aggregation Revenue (All Zone 132 trips): ${sql_revenue:,.2f}")
    
    # 4. Compare
    if abs(pandas_revenue - sql_revenue) < 0.01: 
        print("✅ SUCCESS: Metrics match perfectly!")
    else:
        print(f"❌ ERROR: Metrics do not match! Difference: {abs(pandas_revenue - sql_revenue)}")
        
    conn.close()

if __name__ == "__main__":
    validate_aggregations()