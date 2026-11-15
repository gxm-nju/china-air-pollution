"""由 KNMI 月包抽取东部每日数据，支持重新导入下载的三个原始 ZIP。需 GDAL、NumPy。"""
import argparse,csv,hashlib,zipfile,tempfile,re
from pathlib import Path
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
ROOT=Path(__file__).resolve().parents[1]
FIELDS=dict(column='tropospheric_NO2_column_number_density',observations='no_observations',cloud='cloud_radiance_fraction',fraction_local_day='eff_frac_day',uncertainty='tropospheric_NO2_column_number_density_total_uncertainty')
def main(files):
    target=ROOT/'data/raw/s5p';target.mkdir(parents=True,exist_ok=True);(ROOT/'logs').mkdir(exist_ok=True)
    packages=[];days=[]
    for archive in files:
        with archive.open('rb') as s:digest=hashlib.file_digest(s,'sha256').hexdigest()
        with zipfile.ZipFile(archive) as zp,tempfile.TemporaryDirectory() as temp:
            members=sorted(x for x in zp.namelist() if x.endswith('.nc'))
            month=re.search(r'_1D-(\d{6})',members[0]).group(1)
            bundle=f'ESACCI-PREC-L3C-NO2-S5P_TROPOMI_KNMI-0360x0720_1D-{month}-fv2.0.zip'
            packages.append(dict(month=month,bytes_transport_only=archive.stat().st_size,sha256=digest,url='https://d1qb6yzwaaq4he.cloudfront.net/airpollution/no2col/cci-no2/tropomi/2023/'+bundle))
            for member in members:
                day=re.search(r'_1D-(\d{8})',member).group(1)
                p=Path(temp)/'one.nc';p.write_bytes(zp.read(member))
                vals={}
                for key,var in FIELDS.items():
                    d=gdal.Open(f'NETCDF:"{p}":{var}')
                    assert d.GetGeoTransform()==(-180,.5,0,90,0,-.5)
                    # 窗口 [105,125)°E 和 (20,42]°N，对应 40 × 44 个中心格点。
                    a=d.GetRasterBand(1).ReadAsArray(570,96,40,44)
                    vals[key]=a.astype('int32' if key=='observations' else 'float32')
                    d=None
                fname=target/(day+'.npz')
                np.savez_compressed(fname,longitude=np.arange(105.25,125,.5),latitude=np.arange(41.75,20,-.5),**vals)
                days.append(dict(day=day,member=member,netcdf_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),regional_bytes=fname.stat().st_size,regional_sha256=hashlib.sha256(fname.read_bytes()).hexdigest(),valid_cells=int((np.isfinite(vals['column'])&(vals['observations']>0)).sum())))
    for name,rows in [('satellite_downloads.csv',packages),('satellite_daily_windows.csv',days)]:
        with (ROOT/'logs'/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print('days',len(days),'bytes',sum(x['regional_bytes'] for x in days))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('archives',type=Path,nargs='+');main(ap.parse_args().archives)
