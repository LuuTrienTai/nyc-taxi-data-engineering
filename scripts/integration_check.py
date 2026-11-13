"""Run against disposable demo project/database only; needs seeded demo Bronze."""
from src.config import DATA_DIR
from src.pipeline import build_gold
from src.verify import verify_month
if DATA_DIR.name!='demo': raise RuntimeError('Integration tests require isolated demo DATA_DIR')
a=build_gold('2025-01');before=verify_month('2025-01')
assert (a['bronze'],a['gold'],a['rejected'])==(1203,1201,2)
b=build_gold('2025-01');assert verify_month('2025-01')==before
try: build_gold('2025-01',fail_after_batch=True)
except RuntimeError as e:
    assert 'Injected failure' in str(e)
else: raise AssertionError('Expected injected failure')
assert verify_month('2025-01')==before
print('PASS: exact counts, duplicate preservation, rerun idempotency, rollback, mart reconciliation')
