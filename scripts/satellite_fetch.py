"""Retrieve native-resolution COG windows. Resolve actual keys by acquisition and orbit.
A collection can contain multiple processing versions. Choose the requested version
if it exists in MEEO, else the most recent complete pair for the same orbit.
"""
import argparse
import hashlib
import datetime as dt
import json
import re
import time
import urllib.parse as url
import urllib.request as req
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds
from sources import RAW, ROOT

BASE='https://meeo-s5p.s3.eu-central-1.amazonaws.com/'
CDSE='https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
COL='PRODUCT_nitrogendioxide_tropospheric_column_4326.tif'
QA='PRODUCT_qa_value_4326.tif'
UTC='utctime_4326.tif'
def bytes_at(address):
    for attempt in range(3):
        try:
            with req.urlopen(address,timeout=65) as r:return r.read()
        except OSError:
            if attempt==2:raise
            time.sleep(2**attempt)
def orbits(month,wide=False):
    start=dt.date.fromisoformat(month+'-01');end=(start.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    footprint="POLYGON((105 20,135 20,135 54,105 54,105 20))" if wide else "POINT(118.8 32.05)"
    query=f"Collection/Name eq 'SENTINEL-5P' and startswith(Name,'S5P_OFFL_L2__NO2____') and ContentDate/Start ge {start}T00:00:00.000Z and ContentDate/Start lt {end}T00:00:00.000Z and OData.CSC.Intersects(area=geography'SRID=4326;{footprint}')"
    address=CDSE+'?'+url.urlencode({'$filter':query,'$select':'Name,ContentDate','$top':1000})
    cat=RAW/'s5p'/('east_catalog_' if wide else 's5p_catalog_')
    cat=cat.with_name(cat.name+month.replace('-','')+'.json')
    if cat.exists():return json.loads(cat.read_text())['value']
    data=[]
    while address:
        page=json.loads(bytes_at(address));data+=page['value'];address=page.get('@odata.nextLink')
    cat.write_text(json.dumps({'query':query,'value':data},ensure_ascii=False))
    return data
def resolve(name):
    stem=name.removesuffix('.nc');m=re.search(r'____(\d{8})T\d{6}_\d{8}T\d{6}_\d{5}',stem)
    if not m:raise ValueError(name)
    day=m[1];path=f'COGT/OFFL/L2__NO2___/{day[:4]}/{day[4:6]}/{day[6:]}/'
    prefix=path+stem[:m.end()]
    listing=ET.fromstring(bytes_at(BASE+'?'+url.urlencode({'list-type':'2','prefix':prefix})))
    keys=[k.text for k in listing.findall('.//{*}Key') if k.text]
    families={k[:-len(COL)] for k in keys if k.endswith(COL)}
    pairs=sorted(k for k in families if k+QA in keys)
    if not pairs:return {}
    head=next((k for k in pairs if k==path+stem+'_'),pairs[-1])
    return {band:BASE+head+band for band in (COL,QA,UTC) if head+band in keys}
def crop(address,dest,bounds):
    temp=dest.with_suffix('.part.tif')
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_MAX_RETRY=2,GDAL_HTTP_TIMEOUT=80),rasterio.open(address) as src:
        if src.crs.to_epsg()!=4326: raise ValueError('unexpected CRS')
        native=from_bounds(*bounds,src.transform);lo=int(np.floor(native.col_off));top=int(np.floor(native.row_off));right=int(np.ceil(native.col_off+native.width));bottom=int(np.ceil(native.row_off+native.height))
        w=Window(lo,top,right-lo,bottom-top).intersection(Window(0,0,src.width,src.height))
        pr=src.profile.copy();pr.update(width=int(w.width),height=int(w.height),transform=src.window_transform(w),compress='deflate',tiled=False);pr.pop('blockxsize',None);pr.pop('blockysize',None)
        with rasterio.open(temp,'w',**pr) as out:
            out.write(src.read(window=w));out.update_tags(**src.tags());out.update_tags(1,**src.tags(1))
            out.scales=src.scales;out.offsets=src.offsets
    temp.replace(dest)
def collect(month,wide=False):
    dest=RAW/'s5p'/('east_clips' if wide else 'pilot_clips');dest.mkdir(exist_ok=True)
    log=ROOT/'扩展实验/运行日志/satellite_download.jsonl';log.parent.mkdir(parents=True,exist_ok=True);miss=0
    saved={}
    if log.exists():
        for line in log.read_text().splitlines():
            record=json.loads(line)
            if record.get('sha256'):saved[record['path']]=record
    def filehash(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

    for obj in orbits(month,wide):
        name=obj['Name']
        try:
            keys=resolve(name)
            if not keys:raise RuntimeError('no paired COG in actual bucket')
            for layer,address in keys.items():
                # Keep the CDSE study ID locally; record the precise MEEO source key separately.
                p=dest/(name[:-3]+'_'+layer)
                if p.exists():
                    rec=saved.get(str(p.relative_to(ROOT)))
                    if rec and p.stat().st_size==rec['bytes'] and filehash(p)==rec['sha256']:continue
                    raise ValueError(f'已有裁片未通过历史校验，保留原件 {p.name}')
                crop(address,p,(105,20,135,54) if wide else (114,27,124,36))
                with log.open('a') as f:f.write(json.dumps(dict(time=dt.datetime.now(dt.timezone.utc).isoformat(),item=name,url=address,path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=filehash(p)))+'\n')
        except Exception as e:
            miss+=1
            with log.open('a') as f:f.write(json.dumps(dict(item=name,error=str(e)))+'\n')
    return miss
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('month');p.add_argument('--east',action='store_true');a=p.parse_args()
    raise SystemExit(bool(collect(a.month,a.east)))
