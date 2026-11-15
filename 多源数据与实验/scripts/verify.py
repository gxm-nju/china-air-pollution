"""核对数据完整性、跨源连接、分组边界和报告。"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import platform
import sys
from datetime import datetime,timezone
from html.parser import HTMLParser
import duckdb
import numpy as np
import pandas as pd
import sklearn
import matplotlib

ROOT=Path(__file__).resolve().parents[1]
def h(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file,'sha256').hexdigest()
def run(check_hash=False):
    O=ROOT/'results'
    snap=lambda key:json.loads((O/(key+'.json')).read_text())
    codes=snap('ground_summary');f=snap('fire_summary');era=snap('fusion_summary')
    assert f['bytes']==558827644 and f['files']==21
    dates=pd.read_csv(O/'ground_date_inventory.csv')
    assert codes['days']==dates.file_validated.sum() and len(dates)==1096 and not dates.date.duplicated().any()
    assert codes['days']+codes['missing']==1096
    assert codes['yrd_episodes']==len(pd.read_csv(O/'episode_cluster.csv'))
    assert pd.read_csv(O/'episode_centers.csv').n.sum()==era['eligible_episode_clusters']
    for rel in ['fire_map_sample_200.csv','station_map_sample_200.csv']:
        assert len(pd.read_csv(O/rel))==200
    pr=pd.read_csv(O/'monthly_bulletins.csv')
    assert len(pr)==72 and set(pr.query("region=='长三角' and month<'2024'").city_count)=={41}
    assert set(pr.query("region=='长三角' and month>='2024'").city_count)=={31}
    cp=duckdb.connect()
    path=str(ROOT/'data/integrated/yrd_ground_era5_hour.parquet')
    assert cp.execute('SELECT count(*) FROM read_parquet(?)',[path]).fetchone()[0]==era['yz_ground_matched']
    total,uniq=cp.execute('SELECT count(*),count(distinct (city,time)) FROM read_parquet(?)',[path]).fetchone()
    assert total==uniq
    q=cp.execute("SELECT COUNT(*),COUNT(pm25),SUM(CASE WHEN pm25<0 THEN 1 ELSE 0 END) FROM read_parquet(?)",[str(ROOT/'data/cleaned/parquet/ground/*/*/*.parquet')]).fetchone()
    assert q[1]==snap('parquet_qa')['ground']['valid_pm25'] and q[2]==0
    n=pd.read_csv(ROOT/'data/integrated/nanjing_dust_era5_hour.csv')
    peak=n.loc[n.PM10.idxmax()]
    assert peak.PM10==600 and peak.wind_from_deg==316 and abs(peak.ws_ms-5.55)<.01
    s=pd.read_csv(O/'fire_lag.csv')
    assert s.lag.tolist()==[0,6,12,24,48] and (s.ci_low<=s.mean_delta).all() and (s.mean_delta<=s.ci_high).all()
    report=(ROOT/'中国城市重污染日_阶段实验报告.html').read_text()
    assert report.count('data:image/png;base64,')==6 and '2025-12' in report
    ss=snap('no2_summary')
    assert len(list((ROOT/'data/raw/s5p').glob('*.npz')))==90
    assert len(list((ROOT/'data/raw/osm').glob('*.pbf')))==4
    mm=pd.read_csv(O/'no2_model_metrics.csv')
    assert len(mm)==18 and ss['matched']==cp.execute('SELECT COUNT(*) FROM read_parquet(?)',[str(ROOT/'data/integrated/no2_four_sources.parquet')]).fetchone()[0]
    assert ss['matched']<=ss['valid_satellite']<=ss['eligible_citydays']
    if check_hash:
        manifest=pd.read_csv(ROOT/'logs/SHA256SUMS.csv')
        for item in manifest.itertuples(index=False):
            p=ROOT/item.path
            assert p.stat().st_size==item.bytes and h(p)==item.sha256,item.path
        print('SHA-256 校验通过，文件数',len(manifest))
    print('逻辑核验通过；火点/站点/气象 Parquet、三源连接、月报口径、有效阈值、报告图件均通过断言。')
if __name__=='__main__':
    arg=argparse.ArgumentParser();arg.add_argument('--hash',action='store_true')
    run(arg.parse_args().hash)
