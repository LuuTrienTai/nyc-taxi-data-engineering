import os,sys,ast,subprocess,json
from pathlib import Path
import tempfile
root=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root))
fixture_dir=tempfile.TemporaryDirectory()
fixture_root=Path(fixture_dir.name)/'demo'
pgdata=Path(fixture_dir.name)/'pgdata'

os.environ['DATA_DIR']=str(fixture_root)
from scripts.demo_seed import seed
from src.pipeline import prepare_dimensions
from src.processing.silver import clean_batch
import pandas as pd
import pgserver
from pgserver._commands import POSTGRES_BIN_PATH
seed('2025-01');z,w=prepare_dimensions('2025-01')
raw=pd.read_parquet(fixture_root/'bronze/taxi/yellow_tripdata_2025-01.parquet')
v,b=clean_batch(raw,'2025-01',0,set(z.location_id))
assert (len(raw),len(v),len(b))==(1203,1201,2)
def lit(x):
 if pd.isna(x):return 'NULL'
 if isinstance(x,bool):return str(x).lower()
 if isinstance(x,(int,float)):return str(x)
 return "'"+str(x).replace("'","''")+"'"
def inserts(table,frame):
 return 'INSERT INTO '+table+' ('+','.join(frame.columns)+') VALUES '+','.join('('+','.join(map(lit,row))+')' for row in frame.itertuples(index=False,name=None))+';'
pgserver.initdb(['-A','trust'],pgdata=pgdata)
sql=[' '.join((root/'docker/postgres/init/01_gold.sql').read_text().split()),'BEGIN;',inserts('gold.dim_zone',z),inserts('gold.dim_weather_hour',w),inserts('gold.fact_trip',v)]
tree=ast.parse((root/'src/pipeline.py').read_text())
for node in ast.walk(tree):
 if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.startswith('INSERT INTO gold.agg_'):
  sql.append(' '.join(node.value.replace('%s',"'2025-01-01'").split())+';')
sql+=['COMMIT;',"DO $$ BEGIN IF (SELECT count(*) FROM gold.fact_trip)<>1201 THEN RAISE EXCEPTION 'fact count'; END IF; END $$;"]
for t in ['agg_daily_demand','agg_zone_demand','agg_hourly_weather']:
 sql.append(f"DO $$ BEGIN IF (SELECT sum(trip_count) FROM gold.{t})<>1201 OR (SELECT sum(total_revenue) FROM gold.{t})<>19216 THEN RAISE EXCEPTION 'mart mismatch'; END IF; END $$;")
sql+=['BEGIN;',"DELETE FROM gold.fact_trip WHERE data_month='2025-01-01';",'ROLLBACK;',"DO $$ BEGIN IF (SELECT count(*) FROM gold.fact_trip)<>1201 THEN RAISE EXCEPTION 'rollback failed'; END IF; END $$;","SELECT 'SQL_CHECKS_PASS' AS result;"]
r=subprocess.run([str(POSTGRES_BIN_PATH/'postgres'),'--single','-D',str(pgdata),'postgres'],input='\n'.join(sql)+'\n',text=True,capture_output=True)
print(r.stdout[-600:])
assert r.returncode==0 and 'ERROR:' not in r.stderr and 'SQL_CHECKS_PASS' in r.stdout,(r.stdout[-3000:],r.stderr)
print('PASS PostgreSQL 16.2 standalone: schema, 1201 facts, 3 marts counts/revenue, transaction rollback')
print('Fixture checks:',len(v),len(b),'weather hours',len(w))
