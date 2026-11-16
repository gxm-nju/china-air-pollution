"""参数为原工程根目录。输出到本脚本所在的结果目录。"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import haversine_distances
root = Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
from extend_fusion import angle, bearing, series
out=Path(__file__).resolve().parent
base=root/'多源数据与实验'
full=root/'扩展实验/三年地面补采/多源复算/更新计算/data/integrated'
keys=['time','lat_grid','lon_grid']
def common(p):
    df=pd.read_csv(p,parse_dates=['time'])
    return df[df.groupby(keys).lag.transform('nunique').eq(5)&df.lag.eq(12)].copy()
anchors=common(full/'fire_wind_sector_contrasts.csv.gz')
old=common(root/'扩展实验/多源复算/data/integrated/fire_wind_sector_contrasts.csv.gz')
compare=anchors.merge(old[keys+['delta_pm25']],on=keys,how='outer',indicator=True,suffixes=('_full','_old'),validate='one_to_one')
print(compare.groupby('_merge',observed=True)[['delta_pm25_full','delta_pm25_old']].agg(['count','mean']))
print('anchor clock',anchors.time.dt.hour.value_counts().sort_index().to_dict())
print('new estimates',anchors.delta_pm25.mean(),old.delta_pm25.mean())
dust=pd.read_csv(root/'过程文件/03_实验结果/MERRA-2气溶胶/三月事前细沙尘_完整窗口/逐城逐小时.csv')
s=dust[dust.city.eq('宿迁')].groupby(dust.date.eq('2023-03-23')).dust.mean()
print('suqian',s.to_dict(),s[True]-s[False])
cities=pd.read_csv(base/'data/cleaned/case_city_grid.csv').dropna(subset='source_group').sort_values('city')
coords=cities[['lat','lon']].to_numpy()
times=pd.date_range('2023-01-01','2025-12-31 23:00',freq='h')
g=pd.read_parquet(full/'yrd_ground_era5_hour.parquet')
pm,wind,speed=[series(g,k,times,cities.city.tolist()) for k in ['pm25','wind_from_deg','ws_ms']]
baseline=pd.DataFrame(pm).shift(1).rolling(24,min_periods=12).mean().to_numpy()
# Include even isolated and fixed heat detections when excluding comparison dates.
observed=set()
for year in range(2022,2026):
    df=pd.read_csv(base/f'data/cleaned/fire_events/utc_{year}.csv.gz',usecols=['local_slot','lat_bin','lon_bin'],parse_dates=['local_slot'])
    for axis in ['lat','lon']:
        df[axis+'_grid']=np.floor((df[axis+'_bin']+.5)/100*4+.5)/4
    observed.update(df.assign(date=df.local_slot.dt.normalize())[['lat_grid','lon_grid','date']].drop_duplicates().itertuples(index=False,name=None))
records=[]
for (lat,lon),z in anchors.groupby(['lat_grid','lon_grid']):
    dist=haversine_distances(np.radians([[lat,lon]]),np.radians(coords))[0]*6371
    az=bearing(lat,lon,*coords.T)
    near=dist.argmin()
    ring=(dist>=30)&(dist<=200)
    for e in z.itertuples():
        h=times.get_loc(e.time)
        orient=wind[h,near]
        v=pm[h+12]-baseline[h]
        up=ring&(angle(az,orient)<=45)&np.isfinite(v)
        down=ring&(angle(az,orient+180)<=45)&np.isfinite(v)
        assert abs(v[down].mean()-v[up].mean()-e.delta_pm25)<1e-5
        candidates=[]
        for offset in range(-14,15):
            k=h+offset*24
            if not offset or k<24 or k+12>=len(times) or times[k].month!=e.time.month: continue
            d=times[k].normalize()
            if any((lat,lon,d+pd.Timedelta(days=i)) in observed for i in (-1,0,1)): continue
            if not (speed[k,near]>=1 and abs(speed[k,near]-speed[h,near])<=2 and angle(wind[k,near],orient)<=30): continue
            # Hold city identities fixed and require them to stay inside their respective wind sectors.
            if not ((angle(az[up],wind[k,near])<=45).all() and (angle(az[down],wind[k,near]+180)<=45).all()):continue
            cv=pm[k+12]-baseline[k]
            if not np.isfinite(cv[up|down]).all():continue
            candidates.append((abs(offset),angle(wind[k,near],orient),k,cv[down].mean()-cv[up].mean()))
        if candidates:
            _,_,k,c=min(candidates)
            records.append([e.time,lat,lon,times[k],e.delta_pm25,c,e.delta_pm25-c,len(candidates)])
result=pd.DataFrame(records,columns=[*keys,'control_time','event','control','difference','candidates'])
result.to_csv(out/'同网格未检出日配对.csv.gz',index=False,compression=dict(method='gzip',mtime=0))
print('matched',len(result),result.time.dt.normalize().nunique(),len(result.drop_duplicates(['control_time','lat_grid','lon_grid'])),result[['event','control','difference']].mean().to_dict())
# Pair shares a calendar month. Resample whole months to retain dependencies within them.
blocks=result.groupby(result.time.dt.to_period('M')).difference.agg(['sum','count']).to_numpy()
rng=np.random.default_rng(20261116)
draw=blocks[rng.integers(len(blocks),size=(10000,len(blocks)))].sum(axis=1)
print('matched months',len(blocks),'interval',np.quantile(draw[:,0]/draw[:,1],[.025,.975]))
