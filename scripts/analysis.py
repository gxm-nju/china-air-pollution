"""Three pilot questions, cross-source tables, lag validation and clustering."""
import json
import argparse
from pathlib import Path
import itertools
import math
import numpy as np
import pandas as pd
import duckdb
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.metrics import mean_absolute_error,r2_score,silhouette_score
from ground import CL,IN,OUT,RAW,YRD,ROOT
AIR_INPUT=IN/"all_city_hour.parquet"
SAT_INPUT=CL/"satellite_city_orbit.parquet"
WEATHER_INPUT=CL
FIRE_INPUT=CL/"firms"
START=END=HOURS=None
def get_facts():
    conn=duckdb.connect()
    air=conn.execute('SELECT * FROM read_parquet(?) WHERE time_bjt>=? AND time_bjt<?',[str(AIR_INPUT),START,END]).df()
    weather=pd.read_parquet(WEATHER_INPUT/'city_weather.parquet')
    coords=pd.read_csv(CL/'cities.csv').set_index('city').loc[YRD].reset_index()
    basis=pd.MultiIndex.from_product([YRD,HOURS],names=['city','time_bjt']).to_frame(index=False)
    z=basis.merge(air,on=['city','time_bjt'],how='left',validate='one_to_one').merge(weather,on=['city','time_bjt'],how='left',validate='one_to_one')
    z=z.merge(pd.read_csv(CL/'osm/city.csv'),how='left',on='city',validate='many_to_one')
    z['national_day_holiday']=z.time_bjt.between('2024-10-01','2024-10-08',inclusive='left').where(z.time_bjt.dt.year.eq(2024))
    sat=pd.read_parquet(SAT_INPUT)
    satday=sat.groupby(['city','date']).agg(no2_column_daily=('no2_mol_m2','mean'),valid_sat_pixels=('valid_pixels','sum')).reset_index()
    z['date']=z.time_bjt.dt.normalize()
    # Daily attributes do not indicate satellite observations in every hour.
    z=z.merge(satday,how='left',on=['city','date'],validate='many_to_one')
    return air,z,coords
