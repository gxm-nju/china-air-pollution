"""Count inputs once, generate reproducible checksums and a conservative data-size ledger."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from ground import RAW,CL,IN,OUT,ROOT,YRD
from sources import make_records
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(4*1024*1024):h.update(chunk)
    return h.hexdigest()
def run():
    rows=make_records();url_map={x['name']:x['url'] for x in rows}
    ledger=[]
    for p in sorted(RAW.rglob('*')):
        if not p.is_file():continue
        group=p.relative_to(RAW).parts[0];name=p.name
        link=url_map.get(name,'')
        kind='网页下载'
        if group=='s5p' and name.endswith('.tif'):
            day=name.split('____')[1][:8];link=f'https://meeo-s5p.s3.eu-central-1.amazonaws.com/COGT/OFFL/L2__NO2___/{day[:4]}/{day[4:6]}/{day[6:]}/{name}'
        elif group=='s5p' and 'catalog' in name:
            link="https://catalogue.dataspace.copernicus.eu/odata/v1/Products";kind='目录元数据'
        elif name=='station_cells.osm.pbf':kind='相关对象子集';link='scripts/osm_extract.py'
        ledger.append(dict(group=group,name=name,path=str(p.relative_to(ROOT)),kind=kind,url_or_script=link,bytes=p.stat().st_size,sha256=sha(p)))
    l=pd.DataFrame(ledger);l.to_csv(ROOT/'logs/原始文件校验与来源.csv',index=False,encoding='utf-8-sig')
    sizes=[];sample=ROOT/'data/effective';sample.mkdir(exist_ok=True)
    def add(group,total,subset,note):
        sizes.append(dict(source=group,downloaded_bytes=int(total),relevant_subset_bytes=int(subset),method=note))
    totals=l[l.kind=='网页下载'].groupby('group').bytes.sum()
    from ground import sites
    stations=set(sites().station)
    sub=sample/'air';sub.mkdir(exist_ok=True)
    for p in (RAW/'air').glob('*.csv'):
        t=pd.read_csv(p,dtype=str,keep_default_na=False)
        t.loc[t.type.isin(['PM2.5','NO2','PM10','SO2','O3','CO','AQI']),[c for c in t.columns if c in stations or c in ['date','hour','type']]].to_csv(sub/(p.stem+'.csv.gz'),index=False,compression={'method':'gzip','mtime':0,'compresslevel':5})
    add('air',totals.air,sum(p.stat().st_size for p in sub.glob('*')),'全国已匹配站点、七种小时值；原值子表 gzip')
    sub=sample/'firms';sub.mkdir(exist_ok=True)
    for p in (RAW/'firms').glob('*.csv'):
        t=pd.read_csv(p,dtype=str,keep_default_na=False);mask=t.longitude.astype(float).between(113.875,124.125)&t.latitude.astype(float).between(26.875,36.125)
        t[mask].to_csv(sub/(p.stem+'.csv.gz'),index=False,compression={'method':'gzip','mtime':0,'compresslevel':5})
    add('firms',totals.firms,sum(p.stat().st_size for p in sub.glob('*')),'七份中国年度文件中长三角及外围窗口原值，含质量筛选所需类型和置信度；gzip')
    sub=sample/'era5';sub.mkdir(exist_ok=True)
    rawmet=pd.read_parquet(next((CL/'era5').glob('202410*/grid.parquet')))
    cells=sites().query('city in @YRD')[['gx','gy']].drop_duplicates()
    fire=pd.read_parquet(CL/'firms/year=2024/events.parquet')
    t=fire[~fire.recurring_heat_flag & fire.time_bjt.between('2024-10-01','2024-11-01',inclusive='left')].copy()
    t['time_bjt']=t.time_bjt.dt.floor('h')
    ri=rawmet[rawmet.time_bjt.between('2024-10-01','2024-11-01',inclusive='left')]
    met=pd.concat([ri.merge(cells),ri.merge(t[['gx','gy','time_bjt']].drop_duplicates())]).drop_duplicates(['gx','gy','time_bjt'])
    era=sub/'used_grid_observations.npz';cols=['u10','v10','t2m_K','blh_m','sp_Pa']
    np.savez_compressed(era,grid_lon=met.gx.to_numpy(),grid_lat=met.gy.to_numpy(),utc_hours_since_1900=((met.time_bjt-pd.Timedelta(hours=8)-pd.Timestamp('1900-01-01'))/pd.Timedelta(hours=1)).astype('int32'),**{c:met[c].to_numpy() for c in cols})
    add('era5',totals.era5,era.stat().st_size,'站点网格×研究时段、火点网格×发生小时取并集；五变量原值和坐标压缩 NPZ')
    sat=list((CL/'s5p').glob('*.tif'))
    add('s5p',totals.s5p,sum(p.stat().st_size for p in sat),'原分辨率 114–124°E、27–36°N 逐轨裁片，含掩膜和填充值；是站点直接使用量的上界')
    add('osm',totals.osm,(RAW/'osm/station_cells.osm.pbf').stat().st_size,'与站点网格相交的道路/工业用地原对象及必要节点；保留完整源要素')
    pd.DataFrame(sizes).to_csv(OUT/'规模核算.csv',index=False,encoding='utf-8-sig')
    ledgerdf=pd.DataFrame(rows).drop(columns='url');avail=set(l.name);ledgerdf['on_disk']=ledgerdf.name.isin(avail);ledgerdf.to_csv(ROOT/'logs/采集缺口.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(sizes).to_string(index=False))
if __name__=='__main__':run()
