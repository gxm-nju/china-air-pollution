"""Verify completed inputs, queue winter first and resume interrupted HTTP responses."""
import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import json
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from sources import ROOT,RAW,make_records

EXT=ROOT/'扩展实验'
BASE=ROOT/'多源数据与实验'
LOG=EXT/'运行日志/续采.jsonl'
def log(**row):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open('a') as f:f.write(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),**row},ensure_ascii=False)+'\n')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verified_paths():
    checks={}
    for ledger,base in [(ROOT/'logs/原始文件校验与来源.csv',ROOT),(BASE/'logs/SHA256SUMS.csv',BASE)]:
        if ledger.is_file():
            for r in csv.DictReader(ledger.open(encoding='utf-8-sig')):
                if r['path'].startswith('data/raw/'):checks[base/r['path']]=(int(r['bytes']),r['sha256'])
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r=json.loads(line)
            if r.get('status')=='ok':checks[ROOT/r['path']]=(r['bytes'],r['sha256'])
    return checks
def validated(path,group):
    if not path.stat().st_size:raise ValueError('empty response')
    with path.open('rb') as f:first=f.read(65536)
    if first.lstrip().lower().startswith((b'<html',b'<!doctype',b'<?xml')):raise ValueError('HTML/XML response')
    if group=='air':
        with path.open(encoding='utf-8-sig',newline='') as f:
            rows=csv.reader(f);head=next(rows);stamp=re.search(r'(\d{8})\.csv',path.name)[1]; keys=set()
            if head[:3]!=['date','hour','type'] or len(head)<100:raise ValueError('invalid station header')
            for r in rows:
                if len(r)!=len(head) or r[0]!=stamp or not 0<=int(r[1])<=23 or (r[1],r[2]) in keys:raise ValueError('invalid station record')
                keys.add((r[1],r[2]))
            if not any(k[1]=='PM2.5' for k in keys):raise ValueError('no PM2.5 records')
    if group=='firms' and b'acq_date' not in first.splitlines()[0]:raise ValueError('invalid FIRMS CSV')
    if group=='era5' and not first.startswith((b'CDF',b'\x89HDF')):raise ValueError('invalid NetCDF')
def fetch(row,dest):
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+'.part');info=tmp.with_suffix('.part.json')
    meta=json.loads(info.read_text()) if info.exists() else {}
    off=tmp.stat().st_size if tmp.exists() and meta.get('url')==row['url'] and meta.get('validator') else 0
    headers={'Range':f'bytes={off}-','If-Range':meta['validator']} if off else {}
    with urllib.request.urlopen(urllib.request.Request(row['url'],headers=headers),timeout=90) as r:
        partial=(r.status==206);content_range=r.headers.get('Content-Range','')
        if partial:
            m=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',content_range)
            if not m or int(m[1])!=off or int(m[2])+1!=int(m[3]):raise ValueError('unexpected partial response')
            expected=int(m[3])
        else:
            expected=int(r.headers['Content-Length']) if 'Content-Length' in r.headers else None
        validator=r.headers.get('ETag') or r.headers.get('Last-Modified')
        if partial and off and validator!=meta['validator']:raise ValueError('source changed during resume')
        info.write_text(json.dumps({'url':row['url'],'validator':validator}))
        with tmp.open('ab' if partial else 'wb') as f:shutil.copyfileobj(r,f,1024*1024)
    if expected is not None and tmp.stat().st_size!=expected:raise ValueError('incomplete download')
    validated(tmp,row['group']);h=sha(tmp);tmp.replace(dest);info.unlink(missing_ok=True)
    log(status='ok',path=str(dest.relative_to(ROOT)),url=row['url'],bytes=dest.stat().st_size,sha256=h)