def compare_fires(z,coords):
    keys=['time_bjt','gx','gy','u10','v10','speed_ms']
    files=sorted((WEATHER_INPUT/'era5').glob('*/grid.parquet'))
    weather=pd.concat([pd.read_parquet(q,columns=keys,filters=[('time_bjt','>=',START),('time_bjt','<',END),('gx','>=',114.),('gx','<=',124.),('gy','>=',27.),('gy','<=',36.)]) for q in files],ignore_index=True)
    if weather.empty:raise ValueError('所选时期无火点网格风场')
    years=range((START-pd.Timedelta(hours=8)).year,(END-pd.Timedelta(hours=8,microseconds=1)).year+1)
    sources=[FIRE_INPUT/f'year={y}'/'events.parquet' for y in years]
    if not all(q.exists() for q in sources):raise ValueError(f'缺少所选 UTC 年火点事件分区 {sources}')
    fires=pd.concat([pd.read_parquet(q,filters=[('time_bjt','>=',START),('time_bjt','<',END)]) for q in sources],ignore_index=True)
    fires=fires[~fires.recurring_heat_flag&fires.gx.between(114,124)&fires.gy.between(27,36)&fires.time_bjt.between(START,END,inclusive='left')].copy()
    fires['time_bjt']=fires.time_bjt.dt.floor('h')
    groups=fires.groupby(['time_bjt','gx','gy']).size().rename('n_fire_events').reset_index()
    groups=groups.merge(weather[['time_bjt','gx','gy','u10','v10','speed_ms']],how='left',on=['time_bjt','gx','gy'],validate='one_to_one')
    # Compare dates in the top quartile of observed regional fire counts, using all 31 days.
    counts=fires.groupby(fires.time_bjt.dt.normalize()).size().reindex(HOURS.normalize().unique(),fill_value=0)
    cutoff=float(counts.quantile(.75))
    groups['fire_dense_day']=groups.time_bjt.dt.normalize().map(counts).ge(cutoff)
    group_records=[];values=[]
    pm=z.pivot(index='time_bjt',columns='city',values='PM2.5')
    names=coords.city.to_numpy();long=coords.lon.to_numpy();lat=coords.lat.to_numpy()
    for gi,e in enumerate(groups.itertuples()):
        if not np.isfinite(e.speed_ms) or e.speed_ms<1:continue
        dx=(long-e.gx)*111.32*np.cos(np.deg2rad((lat+e.gy)/2));dy=(lat-e.gy)*110.57;r=np.hypot(dx,dy)
        align=(dx*e.u10+dy*e.v10)/np.maximum(r*e.speed_ms,1e-10)
        nearby=(r>=25)&(r<=180)
        down=np.flatnonzero(nearby&(align>=np.cos(np.pi/4)));up=np.flatnonzero(nearby&(align<=-np.cos(np.pi/4)))
        options=[(abs(r[d]-r[u]),r[d]+r[u],d,u) for d in down for u in up if abs(r[d]-r[u])<=50]
        if not options:continue
        _,_,d,u=min(options);dn,un=names[d],names[u];h=e.time_bjt
        baseline=(pm[dn]-pm[un]).reindex(pd.date_range(h-pd.Timedelta(hours=6),h-pd.Timedelta(hours=1),freq='h')).dropna()
        group_records.append((gi,h,e.gx,e.gy,e.n_fire_events,e.speed_ms,dn,un,r[d],r[u],e.fire_dense_day,len(baseline)))
        if len(baseline)<4 or not e.fire_dense_day:continue
        for lag in range(49):
            at=h+pd.Timedelta(hours=lag)
            if at not in pm.index:continue
            diff=pm.at[at,dn]-pm.at[at,un]
            if np.isfinite(diff):values.append((gi,lag,diff,diff-baseline.mean(),h.normalize()))
    cols=['fire_group','time_bjt','gx','gy','fires','wind_ms','down_city','up_city','down_km','up_km','dense_day','baseline_hours']
    pairs=pd.DataFrame(group_records,columns=cols);v=pd.DataFrame(values,columns=['fire_group','lag_h','pm_difference','adjusted_difference','fire_date'])
    pairs.to_parquet(IN/'fire_city_pairs.parquet',index=False);v.to_parquet(IN/'fire_lags.parquet',index=False)
    summ=v.groupby('lag_h').agg(pairs=('fire_group','nunique'),days=('fire_date','nunique'),mean_diff=('pm_difference','mean'),mean_adjusted=('adjusted_difference','mean'),median_adjusted=('adjusted_difference','median')).reset_index()
    summ.to_csv(OUT/'Q1_火点与下风向浓度.csv',index=False)
    counts.rename('fires').to_csv(OUT/'fire_daily.csv',index_label='date')
    fexp=pairs.groupby(['down_city','time_bjt']).fires.sum().rename('matched_upwind_fire_events').reset_index().rename(columns={'down_city':'city'})
    return z.merge(fexp,on=['city','time_bjt'],how='left',validate='one_to_one'),{'regional_fire_events':len(fires),'grid_hour_groups':len(groups),'matched_pairs':len(pairs),'dense_day_cutoff':cutoff,'dense_days':int((counts>=cutoff).sum()),'lag0_pairs':int(summ.iloc[0].pairs) if len(summ) else 0}
