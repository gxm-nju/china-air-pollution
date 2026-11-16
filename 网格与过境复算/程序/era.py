from catalog import ROOT,session
from pathlib import Path
import calendar,sys,json,hashlib
from concurrent.futures import ThreadPoolExecutor
from scipy.io import netcdf_file
import pandas as pd
import numpy as np
spec={'u10':('165_10u','VAR_10U',b'm s**-1'),'v10':('166_10v','VAR_10V',b'm s**-1'),'blh':('159_blh','BLH',b'm')}
def fetch(task):
    month,k=task
    ident,var,unit=spec[k]; a=pd.Timestamp(month+'-01')
    b=a+pd.offsets.MonthEnd(); ym=a.strftime('%Y%m')
    url=f'https://tds.gdex.ucar.edu/thredds/ncss/grid/files/d633000/e5.oper.an.sfc/{ym}/e5.oper.an.sfc.128_{ident}.ll025sc.{ym}0100_{b:%Y%m%d}23.nc'
    begin=a if month!='2022-12' else b+pd.Timedelta(hours=16)
    finish=b+pd.Timedelta(hours=23)
    params=dict(var=var,north=35,south=28,west=115.5,east=122.5,time_start=f'{begin:%Y-%m-%dT%H}:00:00Z',time_end=f'{b:%Y-%m-%d}T23:00:00Z',accept='netcdf3')
    p=ROOT/'原始数据/ERA5'/f'{month}_{k}.nc'
    tmp=p if p.exists() else p.with_suffix('.part')
    if not p.exists():
        r=session().get(url,params=params,timeout=(20,150));r.raise_for_status();tmp.write_bytes(r.content)
    with netcdf_file(tmp,mmap=False) as f:
        x=f.variables[var]; t=f.variables['time']; lat=f.variables['latitude'].data;lon=f.variables['longitude'].data
        assert x.data.shape==(int((finish-begin)//pd.Timedelta(hours=1))+1,29,29) and x.units in (unit,b'm s-1',b'm/s') and t.units==b'hours since 1900-01-01 00:00:00'
        assert np.array_equal(t.data,np.arange(len(t.data))+(begin-pd.Timestamp('1900-01-01'))//pd.Timedelta(hours=1))
        assert np.array_equal(np.sort(lat),np.arange(28,35.01,.25)) and np.array_equal(np.sort(lon),np.arange(115.5,122.51,.25))
        assert np.isfinite(x.data).all() and np.max(np.abs(x.data))<(15000 if k=='blh' else 150)
    if tmp!=p:tmp.replace(p)
    return dict(month=month,field=k,file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=session().prepare_request(__import__('requests').Request('GET',url,params=params)).url)
if __name__=='__main__':
    tasks=[(m,k) for m in sys.argv[1:] for k in spec]
    def run(t):
        try:
            row=fetch(t);print(t,row['bytes'],flush=True);return row
        except Exception as e:
            print(t,type(e).__name__,str(e)[:280],flush=True);return dict(month=t[0],field=t[1],error=repr(e))
    with ThreadPoolExecutor(5) as ex: records=list(ex.map(run,tasks))
    pd.DataFrame(records).to_csv(ROOT/'记录'/('ERA5清单_'+sys.argv[1]+'_'+sys.argv[-1]+'.csv'),index=False)
