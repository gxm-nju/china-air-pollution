"""生成 FIRMS 地方时、0.01 度 × 30 分钟近似去重事件表及质量核算。"""
from pathlib import Path
import hashlib
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN, OUT = [ROOT / p for p in ('data/raw/firms','data/cleaned','results')]
RNG = np.random.default_rng(20261115)

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def prepare(path):
    sensor, yearly, _ = path.stem.split('_')
    cols = ['latitude','longitude','acq_date','acq_time','confidence','type','frp']
    x = pd.read_csv(path,usecols=cols)
    conf = pd.to_numeric(x.confidence, errors='coerce').between(30,100) if sensor=='modis' else x.confidence.isin(['n','h'])
    hh, mm = x.acq_time//100, x.acq_time%100
    dt = pd.to_datetime(x.acq_date,format='%Y-%m-%d',errors='coerce') + pd.to_timedelta(hh+8,unit='h') + pd.to_timedelta(mm,unit='min')
    valid = x.latitude.between(-90,90) & x.longitude.between(-180,180) & hh.between(0,23) & mm.between(0,59) & dt.notna()
    kept = valid & conf & x.type.eq(0)
    inside = kept & (dt >= '2019-01-01') & (dt < '2026-01-01')
    static = x.loc[valid & conf & x.type.eq(2),['latitude','longitude']].copy()
    static['lat_bin'] = np.floor(static.latitude*100).astype('int32')
    static['lon_bin'] = np.floor(static.longitude*100).astype('int32')
    static = static.value_counts(['lat_bin','lon_bin']).rename('static_detections')
    y = pd.DataFrame(dict(local_slot=dt[inside].dt.floor('30min'),
        lat_bin=np.floor(x.loc[inside,'latitude']*100).astype('int32'),
        lon_bin=np.floor(x.loc[inside,'longitude']*100).astype('int32'),
        frp_mw=x.frp[inside].where(x.frp[inside]>=0)))
    audit = dict(sensor=sensor,utc_year=int(yearly),raw=len(x),invalid_time_coord=int((~valid).sum()),
                 low_or_invalid_confidence=int((valid & ~conf).sum()),other_type=int((valid & conf & x.type.ne(0)).sum()),
                 static_type2_before_exclusion=int((valid & conf & x.type.eq(2)).sum()),
                 outside_local_period=int((kept & ~inside).sum()),retained=int(inside.sum()),
                 utc_days_with_any_detection=x.acq_date.nunique())
    assert sum(audit[k] for k in ['invalid_time_coord','low_or_invalid_confidence','other_type','outside_local_period','retained'])==len(x)
    return y, static, audit

def main():
    target = CLEAN / 'fire_events'
    target.mkdir(exist_ok=True)
    manifest=pd.read_csv(ROOT/'logs/fire_downloads.csv').set_index('file')
    assert len(manifest)==21
    daily=[]; audits=[]; static=[]; samples=[]
    for year in range(2019,2026):
        inputs=sorted(RAW.glob(f'*_{year}_China.csv'))
        assert len(inputs)==3
        parts=[]
        for p in inputs:
            assert p.stat().st_size==manifest.loc[p.name,'bytes'] and sha(p)==manifest.loc[p.name,'sha256'],p
            y, st, audit = prepare(p)
            parts.append(y); static.append(st); audits.append(audit)
        obs=pd.concat(parts,ignore_index=True)
        # UTC 年份在北京时间上午 8 时切换，30 分钟格从不会跨两个 UTC 年文件。
        events=(obs.groupby(['local_slot','lat_bin','lon_bin'],sort=True,as_index=False)
                  .agg(detections=('frp_mw','size'),max_frp_mw=('frp_mw','max')))
        rowkey=RNG.random(len(events))
        sample=events.iloc[np.argsort(rowkey)[:200]].copy()
        sample['random_key']=np.sort(rowkey)[:200]; samples.append(sample)
        events.to_csv(target/f'utc_{year}.csv.gz',index=False,compression={'method':'gzip','compresslevel':2,'mtime':0})
        for label,part in [('全国',events),('华东矩形',events[events.lat_bin.between(2700,3499)&events.lon_bin.between(11400,12299)])]:
            counts=part.groupby(part.local_slot.dt.normalize()).agg(unique_slots=('detections','size'),detections=('detections','sum')).reset_index(names='date')
            counts['area']=label; daily.append(counts)
        print(year,len(obs),len(events),flush=True)
    audit=pd.DataFrame(audits); audit.to_csv(OUT/'fire_filter_counts.csv',index=False)
    heat=pd.concat(static).groupby(level=[0,1]).sum().sort_values(ascending=False)
    heat.to_csv(CLEAN/'fixed_heat_sources.csv.gz',compression={'method':'gzip','compresslevel':2,'mtime':0})
    sample=pd.concat(samples).nsmallest(200,'random_key').drop(columns='random_key')
    sample['latitude_center']=(sample.lat_bin+0.5)/100
    sample['longitude_center']=(sample.lon_bin+0.5)/100
    sample['manual_review']='待人工地图复核'
    sample.to_csv(OUT/'fire_map_sample_200.csv',index=False)
    dates=pd.date_range('2019-01-01','2025-12-31')
    observed=pd.concat(daily).groupby(['date','area'])[['unique_slots','detections']].sum()
    daily=observed.reindex(pd.MultiIndex.from_product([dates,['全国','华东矩形']],names=['date','area']),fill_value=0).reset_index()
    daily.to_csv(OUT/'fire_daily.csv',index=False)
    daily['week_start']=daily.date-pd.to_timedelta(daily.date.dt.dayofweek,unit='d')
    daily['year']=daily.date.dt.year
    week=daily.groupby(['area','year','week_start'],as_index=False).agg(unique_slots=('unique_slots','sum'),detections=('detections','sum'),days_in_window=('date','size'))
    week.to_csv(OUT/'fire_weekly.csv',index=False)
    week.sort_values('unique_slots',ascending=False).groupby(['area','year']).head(1).sort_values(['area','year']).to_csv(OUT/'fire_peak_weeks.csv',index=False)
    country=daily.loc[daily.area=='全国']
    assert country.detections.sum()==audit.retained.sum()
    (OUT/'fire_summary.json').write_text(json.dumps(dict(files=len(audit),bytes=int(manifest.bytes.sum()),raw=int(audit.raw.sum()),retained=int(audit.retained.sum()),unique=int(country.unique_slots.sum()),static_type2=int(audit.static_type2_before_exclusion.sum()),fixed_cells=len(heat)),indent=2))
if __name__=='__main__':
    main()
