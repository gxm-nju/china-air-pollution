from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests,json,re,sys,time
import pandas as pd
from xml.etree import ElementTree as ET
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[1]
S3='https://meeo-s5p.s3.eu-central-1.amazonaws.com/'
CAT='https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
def session():
    s=requests.Session()
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=.6,status_forcelist=(429,502,503,504))))
    return s
def catalogue(month):
    s=session(); a=pd.Timestamp(month+'-01');b=a+pd.offsets.MonthBegin()
    f=f"Collection/Name eq 'SENTINEL-5P' and startswith(Name,'S5P_OFFL_L2__NO2____') and ContentDate/Start ge {a:%Y-%m-%d}T00:00:00Z and ContentDate/Start lt {b:%Y-%m-%d}T00:00:00Z and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON((115.5 28,122.5 28,122.5 35,115.5 35,115.5 28))')"
    p=ROOT/'记录'/f'轨道_{month}.json'
    if not p.exists():
        r=s.get(CAT,params={'$filter':f,'$select':'Name,Id','$top':1000},timeout=60);r.raise_for_status()
        j=r.json();assert '@odata.nextLink' not in j and j['value']
        p.write_text(json.dumps(j['value']))
    names=[r['Name'] for r in json.loads(p.read_text())]
    def daykeys(day):
        prefix=f'OFFL/L2__NO2___/{day[:4]}/{day[4:6]}/{day[6:8]}/'
        resp=session().get(S3,params={'list-type':2,'prefix':prefix},timeout=30);resp.raise_for_status()
        tree=ET.fromstring(resp.content)
        assert tree.findtext('{*}IsTruncated')=='false'
        return [k.text for k in tree.findall('.//{*}Key') if k.text.endswith('.nc')]
    ds=sorted({n.split('____')[1][:8] for n in names})
    with ThreadPoolExecutor(7) as ex:keys=sum(ex.map(daykeys,ds),[])
    rows=[]
    for stem in sorted({n[:n.find('_03_',44)] for n in names}):
        matched=sorted(k for k in keys if Path(k).name.startswith(stem+'_'))
        rows.append({'orbit':stem,'key':matched[-1] if matched else '', 'CDSE':max(n for n in names if n.startswith(stem))})
    pd.DataFrame(rows).to_csv(ROOT/'记录'/f'轨道清单_{month}.csv',index=False)
    print(month,len(rows),sum(bool(r['key']) for r in rows),flush=True)
if __name__=='__main__':
    for m in sys.argv[1:]: catalogue(m)
