from catalog import ROOT,S3
from sat import Reader,decoded
import h5py,pandas as pd,numpy as np,hashlib,json
from pathlib import Path
from scipy.io import netcdf_file
from sklearn.metrics import mean_absolute_error
project=ROOT.parents[1]
out=ROOT/'结果'
checks={}
ledger=[]
for name in ['ERA5清单_2023-01_2025-12.csv','ERA5清单_2022-12_2022-12.csv',
             '卫星下载_2023-01.csv','卫星下载_2024-01.csv','卫星下载_2025-01.csv']:
    s=pd.read_csv(ROOT/'记录'/name)
    is_sat='卫星' in name
    if is_sat:
        cat=pd.read_csv(ROOT/'记录'/name.replace('卫星下载','轨道清单'))
        assert set(cat.orbit)==set(s.orbit) and not cat.orbit.duplicated().any()
    for r in s.itertuples():
        p=ROOT/'原始数据'/('S5P' if is_sat else 'ERA5')/(r.orbit+'.npz' if is_sat else r.file)
        assert p.stat().st_size==r.bytes and hashlib.sha256(p.read_bytes()).hexdigest()==r.sha256
        ledger.append(dict(source='S5P' if is_sat else 'ERA5',file=p.name,bytes=r.bytes,sha256=r.sha256,url=r.url))
m=pd.DataFrame(ledger)
assert not m.file.duplicated().any() and not m.sha256.duplicated().any()
m.to_csv(ROOT/'记录/本次区域输入清单.csv',index=False)
checks['raw_files']=m.groupby('source').bytes.agg(['count','sum']).to_dict('index')
# Independent single-sounding retrieval from the native NetCDF and comparison to each regional record.
for yr in (2023,2024,2025):
    cat=pd.read_csv(ROOT/'记录'/f'卫星下载_{yr}-01.csv')
    rec=cat[cat.valid>0].iloc[len(cat[cat.valid>0])//2]
    with np.load(ROOT/'原始数据/S5P'/(rec.orbit+'.npz')) as subset:
        ix=np.flatnonzero((subset['qa']>.75)&np.isfinite(subset['no2']))[0]
        i,j=int(subset['row'][ix]),int(subset['col'][ix])
        with h5py.File(Reader(rec.url),'r') as f:
            g=f['PRODUCT']
            for src,dst in [('longitude','lon'),('latitude','lat'),('qa_value','qa'),('nitrogendioxide_tropospheric_column','no2')]:
                a=g[src];val=decoded(a,a[0,i:i+1,j])
                assert np.isclose(val[0],subset[dst][ix],rtol=1e-7,atol=1e-12)
            ut=pd.Timestamp(g['time'].attrs['units'].decode().split('since ')[1])+pd.to_timedelta(float(g['time'][0]),unit='s')+pd.to_timedelta(int(g['delta_time'][0,i]),unit='ms')
            assert ut.value//10**6==subset['time_ms'][ix]
        checks[str(yr)+'_satellite_sample']={'orbit':rec.orbit,'row':i,'col':j,'utc':str(ut)}
old=project/'扩展实验/三年地面补采/多源复算/ERA5边界层补采/202401.nc'
with netcdf_file(old,mmap=False) as a,netcdf_file(ROOT/'原始数据/ERA5/2024-01_blh.nc',mmap=False) as b:
    sub=b.variables['BLH'].data
    for axis,key in [(1,'latitude'),(2,'longitude')]:
        ix=[np.flatnonzero(b.variables[key].data==x).item() for x in a.variables[key].data]
        sub=np.take(sub,ix,axis=axis)
    checks['blh_overlap_values']=sub.size
    assert np.array_equal(sub,a.variables['BLH'].data)
pred=pd.read_csv(out/'NO2验证预测.csv.gz');metrics=pd.read_csv(out/'NO2验证.csv')
for r in metrics.itertuples():
    d=pred[pred.run.eq(r.run)]
    assert len(d)==r.n_test
    np.testing.assert_allclose([mean_absolute_error(d.no2,d[c]) for c in ['pred0','pred1']],[r.mae0,r.mae1])
checks['verified_fit_comparisons']=len(metrics)
wx=pd.read_csv(out/'区域气象与超阈值日期.csv')
assert len(wx)==1077 and (wx.iloc[:,-1]>0).sum()==34
checks['region_calendar']={'matched_eligible_days':len(wx),'days_with_heavy_city':int((wx.iloc[:,-1]>0).sum())}
stats=pd.read_csv(out/'逐轨筛选.csv');checks['pixels']=stats[['region_pixels','quality_pixels','city_quality_pixels']].sum().to_dict()
(ROOT/'记录/交叉核验.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2,default=int))
print(json.dumps(checks,ensure_ascii=False,default=int),flush=True)
