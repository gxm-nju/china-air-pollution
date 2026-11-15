"""Build a verifiable download ledger. Run from any working directory."""
import calendar
import csv
import datetime as dt
import html
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw'
VARS = {'159_blh':'BLH','165_10u':'VAR_10U','166_10v':'VAR_10V','167_2t':'VAR_2T','134_sp':'SP'}
def make_records():
    rows = []
    def add(group, name, url, scope):
        rows.append(dict(group=group, name=name, url=url, scope=scope))
    for y in range(2019,2026):
        for sensor in ('modis','viirs-snpp','viirs-jpss1'):
            n=f'{sensor}_{y}_China.csv'
            add('firms',n,f'https://firms.modaps.eosdis.nasa.gov/data/country/{sensor}/{y}/{n}','中国年度')
    for i in range(1096):
        d=dt.date(2023,1,1)+dt.timedelta(days=i)
        n=f'china_sites_{d:%Y%m%d}.csv'
        add('air',n,'https://quotsoft.net/air/data/'+n,'全国日文件')
    for y in range(2022,2026):
        for m in range(1,13):
            if y==2022 and m!=12: continue
            ym=f'{y}{m:02d}'; end=calendar.monthrange(y,m)[1]
            for code,v in VARS.items():
                n=f'e5.oper.an.sfc.128_{code}.ll025sc.{ym}0100_{ym}{end}23.nc'
                start=24-8 if (y,m)==(2022,12) else 0
                first=end if (y,m)==(2022,12) else 1
                url=f'https://tds.gdex.ucar.edu/thredds/ncss/grid/files/d633000/e5.oper.an.sfc/{ym}/{n}?var={v}&north=36&south=27&west=114&east=124&time_start={y}-{m:02d}-{first:02d}T{start:02d}:00:00Z&time_end={y}-{m:02d}-{end}T23:00:00Z&accept=netcdf3&addLatLon=true'
                add('era5',n,url,'长三角及上游 114–124°E、27–36°N')
    add('metadata','Station_information.csv','https://zenodo.org/records/10892980/files/Station_information.csv?download=1','站点编号、城市与坐标（历史清单）')
    add('osm','china-261114.osm.pbf','https://download.geofabrik.de/asia/china-261114.osm.pbf','全国快照；以校验值定位此次版本')
    return list({(r['group'],r['name']):r for r in rows}.values())

def write_catalog(rows):
    with (ROOT/'docs/下载清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
        out=csv.DictWriter(f,fieldnames=rows[0]);out.writeheader();out.writerows(rows)
if __name__=='__main__':
    rows=make_records();write_catalog(rows)
