"""生成站点、火点和 ERA5 的年月分区，用 DuckDB 对保存的 Parquet 独立核算。"""
from pathlib import Path
import json
import os
import duckdb
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
con=duckdb.connect()
con.execute("SET threads=2")
base=Path('data/cleaned/parquet')
base.mkdir(exist_ok=True)
for path in sorted(Path('data/raw/ground').glob('*.csv')):
    ds=path.stem[-8:]
    target=base/'ground'/f'year={ds[:4]}'/f'month={ds[4:6]}'
    target.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(path);cols=d.columns[3:]
    vals=[]
    for pollutant,field in [('PM2.5','pm25'),('PM10','pm10'),('NO2','no2')]:
        x=d.loc[d.type==pollutant].set_index('hour')[cols].reindex(range(24))
        vals.append(x.where(x>=0).rename_axis(columns='station_id').stack(future_stack=True).rename(field))
    data=pd.concat(vals,axis=1).dropna(how='all').reset_index()
    data['hour_bjt']=pd.to_datetime(ds)+pd.to_timedelta(data.hour,unit='h')
    con.register('observations',data)
    con.execute("COPY (SELECT station_id,hour_bjt, pm25::FLOAT AS pm25, pm10::FLOAT AS pm10, no2::FLOAT AS no2 FROM observations ORDER BY station_id,hour_bjt) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",[str(target/(ds+'.parquet'))])
    con.unregister('observations')
for source,query in [
    ('fire',"""SELECT *,year(local_slot) AS year,month(local_slot) AS month FROM read_csv_auto('data/cleaned/fire_events/*.csv.gz')"""),
    ('era5',"""SELECT location_id,time AS hour_bjt, "temperature_2m (°C)" AS t2m_c, "surface_pressure (hPa)" AS sp_hpa,"wind_speed_10m (m/s)" AS ws_ms, "wind_direction_10m (°)" AS wind_from_deg,"boundary_layer_height (m)" AS blh_m,year(time) AS year,month(time) AS month FROM read_csv('data/raw/era5/yrd41_2023_2025.csv',skip=43,header=true,nullstr=['','NaN','nan','-999'])""")]:
    con.execute(f"COPY ({query}) TO '{base/source}' (FORMAT PARQUET, COMPRESSION ZSTD,PARTITION_BY(year,month),OVERWRITE_OR_IGNORE)")
for name in ('ground_city_hour','yrd_ground_era5_hour','case_city_hour'):
    con.execute(f"COPY (SELECT * FROM read_csv_auto('data/integrated/{name}.csv.gz')) TO 'data/integrated/{name}.parquet' (FORMAT PARQUET,COMPRESSION ZSTD)")
qa={}
for source,col in [('ground','pm25'),('fire','local_slot'),('era5','blh_m')]:
    total,valid=con.execute(f"SELECT COUNT(*),COUNT({col}) FROM read_parquet('data/cleaned/parquet/{source}/*/*/*.parquet')").fetchone()
    qa[source]={'rows':total,'valid_'+col:valid}
q=pd.read_csv('results/ground_daily_qc.csv').query("metric=='pm25'")
assert qa['ground']['valid_pm25']==q.valid_all.sum()
assert qa['fire']['rows']==json.loads(Path('results/fire_summary.json').read_text())['unique']
expected=json.loads(Path('results/fusion_summary.json').read_text())
assert qa['era5']['rows']==expected['era5_cityhours'] and qa['era5']['valid_blh_m']==expected['era5_valid_blh']
Path('results/parquet_qa.json').write_text(json.dumps(qa,indent=2))
print(json.dumps(qa),flush=True)
