"""Extract native swath pixels by HTTP ranges from public OFFL NetCDF; save original packed columns."""
from catalog import ROOT,S3,session
import sys,io,re,hashlib,time,struct,zipfile,json,os
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import h5py
class Reader(io.RawIOBase):
    block=1024*1024
    def __init__(self,url):
        self.s=session();self.url=url;self.pos=0;self.cache={};self.network=0
        r=self.s.get(url,headers={'Range':f'bytes=0-{self.block-1}'},timeout=(20,60))
        r.raise_for_status()
        assert r.status_code==206 and r.headers['Content-Range'].startswith('bytes 0-')
        self.size=int(r.headers['Content-Range'].split('/')[1]);self.cache[0]=r.content;self.network=len(r.content)
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,p,whence=0):
        self.pos=(0,self.pos,self.size)[whence]+p
        return self.pos
    def readinto(self,buf):
        length=min(len(buf),self.size-self.pos)
        if length<=0:return 0
        start=self.pos;end=start+length;first=start//self.block;last=(end-1)//self.block
        for i in range(first,last+1):
            if i in self.cache:continue
            j=i
            while j<last and j+1 not in self.cache:j+=1
            a=i*self.block;b=min((j+1)*self.block,self.size)-1
            r=self.s.get(self.url,headers={'Range':f'bytes={a}-{b}'},timeout=(20,75))
            r.raise_for_status()
            assert r.headers.get('Content-Range')==f'bytes {a}-{b}/{self.size}' and len(r.content)==b-a+1
            self.network+=len(r.content)
            for k in range(i,j+1):self.cache[k]=r.content[(k-i)*self.block:(k-i+1)*self.block]
        view=memoryview(buf)
        for i in range(first,last+1):
            a=max(start,i*self.block);b=min(end,(i+1)*self.block)
            view[a-start:b-start]=self.cache[i][a-i*self.block:b-i*self.block]
        self.pos=end;return length
class StoredMember(io.RawIOBase):
    """Random access to a stored HDF5 member without transferring the whole orbit."""
    def __init__(self, remote, offset, size):
        self.remote, self.offset, self.size, self.pos = remote, offset, size, 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = (0, self.pos, self.size)[whence] + offset
        if self.pos < 0:
            raise ValueError('negative member offset')
        return self.pos

    def readinto(self, buf):
        available = min(len(buf), self.size - self.pos)
        if available <= 0:
            return 0
        self.remote.seek(self.offset + self.pos)
        n = self.remote.readinto(memoryview(buf)[:available])
        self.pos += n
        return n

@contextmanager
def netcdf(remote, name):
    remote.seek(0)
    header = remote.read(8)
    remote.seek(0)
    stream = remote
    if header.startswith(b'PK'):
        with zipfile.ZipFile(remote) as archive:
            members = [m for m in archive.infolist() if m.filename.split('/')[-1].startswith(name + '_') and m.filename.endswith('.nc')]
            if len(members) != 1 or members[0].compress_type != zipfile.ZIP_STORED:
                raise ValueError('unexpected ZIP layout or compression')
            member = members[0]
            remote.seek(member.header_offset)
            local = remote.read(30)
            if local[:4] != b'PK\x03\x04':
                raise ValueError('invalid ZIP local header')
            name_len, extra_len = struct.unpack_from('<HH', local, 26)
            offset = member.header_offset + 30 + name_len + extra_len
            stream = StoredMember(remote, offset, member.file_size)
    with h5py.File(stream, 'r') as f:
        yield f

def scalar(d,key,default):
    return float(np.asarray(d.attrs.get(key,default)).item())
def decoded(d,a):
    b=a.astype(float)
    b[a==scalar(d,'_FillValue',-99999)]=np.nan
    return b*scalar(d,'scale_factor',1)+scalar(d,'add_offset',0)