def sat_reg(z):
    sat=pd.read_parquet(SAT_INPUT).dropna(subset=['no2_mol_m2'])
    sat=sat[sat.date.between(START.normalize(),END,inclusive='left')]
    if sat.empty:
        (OUT/'Q2_无可用轨道.txt').write_text('本窗口没有有效L2轨道。')
        return
    catalogs=list((RAW/'s5p').glob('*catalog*.json'))
    meta={x['Name'][:-3]:x['ContentDate'] for c in catalogs for x in json.loads(c.read_text())['value']}
    scenarios=[]
    for row in sat.itertuples():
        if pd.notna(getattr(row,'pixel_time_bjt',pd.NaT)) and row.timed_valid_pixels>0:
            scenarios.append(dict(city=row.city,time_bjt=row.pixel_time_bjt.round('h'),date=row.date,orbit=row.orbit,scenario='matched_pixel_time',satellite_umol_m2=row.timed_column*1e6,valid_pixels=row.timed_valid_pixels))
        if row.orbit not in meta:continue
        utc=meta[row.orbit];win=[pd.to_datetime(utc[k],utc=True).tz_convert('Asia/Shanghai').tz_localize(None).floor('h') for k in ['Start','End']]
        for scenario,h in zip(['orbit_start_hour','orbit_end_hour'],win):
            scenarios.append(dict(city=row.city,time_bjt=h,date=row.date,orbit=row.orbit,scenario=scenario,satellite_umol_m2=row.no2_mol_m2*1e6,valid_pixels=row.valid_pixels))
    if not scenarios:
        (OUT/'Q2_无可用轨道.txt').write_text('本窗口缺少可对齐的轨道时间和像元时间。')
        return
    v=pd.DataFrame(scenarios).merge(z.drop(columns='date'),on=['city','time_bjt'],how='left',validate='many_to_one')
    v.to_csv(OUT/'Q2_卫星与地面配对.csv',index=False)
    results=[]
    sets={'柱浓度':['satellite_umol_m2'],'加风速和边界层':['satellite_umol_m2','blh_m','speed_ms'],'再加OSM':['satellite_umol_m2','blh_m','speed_ms','road_km_per_km2','industrial_fraction']}
    for sc,g in v.groupby('scenario'):
        common=g.dropna(subset=sets['再加OSM']+['NO2'])
        for name,cols in sets.items():
            if common.city.nunique()<6: continue
            pred=cross_val_predict(make_pipeline(StandardScaler(),Ridge(alpha=1)),common[cols],common.NO2,groups=common.city,cv=LeaveOneGroupOut())
            results.append(dict(scenario=sc,model=name,n=len(common),cities=common.city.nunique(),MAE_ug_m3=mean_absolute_error(common.NO2,pred),R2_heldout=r2_score(common.NO2,pred)))
    pd.DataFrame(results).to_csv(OUT/'Q2_回归敏感性.csv',index=False)
def extremes(air,z):
    daily=air.groupby(['city',air.time_bjt.dt.normalize().rename('date')])['PM2.5'].agg(pm25_day='mean',valid_hours='count').reset_index()
    daily['qualified']=daily.valid_hours.ge(20);daily['above150']=daily.qualified & daily.pm25_day.gt(150)
    daily.to_parquet(IN/'city_days.parquet',index=False)
    high=daily[daily.above150].sort_values(['city','date']).copy()
    new=high.city.ne(high.city.shift())|high.date.diff().ne(pd.Timedelta(days=1));high['event_id']=new.cumsum()
    events=high.groupby(['event_id','city']).agg(start=('date','min'),end=('date','max'),days=('date','size'),peak_daily_pm25=('pm25_day','max')).reset_index()
    events['yrd']=events.city.isin(YRD);events.to_csv(OUT/'Q3_重污染过程.csv',index=False)
    d=z.groupby(['city','date']).agg(blh_m=('blh_m','mean'),speed_ms=('speed_ms','mean'),weather_hours=('blh_m','count'),NO2=('NO2','mean')).reset_index().merge(daily,on=['city','date'])
    d=d[d.qualified&d.weather_hours.ge(20)].dropna(subset=['blh_m','speed_ms','pm25_day']).copy()
    if len(d)<3 or d[['blh_m','speed_ms','pm25_day']].drop_duplicates().shape[0]<3:
        return {'national_exceedances':len(high),'national_episodes':len(events),'yrd_exceedances':int(high.city.isin(YRD).sum()),'cluster_n':0}
    features=['blh_m','speed_ms','pm25_day'];scaled=StandardScaler().fit_transform(d[features]);model=KMeans(n_clusters=3,n_init=20,random_state=42).fit(scaled)
    d['cluster']=model.labels_;d.to_parquet(IN/'exploratory_city_days.parquet',index=False)
    d.groupby('cluster')[features].agg(['size','mean']).to_csv(OUT/'探索性城市日聚类.csv')
    return {'qualified_national_days':int(daily.qualified.sum()),'national_exceedances':len(high),'national_episodes':len(events),'yrd_qualified':int(daily[daily.city.isin(YRD)].qualified.sum()),'yrd_exceedances':int(high.city.isin(YRD).sum()),'nanjing_max':float(daily[daily.city.eq('南京')&daily.qualified].pm25_day.max()),'cluster_n':len(d),'cluster_silhouette':float(silhouette_score(scaled,model.labels_,sample_size=min(len(d),5000),random_state=42) if len(d)>3 else np.nan)}
