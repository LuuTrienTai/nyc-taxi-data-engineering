import ast
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class M1StructureTests(unittest.TestCase):
    def test_airflow_compose_services_and_localhost_binding(self):
        obj = yaml.safe_load((ROOT / "compose.airflow.yaml").read_text())
        self.assertEqual(set(obj["services"]), {"airflow-init", "airflow-webserver", "airflow-scheduler"})
        self.assertIn("127.0.0.1:", obj["services"]["airflow-webserver"]["ports"][0])

    def test_existing_compose_preserved(self):
        obj = yaml.safe_load((ROOT / "compose.yaml").read_text())
        self.assertTrue({"postgres", "metabase"}.issubset(obj["services"]))

    def test_dag_contract(self):
        text = (ROOT / "airflow/dags/nyc_taxi_monthly.py").read_text()
        ast.parse(text)
        for part in ("src.ingestion.taxi", "src.ingestion.weather", "src.processing.validate", "src.warehouse.load_staging", "dbt", "verify_output"):
            self.assertIn(part, text)
        self.assertIn("schedule=None", text)

if __name__ == '__main__':
    unittest.main()
