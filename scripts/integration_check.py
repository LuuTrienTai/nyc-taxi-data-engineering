"""End-to-end 3-layer integration test on isolated synthetic demo fixture."""
import sys
from src.config import DATA_DIR
from src.pipeline import build_gold
from src.verify import verify_month


def run_check() -> int:
    if DATA_DIR.name != 'demo':
        raise RuntimeError('Integration tests require isolated demo DATA_DIR (e.g. /opt/project/data/demo)')

    print('=== Step 1: Initial Bronze -> Silver/Quarantine -> Gold run ===')
    first = build_gold('2025-01')
    assert (first['bronze'], first['gold'], first['rejected']) == (1203, 1200, 3), (
        f"Expected (1203, 1200, 3), got {(first['bronze'], first['gold'], first['rejected'])}"
    )
    expected_reasons = {'duplicate_trip_id': 1, 'invalid_trip_distance': 1, 'unknown_zone': 1}
    assert first['rejection_reasons'] == expected_reasons, (
        f"Expected rejection reasons {expected_reasons}, got {first['rejection_reasons']}"
    )

    print('\n=== Step 2: Independent 3-Layer Verification (before rerun) ===')
    before = verify_month('2025-01')

    print('\n=== Step 3: Idempotent Rerun Check ===')
    second = build_gold('2025-01')
    assert (second['bronze'], second['gold'], second['rejected']) == (1203, 1200, 3)
    after_rerun = verify_month('2025-01')
    assert after_rerun['bronze'] == before['bronze'], 'Bronze summary changed after idempotent rerun'
    assert after_rerun['silver_quarantine'] == before['silver_quarantine'], (
        'Silver/Quarantine summary changed after idempotent rerun'
    )
    assert after_rerun['gold'] == before['gold'], 'Gold summary changed after idempotent rerun'

    print('\n=== Step 4: Atomic Rollback Check (fail_after_batch=True) ===')
    try:
        build_gold('2025-01', fail_after_batch=True)
    except RuntimeError as exc:
        assert 'Injected failure' in str(exc), f'Unexpected RuntimeError: {exc}'
    else:
        raise AssertionError('Expected injected failure after COPY')

    after_rollback = verify_month('2025-01')
    assert after_rollback == after_rerun, 'Committed Gold state mutated after injected failure rollback'

    print(
        '\n[PASS] 3-Layer Integration Check Passed: '
        'Bronze=1,203 -> Silver valid=1,200 + Quarantine=3 (duplicate_trip_id=1, invalid_trip_distance=1, unknown_zone=1) '
        '-> Gold=1,200 facts & 3 reconciled marts; idempotent rerun and atomic rollback verified.'
    )
    return 0


if __name__ == '__main__':
    sys.exit(run_check())