def run(scope,plan_only,groups):
    checks=verified_paths();schedule=[]
    cal={r['date'] for r in csv.DictReader((BASE/'data/cleaned/spring_calendar.csv').open()) if r['spring_break']=='True'} if BASE.exists() else set()
    festive={str(dt.date.fromisoformat(day)+dt.timedelta(days=offset)) for day in cal for offset in range(-7,8)}
    for r in make_records():
        g,n=r['group'],r['name']
        if g not in groups:continue
        dest=RAW/g/n;alternates=[]
        if g=='air':alternates=[BASE/'data/raw/ground'/n]
        if g=='firms':alternates=[BASE/'data/raw/firms'/n]
        if scope=='pilot':
            if g=='air' and '202410' not in n:continue
            if g=='era5' and not any(x in n for x in ('2024100100','2024090100')):continue
            if g=='era5' and '2024090100' in n:r=dict(r,url=r['url'].replace('2024-09-01T00:00:00Z','2024-09-30T16:00:00Z'))
            if g=='firms' and '_2024_' not in n:continue
        elif g=='era5':
            dest=RAW/'era5/east'/n;r=dict(r,url=r['url'].replace('north=36&south=27&west=114&east=124','north=54&south=20&west=105&east=135'))
        state='待下载';local=''
        for p in [dest,*alternates]:
            if p.is_file():
                if p not in checks:state='无历史校验值，待核对';local=str(p.relative_to(ROOT));continue
                size,h=checks[p]
                if size!=p.stat().st_size or sha(p)!=h:raise ValueError(f'既有文件校验失败 {p}')
                state='已校验';local=str(p.relative_to(ROOT));break
        date=n[-12:-4] if g=='air' else ''
        ym=date[4:6] if date else re.search(r'\.(\d{4})(\d{2})0100_',n)[2] if g=='era5' else ''
        iso=f'{date[:4]}-{date[4:6]}-{date[6:]}' if date else ''
        priority=0 if iso in festive else 1 if ym in ['12','01','02'] else 2
        schedule.append(dict(group=g,name=n,priority=priority,status=state,local=local,target=str(dest.relative_to(ROOT)),url=r['url']))
    schedule.sort(key=lambda r:(r['priority'],r['group'],r['name']))
    path=EXT/f'下载计划_{scope}.csv'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['group','name','priority','status','local','target','url']);w.writeheader();w.writerows(schedule)
    if 's5p' in groups:
        months=['2024-10'] if scope=='pilot' else [f'{y}-{m:02d}' for y in range(2023,2026) for m in range(1,13)]
        with (EXT/f'卫星轨道补采_{scope}.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['月份','优先级','已存完整东部L2三层轨道数','任务'])
            for m in sorted(months,key=lambda m:(m[-2:] not in ('01','02','12'),m)):
                prefixes=[p.name.split('_PRODUCT_')[0] for p in (RAW/'s5p/east_clips').glob(f'*____{m.replace("-","")}*_PRODUCT_qa_value_4326.tif')]
                done=sum(all((RAW/'s5p/east_clips'/(s+end)).is_file() for end in ('_PRODUCT_nitrogendioxide_tropospheric_column_4326.tif','_utctime_4326.tif')) for s in prefixes)
                w.writerow([m,1 if m[-2:] in ('01','02','12') else 2,done,'检索相交轨道并获取柱浓度、QA、像元UTC'])
    if plan_only:print('清单行数',len(schedule),'已校验',sum(r['status']=='已校验' for r in schedule));return 0
    blocked=set();errors=sum(r['status']=='无历史校验值，待核对' for r in schedule)
    for r in schedule:
        if r['status']!='待下载':continue
        host=urllib.parse.urlparse(r['url']).hostname
        if host in blocked:continue
        try:fetch(r,ROOT/r['target'])
        except (OSError,ValueError) as e:
            errors+=1;log(status='failure',name=r['name'],url=r['url'],error=str(e))
            if isinstance(e,urllib.error.URLError) and (not isinstance(e,urllib.error.HTTPError) or e.code in [401,403,429]):blocked.add(host)
    if 's5p' in groups:
        from satellite_fetch import collect
        months=['2024-10'] if scope=='pilot' else sorted([f'{y}-{m:02}' for y in range(2023,2026) for m in range(1,13)],key=lambda x:(x[-2:] not in ('01','02','12'),x))
        for m in months:
            try:errors+=collect(m,wide=scope=='full')
            except OSError as e:log(status='satellite_unavailable',month=m,error=str(e));errors+=1;break
    return int(bool(errors))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('scope',choices=['pilot','full']);p.add_argument('--plan-only',action='store_true');p.add_argument('--groups',nargs='+',choices=['air','era5','firms','s5p','metadata','osm'],default=['air','era5','firms','s5p','metadata','osm']);a=p.parse_args()
    EXT.mkdir(exist_ok=True)
    with (EXT/'采集.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('已有此采集器运行')
        raise SystemExit(run(a.scope,a.plan_only,a.groups))
