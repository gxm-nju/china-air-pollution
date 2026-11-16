from catalog import ROOT
from pathlib import Path
import hashlib,sys,json
import numpy as np
import pandas as pd
from scipy.io import netcdf_file
from sklearn.metrics.pairwise import haversine_distances
project=ROOT.parents[1]
sys.path.insert(0,str(project/'scripts'))
from extend_fusion import bearing,angle,series
from era import spec
out=ROOT/'结果';out.mkdir(exist_ok=True)
old=project/'扩展实验/三年地面补采/多源复算/更新计算/data/integrated'
places=pd.read_csv(project/'多源数据与实验/data/cleaned/case_city_grid.csv').dropna(subset='source_group').sort_values('city')
coords=places[['lat','lon']].to_numpy()
keys=['time','lat_grid','lon_grid']
anchors=pd.read_csv(old/'fire_wind_sector_contrasts.csv.gz',parse_dates=['time'])
anchors=anchors[anchors.groupby(keys).lag.transform('nunique').eq(5)&anchors.lag.eq(12)].copy()
controls=pd.read_csv(project/'过程文件/06_GitHub仓库/三年地面扩展/同网格未检出日配对.csv.gz',parse_dates=['time','control_time'])
controls=controls.merge(anchors[keys],on=keys,validate='one_to_one')
ground=pd.read_parquet(old/'yrd_ground_era5_hour.parquet')
ts=pd.date_range('2023-01-01','2025-12-31 23:00',freq='h')
pm=series(ground,'pm25',ts,places.city)
base=pd.DataFrame(pm).shift(1).rolling(24,min_periods=12).mean().to_numpy()
wind=series(ground,'wind_from_deg',ts,places.city)
speed=series(ground,'ws_ms',ts,places.city)
def interval(z,col):
    a=z.groupby(z.time.dt.normalize())[col].agg(['sum','count']).to_numpy()
    rng=np.random.default_rng(20261116)
    b=a[rng.integers(len(a),size=(2000,len(a)))].sum(axis=1)
    return np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()
