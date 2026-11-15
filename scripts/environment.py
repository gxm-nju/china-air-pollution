"""Build ERA5 station-cell summaries, FIRMS events and QA-filtered satellite observations."""
from collections import defaultdict
import json
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
from scipy.io import netcdf_file
from ground import RAW,CL,IN,OUT,grid,sites,YRD

def meteo(start=None,end=None,raw_dir=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from contextlib import ExitStack
    from scipy.io import netcdf_file
    base=raw_dir or RAW/'era5'
    folders=defaultdict(dict)
    for p in sorted(base.rglob('*.nc'),key=lambda x:('east' in x.relative_to(base).parts,str(x))):
        period=p.name.split('.')[-2]
        code=p.name.split('.')[4].split('_')[-1]
        folders[period][code]=p
    keys={'10u':'u10','10v':'v10','2t':'t2m_K','blh':'blh_m','sp':'sp_Pa'}
    cities=sites().query('city in @YRD').drop_duplicates(['city','gx','gy'])
    city_tables=[];grid_rows=0
    for period,files in sorted(folders.items()):
        first=pd.to_datetime(period[:10],format='%Y%m%d%H')+pd.Timedelta(hours=8)
        last=pd.to_datetime(period[-10:],format='%Y%m%d%H')+pd.Timedelta(hours=8)
        if (start is not None and last<start) or (end is not None and first>=end):continue
        with ExitStack() as stack:
            fields={}
            for code,p in files.items():
                if code not in keys:continue
                nc=stack.enter_context(netcdf_file(p,mmap=True))
                v=next(v for k,v in nc.variables.items() if k not in ['time','longitude','latitude'])
                tv=nc.variables['time']; unit=tv.units.decode().lower()
                times=pd.Timestamp(unit.split(' since ')[1])+pd.to_timedelta(tv[:].copy(),unit={'hours':'h','days':'D','seconds':'s'}[unit.split()[0]])+pd.Timedelta(hours=8)
                fields[keys[code]]=(times,nc.variables['longitude'][:].copy(),nc.variables['latitude'][:].copy(),v)
            if not fields:continue
            path=CL/'era5'/period;path.mkdir(parents=True,exist_ok=True);tmp=path/'grid.part.parquet';writer=None
            try:
                for day in sorted(set().union(*(set(t.normalize()) for t,_,_,_ in fields.values()))):
                    frames=[]
                    for label,(t,lons,lats,v) in fields.items():
                        mask=t.normalize()==day
                        if start is not None:mask&=t>=start
                        if end is not None:mask&=t<end
                        idx=np.flatnonzero(mask)
                        if not len(idx):continue
                        a=v[idx,:,:].astype('float32');fill=getattr(v,'_FillValue',None)
                        if fill is not None:a[a==fill]=np.nan
                        a[np.abs(a)>1e10]=np.nan
                        index=pd.MultiIndex.from_product([t[idx],lats.astype(float),lons.astype(float)],names=['time_bjt','gy','gx'])
                        frames.append(pd.Series(a.ravel(),index=index,name=label))
                    if not frames:continue
                    x=pd.concat(frames,axis=1).reindex(columns=list(keys.values())).reset_index()
                    x['speed_ms']=np.hypot(x.u10,x.v10);x['t2m_C']=x.t2m_K-273.15
                    tb=pa.Table.from_pandas(x,preserve_index=False)
                    if writer is None:writer=pq.ParquetWriter(tmp,tb.schema)
                    writer.write_table(tb);grid_rows+=len(x)
                    g=x.merge(cities[['city','gx','gy']],on=['gx','gy']).groupby(['city','time_bjt'])
                    city_tables.append(g[['u10','v10','blh_m','t2m_C','sp_Pa']].mean().join(g.size().rename('n_met_cells')).reset_index())
            finally:
                if writer is not None:writer.close()
            if writer is not None:tmp.replace(path/'grid.parquet')
            fields.clear()
            del v,tv
    if not city_tables:raise ValueError(f'没有所选时期可读的 ERA5 研究窗口 {base}')
    cm=pd.concat(city_tables,ignore_index=True);assert not cm.duplicated(['city','time_bjt']).any()
    cm['speed_ms']=np.hypot(cm.u10,cm.v10);cm.to_parquet(CL/'city_weather.parquet',index=False)
    print('weather grid-hours',grid_rows,'YR city-hours',len(cm),flush=True)

def fires():
    years=defaultdict(list);stats=[]
    sources={p.name:p for p in (RAW/'firms').glob('*_China.csv')}
    sources.update({p.name:p for p in (RAW.parents[1]/'多源数据与实验/data/raw/firms').glob('*_China.csv')})
    for p in sorted(sources.values()):
        sensor,y,_=p.stem.split('_');a=pd.read_csv(p,low_memory=False)
        n=len(a); conf=a.confidence.astype(str).str.lower()
        ok=pd.to_numeric(conf,errors='coerce').ge(30) if sensor=='modis' else conf.isin(['n','h'])
        other=int((ok&a.type.ne(0)).sum())
        a=a[ok&a.type.eq(0)].copy();a['sensor']=sensor
        hhmm=a.acq_time.astype(str).str.zfill(4);a['time_bjt']=pd.to_datetime(a.acq_date+' '+hhmm,format='%Y-%m-%d %H%M')+pd.Timedelta(hours=8)
        a['gx']=grid(a.longitude);a['gy']=grid(a.latitude)
        # A ~1 km bin over eastern China. Adjacent-bin duplicates can remain.
        a['ix']=np.floor(a.longitude*111.32*np.cos(np.radians(a.gy))*1.0).astype(int)
        a['iy']=np.floor(a.latitude*110.57).astype(int)
        a['bin']=a.time_bjt.dt.floor('30min')
        years[int(y)].append(a[['sensor','time_bjt','longitude','latitude','gx','gy','ix','iy','bin','frp']])
        stats.append(dict(file=p.name,raw=n,low_or_unknown_conf=int((~ok).sum()),nonvegetation_or_unknown=other,retained=len(a)))
    week=[]
    for y,frames in years.items():
        full=pd.concat(frames,ignore_index=True)
        z=full.groupby(['bin','gy','ix','iy'],as_index=False).agg(time_bjt=('time_bjt','min'),longitude=('longitude','mean'),latitude=('latitude','mean'),frp_max_MW=('frp','max'),detections=('sensor','size'),n_sensors=('sensor','nunique'))
        z['gx']=grid(z.longitude);z['month']=z.time_bjt.dt.month
        many=z.groupby(['gy','ix','iy']).month.transform('nunique').ge(10)
        z['recurring_heat_flag']=many
        d=CL/'firms'/f'year={y}';d.mkdir(parents=True,exist_ok=True);z.to_parquet(d/'events.parquet',index=False)
        region=z[z.gx.between(114,124)&z.gy.between(27,36)&~many].copy()
        region['week']=region.time_bjt.dt.isocalendar().week.astype(int);counts=region.groupby('week').size().rename('events').reset_index();counts['file_year']=y;counts['available_sensors']=len(frames);week.append(counts)
    pd.concat(week).to_csv(OUT/'fire_weeks.csv',index=False);pd.DataFrame(stats).to_csv(OUT/'fire_quality.csv',index=False)
    print('fire files',len(stats),'raw',sum(q['raw'] for q in stats),'after confidence and type',sum(q['retained'] for q in stats))

def pixel_times(no2,prefix,w):
    """Decode a co-registered pixel time band only when metadata defines its epoch and units."""
    import re
    fp=no2.with_name(prefix+'_utctime_4326.tif')
    if not fp.exists():return None,'missing'
    with rasterio.open(fp) as t,rasterio.open(no2) as n:
        if (t.crs,t.transform,t.shape)!=(n.crs,n.transform,n.shape):return None,'grid_mismatch'
        tags={**t.tags(),**t.tags(1)};unit=t.units[0] or tags.get('units') or tags.get('UNITTYPE') or ''
        m=re.fullmatch(r'(milliseconds?|seconds?|minutes?|hours?|days?) since (.+)',unit.strip(),re.I)
        if not m:return None,'unknown_time_units'
        factors={'millisecond':.001,'second':1,'minute':60,'hour':3600,'day':86400}
        origin=pd.to_datetime(m[2],utc=True,errors='coerce')
        if pd.isna(origin):return None,'unknown_time_epoch'
        arr=t.read(1,window=w,masked=True).astype(float).filled(np.nan)
        sec=(arr*t.scales[0]+t.offsets[0])*factors[m[1].lower().rstrip('s')]+origin.timestamp()
        stamps=prefix.split('____')[1].split('_')[:2]
        a,b=[pd.to_datetime(v,format='%Y%m%dT%H%M%S',utc=True).timestamp() for v in stamps]
        return np.where((sec>=a)&(sec<=b),sec,np.nan),'checked_against_orbit'

def satellite():
    records=[];qa=[];s=sites();s=s[s.city.isin(YRD)].copy()
    # Local raw clips are products at native resolution; full swaths are transport copies.
    dd=CL/'s5p';dd.mkdir(exist_ok=True)
    pattern='*PRODUCT_nitrogendioxide_tropospheric_column_4326.tif'
    files={}
    for folder in [RAW/'s5p',RAW/'s5p/pilot_clips',RAW/'s5p/east_clips']:
        files.update({p.name:p for p in folder.glob(pattern)})
    for no2 in sorted(files.values()):
        prefix=no2.name.split('_PRODUCT_')[0];quality=no2.with_name(prefix+'_PRODUCT_qa_value_4326.tif')
        if not quality.exists():continue
        nodate=prefix.split('____')[1][:8]
        with rasterio.open(no2) as ds,rasterio.open(quality) as qs:
            assert ds.crs==qs.crs and ds.transform==qs.transform and ds.shape==qs.shape
            native=from_bounds(114,27,124,36,ds.transform)
            x0=int(np.floor(native.col_off));y0=int(np.floor(native.row_off));x1=int(np.ceil(native.col_off+native.width));y1=int(np.ceil(native.row_off+native.height))
            if x1<=0 or y1<=0 or x0>=ds.width or y0>=ds.height:continue
            w=Window(x0,y0,x1-x0,y1-y0).intersection(Window(0,0,ds.width,ds.height))
            col=ds.read(1,window=w,masked=True);q=qs.read(1,window=w,masked=True)
            for source,data,tgt in [(ds,col,'column'),(qs,q,'qa')]:
                opts=source.profile.copy();opts.update(width=int(w.width),height=int(w.height),transform=source.window_transform(w),compress='deflate',tiled=False);opts.pop('blockxsize',None);opts.pop('blockysize',None)
                with rasterio.open(dd/f'{prefix}_{tgt}.tif','w',**opts) as dst:dst.write(data.filled(source.nodata),1)
            pixel_sec,time_status=pixel_times(no2,prefix,w)
            quality_percent=q.astype(float).filled(np.nan);vals=col.filled(np.nan)
            valid=np.isfinite(vals)&np.isfinite(quality_percent)&(quality_percent>75)
            rows=[]
            for a in s.itertuples():
                r,c=ds.index(a.lon,a.lat);r-=y0;c-=x0
                if 0<=r<vals.shape[0] and 0<=c<vals.shape[1]:
                    rows.append([a.city,r,c,vals[r,c],quality_percent[r,c],bool(valid[r,c]),pixel_sec[r,c] if pixel_sec is not None else np.nan])
            u=pd.DataFrame(rows,columns=['city','row','col','column_raw','qa_pct','valid','pixel_utc_s']).drop_duplicates(['city','row','col'])
            for city,g in u.groupby('city'):
                timed=g[g.valid & g.pixel_utc_s.notna()]
                median=pd.to_datetime(timed.pixel_utc_s.median(),unit='s',utc=True).tz_convert('Asia/Shanghai').tz_localize(None) if len(timed) else pd.NaT
                records.append(dict(date=pd.Timestamp(nodate),city=city,orbit=prefix,located_pixels=len(g),valid_pixels=int(g.valid.sum()),valid_fraction=g.valid.mean(),no2_mol_m2=g.loc[g.valid,'column_raw'].mean(),pixel_time_bjt=median,timed_valid_pixels=len(timed),timed_column=timed.column_raw.mean(),time_status=time_status))
            qa.append(dict(orbit=prefix,window_pixels=valid.size,nonfill=int(np.isfinite(vals).sum()),valid=int(valid.sum()),observed_station_pixels=len(u),valid_station_pixels=int(u.valid.sum())))
    pd.DataFrame(records).to_parquet(CL/'satellite_city_orbit.parquet',index=False);pd.DataFrame(qa).to_csv(OUT/'satellite_quality.csv',index=False)
    print('satellite paired orbits',len(qa),'city-orbit records',len(records))
if __name__=='__main__':
    import argparse
    from pathlib import Path
    from ground import ROOT
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['meteo','fires','satellite','all'],default='all');p.add_argument('--start',type=pd.Timestamp);p.add_argument('--end-exclusive',type=pd.Timestamp);p.add_argument('--era5-dir',type=Path)
    p.add_argument('--output-dir',type=Path,default=ROOT/'扩展实验/环境复算');a=p.parse_args()
    OUT=a.output_dir;CL=OUT/'cleaned';CL.mkdir(parents=True,exist_ok=True)
    if a.stage in ['all','meteo']:meteo(a.start,a.end_exclusive,a.era5_dir)
    if a.stage in ['all','fires']:fires()
    if a.stage in ['all','satellite']:satellite()