def validate(p):
    with np.load(p,allow_pickle=False) as a:
        n=len(a['lat'])
        assert all(len(a[k])==n for k in ('lon','time_ms','qa','no2','row','col'))
        assert np.all((a['lat']>=28)&(a['lat']<=35)&(a['lon']>=115.5)&(a['lon']<=122.5))
        assert len(np.unique(a['row'].astype('int64')*10000+a['col']))==n
        match=re.search(r'____(\d{8}T\d{6})_(\d{8}T\d{6})_',p.name)
        lo,hi=(pd.Timestamp(x).value//10**6 for x in match.groups())
        assert np.all((a['time_ms']>=lo-1000)&(a['time_ms']<=hi+1000))
        q=a['qa'][np.isfinite(a['qa'])]
        assert np.all((q>=0)&(q<=1))
        return n,int(((a['qa']>.75)&np.isfinite(a['no2'])).sum())
def alternate_product(rec):
    scene = rec.CDSE.removesuffix('.nc')
    day = rec.orbit.split('____')[1][:8]
    return f'https://sentinel5euwest.blob.core.windows.net/sentinel-5p/TROPOMI/L2__NO2___/{day[:4]}/{day[4:6]}/{day[6:]}/{scene}/{scene}.nc'

def extract(rec, alternate=False):
    t=time.monotonic();name=rec.orbit;p=ROOT/'原始数据/S5P'/(name+'.npz');url=S3+str(rec.key)
    provenance=p.with_suffix('.source.json')
    if p.exists():
        if provenance.is_file():
            url=json.loads(provenance.read_text())['url']
        n,q=validate(p);return dict(orbit=name,url=url,pixels=n,valid=q,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    import_dir=os.getenv('S5P_ORIGINAL_DIR')
    local=Path(import_dir)/rec.CDSE if import_dir else None
    source_record=None
    if local is not None and local.is_file():
        day=pd.Timestamp(rec.orbit.split('____')[1][:8])
        url=f'https://data.gesdisc.earthdata.nasa.gov/data/S5P_TROPOMI_Level2/S5P_L2__NO2____HiR.2/{day:%Y}/{day:%j}/{rec.CDSE}'
        with local.open('rb') as stream:
            sha=hashlib.file_digest(stream,'sha256').hexdigest()
        source_record={'url':url,'input_name':local.name,'input_sha256':sha,'access':'user-supplied exact product'}
        remote=local.open('rb')
    elif alternate:
        url=alternate_product(rec)
        response=session().get('https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-5p-l2-netcdf',timeout=30)
        response.raise_for_status()
        token=response.json()['token']
        try:
            remote=Reader(url+'?'+token)
        except Exception as exc:
            if getattr(getattr(exc,'response',None),'status_code',None) != 404:
                raise
            folder,filename=url.rsplit('/',1)
            url=folder.rsplit('/',1)[0]+'/'+filename
            remote=Reader(url+'?'+token)
    else:
        remote=Reader(url)
    with netcdf(remote, name) as f:
        if source_record is not None:
            orbit=int(name.rsplit('_',1)[-1])
            if 'orbit' in f.attrs and int(np.asarray(f.attrs['orbit']).item())!=orbit:
                raise ValueError('source orbit metadata does not match catalogue')
        g=f['PRODUCT'];la=g['latitude'];lo=g['longitude']
        lat=la[0];lon=lo[0]
        rows,cols=np.where((lat>=28)&(lat<=35)&(lon>=115.5)&(lon<=122.5))
        fields=dict(lat=lat[rows,cols],lon=lon[rows,cols],row=rows.astype('int32'),col=cols.astype('int16'))
        dt=g['delta_time']; assert b'millisecond' in dt.attrs['units']
        time_d=g['time'];epoch=pd.Timestamp(time_d.attrs['units'].decode().split('since ')[1]).tz_localize(None)
        seconds=decoded(time_d,time_d[:]).item();offset=decoded(dt,dt[0])
        assert np.isfinite(offset[rows]).all() and b'seconds since' in time_d.attrs['units']
        fields['time_ms']=(epoch.value//10**6+np.rint(seconds*1000+offset[rows]).astype('int64'))
        for var,key in [('nitrogendioxide_tropospheric_column','no2'),('qa_value','qa')]:
            d=g[var]
            if key=='no2':assert d.attrs['units'] in (b'mol m-2',b'mol/m2',b'mol m^-2')
            if len(rows):
                cut=d[0,rows.min():rows.max()+1,:]
                fields[key]=decoded(d,cut[rows-rows.min(),cols]).astype('float32')
            else:fields[key]=np.empty(0,dtype='float32')
        tmp=p.with_suffix('.part.npz')
        np.savez_compressed(tmp,**fields)
    n,q=validate(tmp)
    if source_record is not None:
        remote.close()
    if alternate or source_record is not None:
        provenance.write_text(json.dumps(source_record or {'url':url},ensure_ascii=False))
    tmp.replace(p)
    print(name,n,q,getattr(remote,"network",0),round(time.monotonic()-t,1),flush=True)
    return dict(orbit=name,url=url,pixels=n,valid=q,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def run(r):
    from types import SimpleNamespace
    rec=SimpleNamespace(**r)
    problem='missing MEEO object key'
    if pd.notna(rec.key) and rec.key:
        try:
            return extract(rec)
        except Exception as exc:
            problem=repr(exc)
    try:
        result=extract(rec, alternate=True)
        print(rec.orbit,'same official product from Planetary Computer',flush=True)
        return result
    except Exception as exc:
        status=getattr(getattr(exc,'response',None),'status_code',None)
        reason=f'MEEO: {problem} | Planetary Computer: {type(exc).__name__} HTTP={status}'
        print(rec.orbit,reason,flush=True)
        return dict(orbit=rec.orbit,error=reason)
if __name__=='__main__':
    from concurrent.futures import ProcessPoolExecutor
    import os
    for month in sys.argv[1:]:
        import fcntl
        with (ROOT/'记录'/f'{month}.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            cat=pd.read_csv(ROOT/'记录'/f'轨道清单_{month}.csv')
            with ProcessPoolExecutor(int(os.getenv('SAT_WORKERS','6'))) as ex:
                out=list(ex.map(run,cat.to_dict('records')))
            table=ROOT/'记录'/f'卫星下载_{month}.csv'
            tmp=table.with_suffix('.part.csv')
            pd.DataFrame(out).to_csv(tmp,index=False)
            tmp.replace(table)
