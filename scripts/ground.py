"""Station observations to city-hour means, with availability and hourly continuity checks."""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'
CL=ROOT/'data/cleaned'
IN=ROOT/'data/integrated'
OUT=ROOT/'results'
YRD='上海 南京 无锡 徐州 常州 苏州 南通 连云港 淮安 盐城 扬州 镇江 泰州 宿迁 杭州 宁波 温州 嘉兴 湖州 绍兴 金华 衢州 舟山 台州 丽水 合肥 芜湖 蚌埠 淮南 马鞍山 淮北 铜陵 安庆 黄山 滁州 阜阳 宿州 六安 亳州 池州 宣城'.split()
def grid(v): return np.floor(np.asarray(v)*4+0.5)/4
def sites():
    t=pd.read_csv(RAW/'metadata/Station_information.csv',encoding='gb18030').rename(columns={'Code':'station','City_Chinese':'city','Longitude':'lon','Latitude':'lat'})
    t=t.drop_duplicates(subset=['station','city','lon','lat'])
    assert not t.station.duplicated().any()
    for c in ['lon','lat']:t[c]=pd.to_numeric(t[c],errors='coerce')
    t=t[t.lon.between(73,136)&t.lat.between(17,55)].copy()
    t['gx']=grid(t.lon);t['gy']=grid(t.lat)
    return t[['station','city','lon','lat','gx','gy','Station_name_Chinese']]
def run():
    m=sites();station_set=set(m.station);m.to_csv(CL/'stations.csv',index=False)
    active=set(); unmatched=[]; monthly=[]; quality=[]
    files=sorted((RAW/'air').glob('china_sites_*.csv'))
    for ym in sorted({f.stem[-8:-2] for f in files}):
        frames=[]
        for f in [p for p in files if p.stem[-8:-2]==ym]:
            w=pd.read_csv(f); assert w.date.astype(str).eq(f.stem[-8:]).all() and w.hour.between(0,23).all()
            ids=list(w.columns[3:]);active.update(ids)
            good=w[w.type.isin(['PM2.5','NO2','PM10','SO2','O3','CO','AQI'])].copy()
            duplicate=int(good.duplicated(['date','hour','type']).sum())
            assert duplicate==0
            validids=[s for s in ids if s in station_set]
            good['time_bjt']=pd.to_datetime(good.date.astype(str),format='%Y%m%d')+pd.to_timedelta(good.hour,unit='h')
            vals=good.set_index(['time_bjt','type'])[validids].apply(pd.to_numeric,errors='coerce')
            neg=int((vals<0).sum().sum()); nan=int(vals.isna().sum().sum())
            tbl=vals.mask(vals<0).rename_axis(columns='station').stack(future_stack=True).unstack('type').reset_index()
            frames.append(tbl);quality.append(dict(date=int(w.date.iloc[0]),archive_stations=len(ids),mapped_stations=len(validids),rows_read=len(w),retained_types_rows=len(good),duplicate_keys=duplicate,negative_cells=neg,missing_cells=nan,selected_cells=vals.size))
        allrows=pd.concat(frames,ignore_index=True).sort_values(['station','time_bjt'])
        for fld in ['PM2.5','NO2']:
            # Runs crossing a month boundary are evaluated separately within each partition.
            same=allrows[fld].eq(allrows[fld].shift())&allrows.station.eq(allrows.station.shift())&allrows.time_bjt.diff().eq(pd.Timedelta(hours=1))
            runid=(~same).cumsum();allrows[fld+'_flat6']=allrows[fld].notna()&allrows.groupby(runid)[fld].transform('size').ge(6)
        p=CL/'air'/f'year={ym[:4]}'/f'month={ym[4:]}';p.mkdir(parents=True,exist_ok=True);allrows.to_parquet(p/'station_hour.parquet',index=False)
        z=allrows.merge(m[['station','city']],on='station',validate='many_to_one')
        vals=['PM2.5','NO2','PM10','SO2','O3','CO','AQI']
        a=z.groupby(['city','time_bjt'])[vals].mean().rename(columns={'AQI':'mean_station_aqi'})
        for v in ['PM2.5','NO2']:a['n_'+v]=z.groupby(['city','time_bjt'])[v].count()
        monthly.append(a.reset_index())
    out=pd.concat(monthly,ignore_index=True);out.to_parquet(IN/'all_city_hour.parquet',index=False)
    pd.DataFrame(quality).to_csv(OUT/'air_quality.csv',index=False);pd.DataFrame({'unmatched_id':sorted(active-station_set)}).to_csv(OUT/'unmatched_stations.csv',index=False)
    x=m[m.station.isin(active)].groupby('city').agg(lon=('lon','median'),lat=('lat','median'),stations=('station','nunique')).reset_index()
    x['yrd']=x.city.isin(YRD);x.to_csv(CL/'cities.csv',index=False)
    print('ground',len(files),'files',len(active),'station columns',len(active & station_set),'matched',len(out),'city-hours',out.city.nunique(),'cities',int(x.yrd.sum()),'YRD')
if __name__=='__main__':
    run()
