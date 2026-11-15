"""将 ERA5、地面站、火点按真实时间与空间对齐，实施风向对照、过程聚类、滞后检验。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import haversine_distances
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
RAW,CLEAN,JOIN,OUT=(ROOT/p for p in ('data/raw','data/cleaned','data/integrated','results'))
def write(x,p):
    x.to_csv(p,index=False,float_format='%.5f')
def angle(x,y):
    return np.abs((x-y+180)%360-180)
def bearing(lat,lon,ys,xs):
    a,b,d=np.radians(lat),np.radians(ys),np.radians(xs-lon)
    return (np.degrees(np.arctan2(np.sin(d)*np.cos(b),np.cos(a)*np.sin(b)-np.sin(a)*np.cos(b)*np.cos(d)))+360)%360
def series(frame,field,times,cities):
    return frame.pivot(index='time',columns='city',values=field).reindex(index=times,columns=cities).to_numpy()
def main():
    cities=pd.read_csv(CLEAN/'case_city_grid.csv').dropna(subset='source_group').sort_values('city').reset_index(drop=True)
    names=cities.city.tolist(); coords=cities[['lat','lon']].to_numpy()
    times=pd.date_range('2023-01-01','2025-12-31 23:00',freq='h')
    path=RAW/'era5/yrd41_2023_2025.csv'
    met=pd.read_csv(path,skiprows=43,parse_dates=['time'])
    met.columns=['location_id','time','t2m_c','sp_hpa','ws_ms','wind_from_deg','blh_m']
    meta=pd.read_csv(path,nrows=41)
    assert len(met)==41*len(times) and not met.duplicated(['location_id','time']).any()
    assert meta.utc_offset_seconds.eq(28800).all() and meta.location_id.tolist()==list(range(41))
    assert np.abs(meta.latitude-cities.lat).max()<.16 and np.abs(meta.longitude-cities.lon).max()<.16
    for col in ['t2m_c','sp_hpa','ws_ms','wind_from_deg','blh_m']:
        met.loc[met[col]<=-999,col]=np.nan
    met['city']=met.location_id.map(cities.city)
    met['u10_ms']=-met.ws_ms*np.sin(np.radians(met.wind_from_deg))
    met['v10_ms']=-met.ws_ms*np.cos(np.radians(met.wind_from_deg))
    params={'latitude':','.join(cities.lat.map(str)),'longitude':','.join(cities.lon.map(str)),'hourly':'temperature_2m,surface_pressure,wind_speed_10m,wind_direction_10m,boundary_layer_height','start_date':'2023-01-01','end_date':'2025-12-31','models':'era5','wind_speed_unit':'ms','timezone':'Asia/Shanghai','cell_selection':'nearest','format':'csv'}
    (ROOT/'docs/era5_url.txt').write_text('https://archive-api.open-meteo.com/v1/archive?'+urlencode(params)+'\n')
    meta['city']=names;write(meta,CLEAN/'era5_requested_city_grid.csv')
    write(met.groupby(['city',met.time.dt.to_period('M').rename('month')])[['t2m_c','sp_hpa','ws_ms','wind_from_deg','blh_m']].count().reset_index(),OUT/'era5_coverage.csv')
    ground=pd.read_csv(JOIN/'ground_city_hour.csv.gz',parse_dates=['hour_bjt']).query('yrd41').rename(columns={'hour_bjt':'time'})
    fact=ground.merge(met,on=['city','time'],validate='one_to_one')
    write(fact,JOIN/'yrd_ground_era5_hour.csv.gz')
    nj=pd.read_csv(OUT/'nanjing_hourly.csv',parse_dates=['hour_bjt']).rename(columns={'hour_bjt':'time'})
    write(nj.merge(met[met.city=='南京'],on=['city','time'],validate='one_to_one'),JOIN/'nanjing_dust_era5_hour.csv')
    pm=series(ground,'pm25',times,names);wind=series(met,'wind_from_deg',times,names)
    speed=series(met,'ws_ms',times,names);blh=series(met,'blh_m',times,names)
    baseline=pd.DataFrame(pm).shift(1).rolling(24,min_periods=12).mean().to_numpy()
    observed_dates=ground.time.dt.floor('D').unique()
    fire=pd.read_csv(CLEAN/'fire_events/utc_2023.csv.gz',parse_dates=['local_slot'])
    fire=fire[fire.local_slot.dt.floor('D').isin(observed_dates)&fire.lat_bin.between(2650,3600)&fire.lon_bin.between(11300,12400)].copy()
    fire['time']=fire.local_slot.dt.floor('h')
    fire['lat_grid']=np.floor(((fire.lat_bin+0.5)/100)*4+0.5)/4
    fire['lon_grid']=np.floor(((fire.lon_bin+0.5)/100)*4+0.5)/4
    # 一个网格小时至少观察到两个不同的小网格，火点强度使用所有已去重时空格数。
    f=fire.groupby(['time','lat_grid','lon_grid'],as_index=False).size().rename(columns={'size':'nslots'})
    distinct=fire.drop_duplicates(['time','lat_bin','lon_bin']).groupby(['time','lat_grid','lon_grid'],as_index=False).size().rename(columns={'size':'n_spatial'})
    f=f.merge(distinct,on=['time','lat_grid','lon_grid']).query('n_spatial>=2')
    rows=[];geometries={}
    for event in f.itertuples(index=False):
        center=(event.lat_grid,event.lon_grid)
        if center not in geometries:
            dist=haversine_distances(np.radians([center]),np.radians(coords))[0]*6371
            az=bearing(*center,coords[:,0],coords[:,1])
            geometries[center]=(dist,az)
        dist,az=geometries[center]; near=int(dist.argmin())
        # 明确舍去距最近取风城市超过 50 km 的火点网格。
        if dist[near]>50:continue
        h=times.get_loc(event.time);from_deg=wind[h,near]
        if not speed[h,near]>=1:continue
        ring=(dist>=30)&(dist<=200)
        up=ring & (angle(az,from_deg)<=45)
        down=ring & (angle(az,(from_deg+180)%360)<=45)
        for lag in [0,6,12,24,48]:
            if h+lag>=len(pm):continue
            v=pm[h+lag]-baseline[h]
            a=v[up&np.isfinite(v)];b=v[down&np.isfinite(v)]
            if len(a) and len(b):
                rows.append((event.time,*center,event.nslots,lag,len(a),len(b),b.mean()-a.mean()))
    pairs=pd.DataFrame(rows,columns=['time','lat_grid','lon_grid','nslots','lag','n_up','n_down','delta_pm25'])
    write(pairs,JOIN/'fire_wind_sector_contrasts.csv.gz')
    rng=np.random.default_rng(20261115)
    def interval(z):
        groups=z.groupby(z.time.dt.normalize()).delta_pm25.agg(['sum','count']).to_numpy()
        boot=groups[rng.integers(0,len(groups),size=(1500,len(groups)))].sum(axis=1)
        l,u=np.quantile(boot[:,0]/boot[:,1],[.025,.975])
        return dict(grids_hours=len(z),anchor_days=len(groups),mean_delta=z.delta_pm25.mean(),ci_low=l,ci_high=u)
    summary=pd.DataFrame([dict(lag=lag,**interval(z)) for lag,z in pairs.groupby('lag')]);write(summary,OUT/'fire_lag.csv')
    dist=haversine_distances(np.radians(coords),np.radians(coords))*6371
    az=np.array([bearing(*p,coords[:,0],coords[:,1]) for p in coords])
    up_prev=pd.DataFrame(pm).shift(1).rolling(6,min_periods=3).mean().to_numpy()
    inputs=pd.read_csv(JOIN/'ground_episodes.csv',parse_dates=['start','end']).query('yrd41').copy()
    features=[]
    for e in inputs.itertuples():
        c=names.index(e.city)
        hours=times.get_indexer(pd.date_range(e.start,e.end+pd.Timedelta(hours=23),freq='h'))
        up_values=[]
        for h in hours:
            ok=(dist[c]>=30)&(dist[c]<=200)&(angle(az[c],wind[h,c])<=45)&np.isfinite(up_prev[h])&(speed[h,c]>=1)
            if ok.any():up_values.append(np.mean(up_prev[h,ok]))
        features.append((np.mean(speed[hours,c]),np.mean(blh[hours,c]),np.mean(up_values) if up_values else np.nan,len(up_values)))
    features=pd.DataFrame(features,columns=['ws_ms','blh_m','upwind_pm25_prev6','upwind_hours'],index=inputs.index)
    inputs=inputs.join(features);cols=['ws_ms','blh_m','upwind_pm25_prev6']
    ok=inputs[cols].notna().all(axis=1)&(inputs.upwind_hours>=6)
    x=StandardScaler().fit_transform(inputs.loc[ok,cols]);model=KMeans(2,n_init=50,random_state=20261115)
    labels=model.fit_predict(x);inputs.loc[ok,'cluster']=labels
    write(inputs,OUT/'episode_cluster.csv')
    centres=inputs.dropna(subset='cluster').groupby('cluster')[cols].mean()
    centres['n']=inputs.cluster.value_counts()
    write(centres.reset_index(),OUT/'episode_centers.csv')
    # 南京入边以一阶小时差分排除慢变水平趋势。按接收地风向筛选；保留全部候选与滞后，选择后的峰值只做探索。
    nj_i=names.index('南京');dm=pd.DataFrame(pm).diff().to_numpy()
    net=[]
    for j,city in enumerate(names):
        if not 30<=dist[nj_i,j]<=250:continue
        aligned=(angle(az[nj_i,j],wind[:,nj_i])<=45)&(speed[:,nj_i]>=1)
        for lag in range(1,7):
            a,b=dm[:-lag,j],dm[lag:,nj_i]
            valid=np.isfinite(a)&np.isfinite(b)&aligned[lag:]
            if valid.sum()>=48:
                net.append(dict(source=city,target='南京',lag=lag,n=int(valid.sum()),r=np.corrcoef(a[valid],b[valid])[0,1],distance_km=dist[nj_i,j]))
    network=pd.DataFrame(net);write(network,OUT/'nanjing_network_all.csv')
    best=network.sort_values('r',ascending=False).drop_duplicates('source')
    write(best,OUT/'nanjing_network_best.csv')
    stats=dict(era5_cityhours=len(met),era5_bytes=path.stat().st_size,era5_valid_blh=int(met.blh_m.notna().sum()),era5_complete_variables=int(met[['t2m_c','sp_hpa','ws_ms','wind_from_deg','blh_m']].notna().all(axis=1).sum()),yz_ground_matched=len(fact),eligible_episode_clusters=int(ok.sum()),silhouette=float(silhouette_score(x,labels)),network_candidates=len(best),positive_corr_025=int((best.r>=.25).sum()),candidate_fire_gridhours=len(f))
    (OUT/'fusion_summary.json').write_text(json.dumps(stats,indent=2))
if __name__=='__main__':
    main()
