"""Independent reconciliation of files, aggregates, time units, controls, and resumable transfer."""
from pathlib import Path
import sys,hashlib,io,importlib.metadata,json,tempfile
import pandas as pd
import numpy as np
import rasterio
from unittest.mock import patch
from ground import ROOT,YRD
from collect import fetch
E=ROOT/'扩展实验'; B=ROOT/'多源数据与实验'; A=E/'跨期分析'; Q=E/'核验'; M=E/'多源复算'
def main():
    old=json.loads((ROOT/'results/summary.json').read_text());new=json.loads((E/'十月复算/summary.json').read_text())
    for k in old:assert np.isclose(old[k],new[k])
    pilot=pd.read_parquet(ROOT/'data/cleaned/city_weather.parquet').sort_values(['city','time_bjt']).reset_index(drop=True)
    met=pd.read_parquet(E/'环境复算/cleaned/city_weather.parquet').sort_values(['city','time_bjt']).reset_index(drop=True)
    pd.testing.assert_frame_equal(pilot[met.columns],met,check_dtype=False)
    d=pd.read_parquet(A/'全国城市日.parquet');h=pd.read_parquet(A/'全国城市小时.parquet')
    assert not d.duplicated(['city','date']).any() and not h.duplicated(['city','time']).any()
    files=pd.read_csv(A/'地面文件校验.csv',parse_dates=['date'])
    sample=[];roster=pd.read_csv(A/'站点匹配明细.csv')
    for row in files.sample(12,random_state=426).itertuples():
        p=ROOT/row.path
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row.sha256
        raw=pd.read_csv(p);names=roster.loc[roster.city.eq('南京'),'station'];raw=raw[raw.type.eq('PM2.5')].set_index('hour')
        hourly=raw[raw.columns.intersection(names)].mask(lambda x:x<0).mean(axis=1)
        v=d[(d.city=='南京')&(d.date==row.date)]
        assert np.isclose(hourly.mean(),v.pm25.iloc[0]) and hourly.count()==v.valid_hours.iloc[0]
        sample.append((row.date,hourly.count(),hourly.mean(),v.pm25.iloc[0]))
    pd.DataFrame(sample,columns=['日期','有效小时','从原始CSV重算','分析表数值']).to_csv(Q/'南京12日独立抽查.csv',index=False)
    spring=pd.read_csv(A/'春节比较.csv');assert spring.loc[spring['实有日期数']==0,'重污染城市日'].isna().all()
    sat=pd.read_csv(M/'data/cleaned/s5p_city_day.csv',parse_dates=['date','effective_time'])
    tests=[]
    for row in sat[sat.valid].sample(200,random_state=20261115).itertuples():
        p=B/'data/raw/s5p'/f'{row.date:%Y%m%d}.npz'
        with np.load(p) as n:
            i=np.flatnonzero(n['latitude']==row.grid_lat)[0];j=np.flatnonzero(n['longitude']==row.grid_lon)[0]
            dt=row.date+pd.Timedelta(days=float(n['fraction_local_day'][i,j]))+pd.Timedelta(hours=(120-row.grid_lon)/15)
            assert abs((dt-row.effective_time).total_seconds())<.00001 and np.isclose(row.column_1e15,n['column'][i,j]/1e15)
            tests.append((row.city,row.date,row.grid_lat,row.grid_lon,dt,row.effective_time))
    pd.DataFrame(tests,columns=['城市','日','纬度','经度','复算L3有效北京时间','分析时刻']).to_csv(Q/'卫星200条时刻复算.csv',index=False)
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td);p=tmp/'test.csv';part=tmp/'test.csv.part'
        b=b'latitude,longitude,acq_date,acq_time\n32.0,118.0,2024-01-01,1000\n';n=23
        class Resp(io.BytesIO):pass
        def check(req,timeout):
            assert req.get_header('Range')==f'bytes={n}-' and req.get_header('If-range')=='"test"'
            resp=Resp(b[n:]);resp.status=206;resp.headers={'Content-Range':f'bytes {n}-{len(b)-1}/{len(b)}','ETag':'"test"'};return resp
        url='https://example.invalid/fixture';part.write_bytes(b[:n]);part.with_suffix('.part.json').write_text(json.dumps({'url':url,'validator':'"test"'}))
        with patch('collect.ROOT',tmp),patch('collect.log'),patch('urllib.request.urlopen',check):fetch({'group':'firms','url':url},p)
        assert p.read_bytes()==b
    assert len(pd.read_csv(Q/'站点200条空间核验.csv'))==len(pd.read_csv(Q/'火点200条空间核验.csv'))==200
    print('PASS 原十月所有汇总指标一致；五气象变量及风速逐城小时一致；12个随机南京日从原CSV独立复算；200个L3有效时刻和单位复算；HTTP 206断点拼接离线测试；抽样表行数；缺数留空。')
    pkgs=['numpy','pandas','xarray','scipy','pyarrow','scikit-learn','rasterio','duckdb','osmium','shapely','matplotlib']
    versions={p:importlib.metadata.version(p) for p in pkgs}
    (E/'运行环境.json').write_text(json.dumps({'python':sys.executable,'version':sys.version,'packages':versions,'satellite_l2_pixel_time_present':any((ROOT/'data/raw/s5p').rglob('*utctime*.tif'))},indent=2,ensure_ascii=False))
    (ROOT/'运行依赖/requirements.txt').write_text(''.join(f'{k}=={v}\n' for k,v in versions.items()))
if __name__=='__main__':main()
