"""Silver is transient: batch DataFrames only, no files or database relations."""
import numpy as np
import pandas as pd
REQUIRED = ['tpep_pickup_datetime','tpep_dropoff_datetime','PULocationID','DOLocationID',
            'trip_distance','fare_amount','total_amount']
COLUMNS = ['data_month','source_row','pickup_datetime','dropoff_datetime','pickup_hour',
           'pickup_location_id','dropoff_location_id','passenger_count','trip_distance',
           'fare_amount','tip_amount','total_amount','duration_minutes','payment_type','dst_ambiguous']
def clean_batch(raw, month, offset, zone_ids):
    missing = set(REQUIRED)-set(raw.columns)
    if missing: raise ValueError(f'Missing required columns: {sorted(missing)}')
    out = pd.DataFrame(index=raw.index)
    out['data_month'] = pd.Timestamp(month+'-01').date()
    out['source_row'] = np.arange(offset+1,offset+len(raw)+1)
    out['pickup_datetime'] = pd.to_datetime(raw.tpep_pickup_datetime,errors='coerce')
    out['dropoff_datetime'] = pd.to_datetime(raw.tpep_dropoff_datetime,errors='coerce')
    out['pickup_hour'] = out.pickup_datetime.dt.floor('h')
    for dest,source in [('pickup_location_id','PULocationID'),('dropoff_location_id','DOLocationID'),
        ('passenger_count','passenger_count'),('trip_distance','trip_distance'),('fare_amount','fare_amount'),
        ('tip_amount','tip_amount'),('total_amount','total_amount'),('payment_type','payment_type')]:
        out[dest] = pd.to_numeric(raw[source],errors='coerce') if source in raw else np.nan
    out['duration_minutes']=(out.dropoff_datetime-out.pickup_datetime).dt.total_seconds()/60
    # TLC wall-clock timestamps cannot identify which occurrence of the DST overlap a trip used.
    localized=out.pickup_datetime.dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT')
    out['dst_ambiguous']=localized.isna() & out.pickup_datetime.notna()
    reason=pd.Series('',index=raw.index)
    def reject(mask,label):
        reason.loc[mask.fillna(True) & reason.eq('')]=label
    start=pd.Timestamp(month+'-01');end=start+pd.offsets.MonthBegin(1)
    reject(out.pickup_datetime.isna()|out.dropoff_datetime.isna(),'invalid_timestamp')
    reject(out.pickup_datetime.dt.tz_localize('America/New_York',ambiguous=True,nonexistent='NaT').isna() & out.pickup_datetime.notna(),'nonexistent_dst_hour')
    reject((out.pickup_datetime<start)|(out.pickup_datetime>=end),'out_of_month')
    reject((out.duration_minutes<=0)|(out.duration_minutes>1440),'invalid_duration')
    reject(~out.pickup_location_id.isin(zone_ids)|~out.dropoff_location_id.isin(zone_ids),'unknown_zone')
    for col in ['trip_distance','fare_amount','total_amount']:
        reject(~np.isfinite(out[col])|(out[col]<=0), 'invalid_'+col)
    reject(out.trip_distance>300,'distance_over_300_miles')
    reject((out.trip_distance/out.duration_minutes*60)>100,'speed_over_100_mph')
    # Optional values remain NULL when unavailable; cash tips are not fully reported by TLC.
    out.loc[~out.passenger_count.between(0,9)|out.passenger_count.mod(1).ne(0),'passenger_count']=np.nan
    out.loc[~out.payment_type.between(0,6)|out.payment_type.mod(1).ne(0),'payment_type']=np.nan
    out.loc[~np.isfinite(out.tip_amount)|(out.tip_amount<0),'tip_amount']=np.nan
    rejected=out.loc[reason.ne(''),['source_row']].copy()
    rejected['reason']=reason[reason.ne('')]
    return out.loc[reason.eq(''),COLUMNS], rejected
