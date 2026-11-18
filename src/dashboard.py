import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# --- Page Config ---
st.set_page_config(page_title="NYC Taxi Dashboard", layout="wide")

# --- DB Connection ---
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="nyc_taxi",
        user="taxi_admin",
        password="12345"
    )

conn = get_connection()

# --- Header & Filter ---
st.title("🚖 NYC Taxi Analytics Dashboard")
st.markdown("**Note on Definitions:** Number of trips = valid rows in Gold (`warehouse.fact_trip`). Revenue is defined as `total_amount`.")

# Get available months
months_df = pd.read_sql("SELECT DISTINCT data_month FROM warehouse.fact_trip ORDER BY data_month DESC", conn)
if months_df.empty:
    st.warning("No data available in warehouse.fact_trip. Please load data first.")
    st.stop()

month_list = months_df['data_month'].astype(str).tolist()
selected_month = st.selectbox("Select Month", month_list)

# --- Queries (Filtered by Month) ---
@st.cache_data(ttl=600)
def load_data(month):
    # 1. KPIs
    kpi_query = f"""
        SELECT COUNT(*) as total_trips,
               SUM(total_amount) as total_revenue,
               AVG(fare_amount) as avg_fare
        FROM warehouse.fact_trip
        WHERE data_month = '{month}'
    """
    kpi_df = pd.read_sql(kpi_query, conn).iloc[0]

    # 2. Daily Demand
    daily_query = f"""
        SELECT pickup_datetime::date as day, COUNT(*) as trip_count
        FROM warehouse.fact_trip
        WHERE data_month = '{month}'
        GROUP BY 1 ORDER BY 1
    """
    daily_df = pd.read_sql(daily_query, conn)

    # 3. Top Zones
    zones_query = f"""
        SELECT pickup_location_id, COUNT(*) as trip_count
        FROM warehouse.fact_trip
        WHERE data_month = '{month}'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """
    zones_df = pd.read_sql(zones_query, conn)

    # 4. Hourly Demand (for Weather-Demand proxy)
    hourly_query = f"""
        SELECT EXTRACT(HOUR FROM pickup_datetime) as hour, COUNT(*) as trip_count
        FROM warehouse.fact_trip
        WHERE data_month = '{month}'
        GROUP BY 1 ORDER BY 1
    """
    hourly_df = pd.read_sql(hourly_query, conn)

    return kpi_df, daily_df, zones_df, hourly_df

kpi, daily, zones, hourly = load_data(selected_month)

# --- KPI Section ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Trips", f"{int(kpi['total_trips']):,}")
col2.metric("Total Revenue", f"${kpi['total_revenue']:,.2f}")
col3.metric("Average Fare", f"${kpi['avg_fare']:,.2f}")

st.divider()

# --- Charts ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📅 Daily Demand")
    if not daily.empty:
        st.line_chart(daily.set_index('day')['trip_count'])
    else:
        st.info("No data for this month.")

with col_b:
    st.subheader("📍 Top 10 Pickup Zones")
    if not zones.empty:
        st.bar_chart(zones.set_index('pickup_location_id')['trip_count'])
    else:
        st.info("No data for this month.")

st.subheader("⏰ Demand by Hour of Day")
if not hourly.empty:
    st.bar_chart(hourly.set_index('hour')['trip_count'])
else:
    st.info("No data for this month.")