def net(z,coords):
    # Candidate edges are screened on early days and validated on later days on disjoint observations.
    pm=z.pivot(index='time_bjt',columns='city',values='PM2.5').reindex(HOURS).diff()
    xy=coords.set_index('city')
    split=round(len(HOURS)*20/31)
    wind=z.set_index(['city','time_bjt']).sort_index();rows=[]
    for src,dst in itertools.permutations(YRD,2):
        a,b=xy.loc[src],xy.loc[dst]
        dx=(b.lon-a.lon)*111.32*math.cos(math.radians((a.lat+b.lat)/2));dy=(b.lat-a.lat)*110.57;r=math.hypot(dx,dy)
        if not 25<=r<=180:continue
        w=wind.loc[dst];ok=((dx*w.u10+dy*w.v10)>=r*w.speed_ms*np.cos(np.pi/4))&w.speed_ms.ge(1)
        x=pm[src].to_numpy();y=pm[dst].to_numpy(); h=np.arange(len(x))
        def stat(lag,test):
            keep=ok.to_numpy()&(h>=lag)&((h>=split+lag) if test else (h<split))
            xx=np.roll(x,lag);keep&=np.isfinite(xx)&np.isfinite(y);n=int(keep.sum())
            return (float(np.corrcoef(xx[keep],y[keep])[0,1]) if n>=24 and np.std(xx[keep])>0 and np.std(y[keep])>0 else np.nan,n)
        train=[stat(l,False)[0] for l in range(1,13)]
        if not np.isfinite(train).any():continue
        lag=int(np.nanargmax(train))+1;te,nn=stat(lag,True);zero,_=stat(0,True)
        rows.append(dict(upstream=src,downstream=dst,distance_km=r,lag_h=lag,train_r=train[lag-1],test_r=te,test_n=nn,test_zero_lag_r=zero,retained=bool(train[lag-1]>=.25 and te>=.25 and te>zero+.02)))
    pd.DataFrame(rows).to_csv(OUT/'Q3_风向滞后关联边.csv',index=False)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description='重算已准备的试验数据；结束日期不包含在窗口内')
    parser.add_argument('--start',type=pd.Timestamp);parser.add_argument('--end-exclusive',type=pd.Timestamp)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--weather-dir',type=Path,default=CL)
    parser.add_argument('--fire-dir',type=Path,default=CL/'firms')
    parser.add_argument('--air-input',type=Path,default=AIR_INPUT)
    parser.add_argument('--sat-input',type=Path,default=SAT_INPUT)
    a=parser.parse_args();SAT_INPUT=a.sat_input
    t=pd.read_parquet(a.air_input,columns=['time_bjt']).time_bjt
    START=a.start if a.start is not None else t.min().normalize()
    END=a.end_exclusive if a.end_exclusive is not None else t.max().normalize()+pd.Timedelta(days=1)
    if START>=END:parser.error('结束日期须晚于起始日期')
    HOURS=pd.date_range(START,END,inclusive='left',freq='h')
    WEATHER_INPUT,FIRE_INPUT,AIR_INPUT=a.weather_dir,a.fire_dir,a.air_input
    OUT=a.output_dir or ROOT/'扩展实验'/f'窗口_{START:%Y%m%d}_{END:%Y%m%d}'
    if OUT.resolve()==(ROOT/'results').resolve():parser.error('输出目录须独立于原10月结果')
    IN=OUT/'integrated';IN.mkdir(parents=True,exist_ok=True)
    air,z,coords=get_facts();z,summary=compare_fires(z,coords);z.to_parquet(IN/'yrd_city_hour.parquet',index=False)
    sat_reg(z);summary.update(extremes(air,z));net(z,coords)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
