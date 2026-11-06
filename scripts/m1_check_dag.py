"""Static contract checks; runnable without Airflow installed."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "airflow/dags/nyc_taxi_monthly.py").read_text()
ast.parse(source)
for fragment in (
    "src.ingestion.taxi", "src.ingestion.weather", "src.processing.validate",
    "src.warehouse.load_staging", "dbt", "verify_output",
):
    assert fragment in source, fragment
assert "schedule=None" in source
print("[OK] DAG syntax and integration contracts")
