"""Validate and normalize the source batch in memory."""
import numpy as np
import pandas as pd

from src.config import BUSINESS_TIMEZONE

REQUIRED = [
    'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'PULocationID', 'DOLocationID',
    'trip_distance', 'fare_amount', 'total_amount',
]
COLUMNS = [
    'data_month', 'source_row', 'pickup_date', 'pickup_datetime', 'dropoff_datetime',
    'pickup_hour', 'pickup_location_id', 'dropoff_location_id', 'passenger_count',
    'trip_distance', 'fare_amount', 'tip_amount', 'total_amount', 'duration_minutes',
    'payment_type', 'dst_ambiguous',
]
NUMERIC_FIELDS = {
    'pickup_location_id': 'PULocationID',
    'dropoff_location_id': 'DOLocationID',
    'passenger_count': 'passenger_count',
    'trip_distance': 'trip_distance',
    'fare_amount': 'fare_amount',
    'tip_amount': 'tip_amount',
    'total_amount': 'total_amount',
    'payment_type': 'payment_type',
}


def clean_batch(raw, month, offset, zone_ids):
    missing = set(REQUIRED) - set(raw.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')

    start = pd.Timestamp(month + '-01')
    end = start + pd.offsets.MonthBegin(1)
    out = pd.DataFrame(index=raw.index)
    out['data_month'] = start.date()
    out['source_row'] = np.arange(offset + 1, offset + len(raw) + 1)
    out['pickup_datetime'] = pd.to_datetime(raw.tpep_pickup_datetime, errors='coerce', format='mixed').dt.floor('us')
    out['dropoff_datetime'] = pd.to_datetime(raw.tpep_dropoff_datetime, errors='coerce', format='mixed').dt.floor('us')
    out['pickup_date'] = out.pickup_datetime.dt.date
    out['pickup_hour'] = out.pickup_datetime.dt.floor('h')
    for dest, source in NUMERIC_FIELDS.items():
        out[dest] = pd.to_numeric(raw[source], errors='coerce') if source in raw else np.nan
    out['duration_minutes'] = (out.dropoff_datetime - out.pickup_datetime).dt.total_seconds() / 60

    pickup_localized = out.pickup_datetime.dt.tz_localize(
        BUSINESS_TIMEZONE, ambiguous=True, nonexistent='NaT'
    )
    dropoff_localized = out.dropoff_datetime.dt.tz_localize(
        BUSINESS_TIMEZONE, ambiguous=True, nonexistent='NaT'
    )
    pickup_unambiguous = out.pickup_datetime.dt.tz_localize(
        BUSINESS_TIMEZONE, ambiguous='NaT', nonexistent='NaT'
    )
    # TLC wall-clock timestamps omit the UTC offset of the repeated hour.
    out['dst_ambiguous'] = pickup_localized.notna() & pickup_unambiguous.isna()

    reason = pd.Series('', index=raw.index)

    def reject(mask, label):
        reason.loc[mask.fillna(True) & reason.eq('')] = label

    reject(out.pickup_datetime.isna() | out.dropoff_datetime.isna(), 'invalid_timestamp')
    reject(pickup_localized.isna() | dropoff_localized.isna(), 'nonexistent_dst_hour')
    reject((out.pickup_datetime < start) | (out.pickup_datetime >= end), 'out_of_month')
    reject(~out.duration_minutes.gt(0) | out.duration_minutes.gt(1440), 'invalid_duration')
    reject(~out.pickup_location_id.isin(zone_ids) | ~out.dropoff_location_id.isin(zone_ids), 'unknown_zone')
    reject(~np.isfinite(out.trip_distance) | (out.trip_distance <= 0), 'invalid_trip_distance')
    for name in ('fare_amount', 'total_amount'):
        values = out[name]
        reject(~np.isfinite(values) | (values < 0.005) | (values >= 999999999999.99), 'invalid_' + name)
    reject(out.trip_distance > 300, 'distance_over_300_miles')
    reject((out.trip_distance / out.duration_minutes * 60) > 100, 'speed_over_100_mph')

    for name, upper in (('passenger_count', 9), ('payment_type', 6)):
        values = out[name]
        out.loc[~values.between(0, upper) | values.mod(1).ne(0), name] = np.nan
    out.loc[~out.tip_amount.between(0, 999999999999.98), 'tip_amount'] = np.nan
    rejected = out.loc[reason.ne(''), ['source_row']].copy()
    rejected['reason'] = reason[reason.ne('')]
    return out.loc[reason.eq(''), COLUMNS], rejected
