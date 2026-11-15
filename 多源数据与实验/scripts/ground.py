"""逐站小时原档 → 城市小时、城市日、连续重污染过程及春节窗口。"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW,CLEAN,JOIN,OUT=(ROOT/p for p in ('data/raw','data/cleaned','data/integrated','results'))
METRICS={'PM2.5':'pm25','PM10':'pm10','NO2':'no2'}

def write(frame,path):
    frame.to_csv(path,index=False,float_format='%.5f')
def main():
    roster=pd.read_csv(RAW/'station_roster.csv').set_index('station_id')
    roster['city']=roster.city.str.replace('市$','',regex=True)
    scope=pd.read_csv(CLEAN/'city_month_scope.csv').city.unique()
    manifest=pd.read_csv(ROOT/'logs/ground_downloads.csv').set_index('file')
    city_hours=[]; audits=[]; station_ids=set(); kept_ids=set(); pm_frames=[]
    for p in sorted((RAW/'ground').glob('*.csv')):
        assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest.loc[p.name,'sha256']
        d=pd.read_csv(p)
        day=pd.to_datetime(p.stem[-8:],format='%Y%m%d')
        assert d.date.astype(str).eq(p.stem[-8:]).all() and d.hour.between(0,23).all()
        assert not d.duplicated(['hour','type']).any(),p
        codes=list(d.columns[3:])
        matched=roster.index.intersection(codes)
        station_ids.update(codes);kept_ids.update(matched)
        panels=[]
        for measure,name in METRICS.items():
            table=d.loc[d.type==measure].set_index('hour')[codes].reindex(range(24))
            valid=table.where(table>=0)
            vals=valid[matched]
            city=roster.loc[matched,'city']
            grouped=vals.T.groupby(city)
            mean=grouped.mean().T.stack(future_stack=True).rename(name)
            count=grouped.count().T.stack(future_stack=True).rename(name+'_n')
            panels.extend([mean,count])
            if name=='pm25':
                a=vals.copy();a.index=day+pd.to_timedelta(a.index,'h');pm_frames.append(a.astype('float32'))
            audits.append(dict(date=day,metric=name,available_stations=len(codes),matched=len(matched),n_expected=24*len(codes),nonempty_hours=int(valid.notna().any(axis=1).sum()),valid_all=int(valid.count().sum()),negative=int((table<0).sum().sum()),valid_mapped=int(vals.count().sum())))
        flat=pd.concat(panels,axis=1).reset_index()
        flat['date']=day;flat['hour_bjt']=day+pd.to_timedelta(flat.hour,'h')
        city_hours.append(flat)
    fact=pd.concat(city_hours,ignore_index=True)
    fact['yrd41']=fact.city.isin(scope)
    cal=pd.read_csv(CLEAN/'spring_calendar.csv',parse_dates=['date'])
    fact=fact.merge(cal,on='date',validate='many_to_one')
    assert not fact.duplicated(['city','hour_bjt']).any()
    write(fact,JOIN/'ground_city_hour.csv.gz')
    q=pd.DataFrame(audits);write(q,OUT/'ground_daily_qc.csv')
    missing=sorted(station_ids-kept_ids)
    write(pd.DataFrame({'station_id':missing}),OUT/'unmapped_observed_stations.csv')
    # 标记连续六小时以上同一读数，包括跨午夜；断档会断开序列。疑似平线不自动剔除。
    pm=pd.concat(pm_frames).sort_index()
    run=np.zeros(len(pm.columns),dtype=np.uint16)
    flags=np.zeros(pm.shape,dtype=bool)
    prev=np.full(len(run),np.nan);last=None
    arr=pm.to_numpy()
    for i,(t,v) in enumerate(zip(pm.index,arr)):
        if last is None or t-last!=pd.Timedelta(hours=1):
            run[:]=0;prev[:]=np.nan
        run=np.where(np.isfinite(v),np.where(v==prev,run+1,1),0)
        start=run==6
        if start.any():flags[i-5:i+1,start]=True
        flags[i,run>6]=True
        prev=v.copy();last=t
    write(pd.DataFrame({'station_id':pm.columns,'valid_pm25':np.isfinite(arr).sum(axis=0),'flat_six_hours_pm25':flags.sum(axis=0)}),OUT/'station_flatline_qc.csv')
    day=fact.groupby(['city','date','yrd41','spring_break'],as_index=False).agg(n=('pm25','count'),pm25_valid_mean=('pm25','mean'),pm10_valid_mean=('pm10','mean'),pm10_n=('pm10','count'),no2_valid_mean=('no2','mean'),no2_n=('no2','count'))
    for v,n in [('pm25','n'),('pm10','pm10_n'),('no2','no2_n')]:
        day[v]=day[v+'_valid_mean'].where(day[n]>=20)
    day['pm25_heavy']=day.pm25.gt(150).astype('boolean').where(day.pm25.notna())
    write(day,JOIN/'ground_city_day.csv.gz')
    episodes=[]
    for city,group in day.groupby('city'):
        seq=group.set_index('date').sort_index()
        dates=seq.index[seq.pm25.gt(150)]
        if dates.empty:continue
        for part in pd.Series(dates).groupby(pd.Series(dates).diff().dt.days.ne(1).cumsum()):
            times=part[1]; start,end=times.iloc[0],times.iloc[-1]
            left,right=start-pd.Timedelta(days=1),end+pd.Timedelta(days=1)
            episodes.append(dict(city=city,yrd41=city in scope,start=start,end=end,days=len(times),peak_pm25=seq.loc[times,'pm25'].max(),left_unknown=pd.isna(seq.pm25.get(left,np.nan)),right_unknown=pd.isna(seq.pm25.get(right,np.nan)),spring_break_days=int(seq.loc[times,'spring_break'].sum())))
    episodes=pd.DataFrame(episodes)
    write(episodes,JOIN/'ground_episodes.csv')
    available=set(q.date)
    coverage=cal[['date']].copy();coverage['file_validated']=coverage.date.isin(available)
    write(coverage,OUT/'ground_date_inventory.csv')
    nj=day[day.city=='南京'];write(nj,OUT/'ground_nanjing_days.csv')
    period=[]
    windows={'前7天':('2023-01-14','2023-01-20'),'春节7天':('2023-01-21','2023-01-27'),'后7天':('2023-01-28','2023-02-03')}
    for label,grp in [('南京',nj),('长三角41城',day[day.yrd41])]:
        for win,(s,e) in windows.items():
            subset=grp[grp.date.between(s,e)]
            period.append(dict(area=label,window=win,start=s,end=e,eligible_citydays=int(subset.pm25.count()),pm25_cityday_mean=subset.pm25.mean(),eligible_no2_citydays=int(subset.no2.count()),no2_cityday_mean=subset.no2.mean()))
    write(pd.DataFrame(period),OUT/'spring_2023_windows.csv')
    summary=dict(days=len(available),missing=1096-len(available),raw_bytes=int(manifest.bytes.sum()),observed_station_ids=len(station_ids),mapped_station_ids=len(kept_ids),cities=int(fact.city.nunique()),yrd_cities=int(fact.loc[fact.yrd41,'city'].nunique()),n_city_hours=len(fact),pm25_flat_hours=int(flags.sum()),valid_pm25_stationhours=int(np.isfinite(arr).sum()),episodes=len(episodes),eligible_citydays=int(day.pm25.notna().sum()),heavy_citydays=int(day.pm25.gt(150).sum()),yrd_eligible=int(day.loc[day.yrd41,'pm25'].count()),yrd_heavy=int(day.loc[day.yrd41,'pm25'].gt(150).sum()),yrd_episodes=int(episodes.yrd41.sum()),nj_heavy=int(nj.pm25.gt(150).sum()),nj_eligible=int(nj.pm25.count()),nj_peak=float(nj.pm25.max()),nj_peak_date=str(nj.loc[nj.pm25.idxmax(),'date'].date()))
    (OUT/'ground_summary.json').write_text(json.dumps(summary,indent=2))
if __name__=='__main__':
    main()