def sample(a,t,gg,lat,lon):
    i=np.where(lat==a.lat_grid)[0];j=np.where(lon==a.lon_grid)[0]
    if not len(i) or not len(j):return None
    h=ts.get_loc(t)
    h_utc=t-pd.Timedelta(hours=8)
    k=int((t-gg['first_bjt'])//pd.Timedelta(hours=1))
    u,v,blh=(gg[field][k,i[0],j[0]] for field in spec)
    sp=np.hypot(u,v);az=np.degrees(np.arctan2(-u,-v))%360
    dist=haversine_distances(np.radians([[a.lat_grid,a.lon_grid]]),np.radians(coords))[0]*6371
    near=dist.argmin();direction=bearing(a.lat_grid,a.lon_grid,*coords.T)
    ring=(dist>=30)&(dist<=200);change=pm[h+12]-base[h]
    def contrast(orientation):
        up=ring&(angle(direction,orientation)<=45)&np.isfinite(change)
        down=ring&(angle(direction,orientation+180)<=45)&np.isfinite(change)
        if not(up.any() and down.any()):return np.nan,up,down
        return change[down].mean()-change[up].mean(),up,down
    prev,pup,pdown=contrast(wind[h,near]);cur,cup,cdown=contrast(az)
    if sp<1:cur=np.nan
    return dict(citywind=prev,gridwind=cur,angle_diff=angle(az,wind[h,near]),speed=sp,blh=blh,changed=not(np.array_equal(pup,cup) and np.array_equal(pdown,cdown)),grid_az=az,up_ids=','.join(map(str,np.flatnonzero(cup))),down_ids=','.join(map(str,np.flatnonzero(cdown))))
def main():
    events=[];ref=[];clim=[]
    for path in sorted((ROOT/'原始数据/ERA5').glob('*_blh.nc')):
        month=path.name[:7];files={k:path.with_name(f'{month}_{k}.nc') for k in spec}
        if not all(p.exists() for p in files.values()):continue
        gg={}
        for k,p in files.items():
            with netcdf_file(p,mmap=False) as f:
                gg[k]=f.variables[spec[k][1]].data.copy()
                lat=f.variables['latitude'].data.copy();lon=f.variables['longitude'].data.copy()
                first_bjt=pd.Timestamp('1900-01-01')+pd.Timedelta(hours=int(f.variables['time'].data[0])+8)
        gg['first_bjt']=first_bjt
        sid=pd.date_range(first_bjt,periods=len(gg['blh']),freq='h')
        weights=np.broadcast_to(np.cos(np.radians(lat))[:,None],(len(lat),len(lon)))
        def avg(x):return np.average(x.reshape(len(sid),-1),axis=1,weights=weights.ravel())
        clim.append(pd.DataFrame(dict(time=sid,region_ws=avg(np.hypot(gg['u10'],gg['v10'])),region_blh=avg(gg['blh']))))
        for table,label,dest in [(anchors,'time',events),(controls,'control_time',ref)]:
            z=table[(table[label]>=sid[0])&(table[label]<=sid[-1])]
            for a in z.itertuples():
                r=sample(a,getattr(a,label),gg,lat,lon)
                if r is None:continue
                if label=='time':assert np.isclose(r['citywind'],a.delta_pm25,atol=.00001)
                dest.append({**{k:getattr(a,k) for k in keys},label:getattr(a,label),**r})
    e=pd.DataFrame(events);e.to_csv(out/'火点风向对照.csv.gz',index=False)
    z=e.dropna(subset=['gridwind']).copy();z['delta']=z.gridwind-z.citywind
    summ=[]
    for label,v in [('全部已下载',z),('2024年1月',z[z.time.dt.to_period('M').astype(str)=='2024-01'])]:
        if len(v):
            summ.append(dict(scope=label,n=len(v),days=v.time.dt.normalize().nunique(),citywind=v.citywind.mean(),gridwind=v.gridwind.mean(),grid_ci=interval(v,'gridwind'),change=v.delta.mean(),change_ci=interval(v,'delta'),changed=v.changed.sum(),median_angle=v.angle_diff.median()))
    c=pd.DataFrame(ref).merge(z,on=keys,suffixes=('_c','_e'))
    c=c.dropna(subset=['gridwind_c'])
    # Keep the original control matching restrictions using new fire-grid wind and identical valid city sets.
    c=c[(angle(c.grid_az_c,c.grid_az_e)<=30)&((c.speed_c-c.speed_e).abs()<=2)&c.up_ids_c.eq(c.up_ids_e)&c.down_ids_c.eq(c.down_ids_e)]
    c['paired']=c.gridwind_e-c.gridwind_c
    if len(c):
        blocks=c.groupby(c.time.dt.to_period('M')).paired.agg(['sum','count']).to_numpy()
        boot=blocks[np.random.default_rng(20261116).integers(len(blocks),size=(10000,len(blocks)))].sum(axis=1)
        print('grid matched contrast',len(c),c.paired.mean(),np.quantile(boot[:,0]/boot[:,1],[.025,.975]),flush=True)
    c.to_csv(out/'网格风未检出日配对.csv.gz',index=False)
    wx=pd.concat(clim).sort_values('time')
    wx=wx[wx.time.isin(ts)].set_index('time');daily=wx.resample('D').mean()[wx.region_ws.resample('D').count()==24]
    gr=pd.read_csv(project/'过程文件/06_GitHub仓库/三年地面扩展/三年逐日覆盖与区域共现.csv',parse_dates=['date']).set_index('date')
    daily=daily.join(gr.iloc[:,-2:]).dropna();daily=daily[daily.iloc[:,-2]>0]
    daily.to_csv(out/'区域气象与超阈值日期.csv')
    print(daily.groupby(daily.iloc[:,-1]>0)[['region_ws','region_blh']].agg(['size','mean']))
    pd.DataFrame(summ).to_json(out/'火点对照汇总.json',orient='records',force_ascii=False,indent=2)
    print('anchor total, in domain and time, both computable',len(anchors),len(e),len(z),summ)
if __name__=='__main__':main()
