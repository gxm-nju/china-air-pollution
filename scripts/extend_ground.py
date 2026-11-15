"""Verified station files -> common roster -> station records, city-hours, episodes and holiday coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from ground import YRD
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'多源数据与实验'
OUT=ROOT/'扩展实验'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def make_roster(active):
    a=pd.read_csv(ROOT/'data/cleaned/stations.csv').rename(columns={'Station_name_Chinese':'name_old','city':'city_old','lon':'lon_old','lat':'lat_old'})
    b=pd.read_csv(BASE/'data/cleaned/station_grid.csv').rename(columns={'station_id':'station','city':'city_new','longitude':'lon_new','latitude':'lat_new'})
    m=pd.DataFrame({'station':sorted(active)}).merge(a,on='station',how='left',validate='one_to_one').merge(b,on='station',how='left',validate='one_to_one')
    old=m.city_old; new=m.city_new.str.removesuffix('市')
    cross=pd.read_csv(ROOT/'docs/历史名录地级归并.csv')
    alias=dict(zip(cross['历史名称'],cross['研究口径']))
    # Apply unambiguous full prefecture names learned from overlapping roster IDs.
    for label,g in m.dropna(subset=['city_old','city_new']).groupby('city_old'):
        options=set(g.city_new.str.removesuffix('市'))
        fits=[name for name in options if name.startswith(label.removesuffix('州')) and name.endswith('自治州')]
        if len(fits)==1:alias.setdefault(label,fits[0])
    adj=old.replace(alias).str.replace(r'(州|地区)$','',regex=True)
    eq=pd.Series([bool(o and n and (n==o or n.startswith(o))) if isinstance(o,str) and isinstance(n,str) else False for o,n in zip(adj,new)],index=m.index)
    conflict=old.notna()&new.notna()&~eq
    m['city']=new.combine_first(old.replace(alias)).mask(conflict)
    m['coord_diff_km']=np.hypot((m.lon_old-m.lon_new)*111.32*np.cos(np.deg2rad((m.lat_old+m.lat_new)/2)),(m.lat_old-m.lat_new)*110.57)
    m['lon']=m.lon_new.combine_first(m.lon_old);m['lat']=m.lat_new.combine_first(m.lat_old)
    m['status']=np.select([conflict,old.notna()&new.notna(),new.notna(),old.notna()],['城市冲突暂缓','双表可归并','仅归档名录','仅试验名录'],default='无匹配')
    return m
def file_dates(start,end):
    files={};ledger=[]
    for parent in (ROOT/'data/raw/air',BASE/'data/raw/ground'):
        for p in sorted(parent.glob('china_sites_*.csv')):
            day=pd.to_datetime(p.stem[-8:],format='%Y%m%d');h=sha(p)
            if day in files and sha(files[day])!=h:raise ValueError(f'同日文件内容冲突 {day}')
            if start<=day<end:files[day]=p;ledger.append((day,p.relative_to(ROOT),p.stat().st_size,h))
    return files,pd.DataFrame(ledger,columns=['date','path','bytes','sha256'])
def main(start,end,out):
    out.mkdir(exist_ok=True,parents=True);(out/'有效站点观测').mkdir(exist_ok=True)
    files,ledger=file_dates(start,end);ledger.to_csv(out/'地面文件校验.csv',index=False)
    if not files:raise ValueError('所选日期没有已校验的站点文件')
    active=set()
    for p in files.values():
        with p.open(encoding='utf-8-sig') as f:active.update(f.readline().strip().split(',')[3:])
    m=make_roster(active);m.to_csv(out/'站点匹配明细.csv',index=False)
    mapped=m[m.city.notna()].set_index('station')
    allhours=[];qc=[]
    for day,p in sorted(files.items()):
        w=pd.read_csv(p); assert w.date.astype(str).eq(day.strftime('%Y%m%d')).all() and w.hour.between(0,23).all() and not w.duplicated(['hour','type']).any()
        cols=mapped.index.intersection(w.columns,sort=False)
        times=pd.date_range(day,periods=24,freq='h');obs={};neg=0;missing=0
        for pollutant in ['PM2.5','NO2']:
            v=w.loc[w.type.eq(pollutant)].set_index('hour')[cols].reindex(range(24))
            neg+=int((v<0).sum().sum());missing+=int(v.isna().sum().sum())
            v=v.mask(v<0);v.index=times;obs[pollutant]=v
        station=pd.concat({k:v.rename_axis(index='time',columns='station').stack(future_stack=True) for k,v in obs.items()},axis=1).dropna(how='all').reset_index()
        station.to_parquet(out/'有效站点观测'/f'{day:%Y%m%d}.parquet',index=False)
        c=station.join(mapped.city,on='station').groupby(['time','city'])
        city=c[['PM2.5','NO2']].mean().join(c[['PM2.5','NO2']].count().add_prefix('n_')).reset_index()
        allhours.append(city);qc.append([day,len(w),len(cols),len(cols)*48,missing,neg,len(station),len(city)])
    hours=pd.concat(allhours,ignore_index=True);hours.to_parquet(out/'全国城市小时.parquet',index=False)
    pd.DataFrame(qc,columns=['date','source_rows','mapped_columns','possible_station_hours_two_fields','missing_before_negative_filter','negative','station_hours_with_any_field','city_hours_with_any_field']).to_csv(out/'逐日质量.csv',index=False)
    days=hours.groupby(['city',hours.time.dt.normalize().rename('date')]).agg(pm25=('PM2.5','mean'),valid_hours=('PM2.5','count'),no2=('NO2','mean')).reset_index()
    days['qualified']=days.valid_hours>=20;days['heavy']=days.qualified & (days.pm25>150);days['yrd41']=days.city.isin(YRD);days.to_parquet(out/'全国城市日.parquet',index=False)
    high=days[days.heavy].sort_values(['city','date']).copy()
    high['event']=(high.city.ne(high.city.shift())|high.date.diff().ne(pd.Timedelta(days=1))).cumsum()
    ev=high.groupby(['city','event']).agg(start=('date','min'),end=('date','max'),days=('date','size'),peak_PM25=('pm25','max')).reset_index()
    qualified=set(zip(days.loc[days.qualified,'city'],days.loc[days.qualified,'date']))
    for side,gap in [('start',-1),('end',1)]:ev[side+'_unknown']=[(c,t+pd.Timedelta(days=gap)) not in qualified for c,t in zip(ev.city,ev[side])]
    ev['yrd41']=ev.city.isin(YRD);ev.to_csv(out/'全国重污染过程.csv',index=False)
    cov=pd.DataFrame({'date':pd.date_range(start,end,inclusive='left')});cov['ground']=cov.date.isin(files)
    cal=pd.read_csv(BASE/'data/cleaned/spring_calendar.csv',parse_dates=['date']);cov=cov.merge(cal,on='date',how='left',validate='one_to_one')
    cov['winter']=cov.date.dt.month.isin([12,1,2]);festive=set(t+pd.Timedelta(days=k) for t in cov.loc[cov.spring_break.fillna(False),'date'] for k in range(-7,8))
    cov['priority']=np.select([cov.date.isin(festive),cov.winter],[1,2],default=3)
    cov['url']='https://quotsoft.net/air/data/china_sites_'+cov.date.dt.strftime('%Y%m%d')+'.csv'
    cov.sort_values(['priority','date']).to_csv(out/'逐日补采队列.csv',index=False)
    stats=[]
    for k,g in [('全部',days),('2023年归档日期',days[days.date.dt.year.eq(2023)]),('2024年10月',days[days.date.between('2024-10-01','2024-10-31')])]:
        for area,z in [('全国',g),('长三角41城',g[g.yrd41]),('南京',g[g.city.eq('南京')])]:
            q=z[z.qualified];stats.append([k,area,len(q),q.city.nunique(),int(q.heavy.sum()),q.pm25.max()])
    pd.DataFrame(stats,columns=['样本','区域','合格城市日','有合格记录城市数','重污染城市日','最高城市日均PM25']).to_csv(out/'地面结果分组.csv',index=False)
    yr=days[days.yrd41 & days.qualified].merge(cal,on='date')
    spring=[]
    for y in range(start.year,(end-pd.Timedelta(days=1)).year+1):
        hol=cal[(cal.date.dt.year==y)&cal.spring_break]
        if hol.empty:continue
        for label,lo,hi in [('节前7日',hol.date.min()-pd.Timedelta(days=7),hol.date.min()-pd.Timedelta(days=1)),('春节假期',hol.date.min(),hol.date.max()),('节后7日',hol.date.max()+pd.Timedelta(days=1),hol.date.max()+pd.Timedelta(days=7))]:
            g=yr[yr.date.between(lo,hi)];spring.append([y,label,lo,hi,(hi-lo).days+1,g.date.nunique(),len(g),g.pm25.mean(),g.heavy.sum() if len(g) else np.nan])
    pd.DataFrame(spring,columns=['年','窗口','起','止','应有日期数','实有日期数','长三角合格城市日','平均PM25','重污染城市日']).to_csv(out/'春节比较.csv',index=False)
    print(json.dumps(dict(start=str(start.date()),end_exclusive=str(end.date()),files=len(files),missing=len(cov)-len(files),active=len(active),mapped=len(mapped),cities=hours.city.nunique(),city_hours=len(hours),events=len(ev),yrd_events=int(ev.yrd41.sum()),map_status=m.status.value_counts().to_dict()),ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',default='2023-01-01');p.add_argument('--end-exclusive',default='2026-01-01');p.add_argument('--out',type=Path,default=OUT/'跨期分析');a=p.parse_args()
    main(pd.Timestamp(a.start),pd.Timestamp(a.end_exclusive),a.out)
