"""复算公报、城市小时、火点同格观测、日历和地图抽查底表。先运行 fires.py。"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW,CLEAN,JOIN,OUT=(ROOT/p for p in ('data/raw','data/cleaned','data/integrated','results'))
def save(frame,path):
    frame.to_csv(path,index=False,float_format='%.6f')
def grid(x):
    return np.floor(x*4+0.5)/4
def bulletins():
    rows=[]
    for path in sorted((RAW/'bulletins').glob('*.json')):
        obj=json.loads(path.read_text())
        for rec in obj['records']:
            keep={k:v for k,v in rec.items() if k!='evidence'}
            rows.append(dict(month=obj['month'],**keep,url=obj['url']))
    frame=pd.DataFrame(rows)
    assert len(frame)==72 and not frame.duplicated(['region','month']).any()
    assert frame[['pm25','good_pct','heavy_pct']].notna().all().all()
    save(frame,OUT/'monthly_bulletins.csv')
    scope=pd.read_csv(RAW/'city_scope.csv')
    scope=scope.assign(city=scope.cities.str.split()).explode('city').drop(columns='cities')
    assert len(scope)==41 and (scope.source_group=='31').sum()==31
    ledger=scope.merge(frame.query("region=='长三角'")[['month','city_count']],how='cross')
    ledger['covered_by_bulletin']=(ledger.city_count==41)|(ledger.source_group=='31')
    save(ledger,CLEAN/'city_month_scope.csv')
    annex=pd.read_csv(RAW/'city_annex_counts.csv')
    annex=annex.assign(city=annex.cities.str.split()).explode('city').drop(columns='cities')
    assert not annex.duplicated(['month','city']).any()
    detailed=ledger[ledger.month.isin(annex.month.unique())].merge(annex,how='left',on=['month','city'],validate='one_to_one')
    detailed.loc[detailed.covered_by_bulletin & detailed.days.isna(),'days']=0
    detailed['source']=detailed.month.map(annex.groupby('month').source.first())
    save(detailed,OUT/'city_annex_two_months.csv')
    assert detailed.groupby('month').days.sum().to_dict()=={'2023-12':56.0,'2024-02':27.0}
    return scope

def calendar():
    days=pd.DataFrame({'date':pd.date_range('2023-01-01','2025-12-31')})
    for flag in ['spring_break','new_year_eve','makeup_workday']:
        days[flag]=False
    for a in pd.read_csv(RAW/'spring_festival_rules.csv').itertuples():
        days.loc[days.date.between(a.start,a.end),'spring_break']=True
        days.loc[days.date==a.eve,'new_year_eve']=True
        days.loc[days.date.isin(pd.to_datetime([a.makeup1,a.makeup2])),'makeup_workday']=True
    assert len(days)==1096 and days.spring_break.sum()==23
    save(days,CLEAN/'spring_calendar.csv')
    return days
def stations():
    st=pd.read_csv(RAW/'station_roster.csv')
    assert st.station_id.nunique()==len(st)==1601
    st['era_lat']=grid(st.latitude);st['era_lon']=grid(st.longitude)
    save(st,CLEAN/'station_grid.csv')
    sample=st.sample(n=200,random_state=20261115).copy()
    sample['manual_review']='待人工地图复核';save(sample,OUT/'station_map_sample_200.csv')

def case(scope,days):
    md5={'20251126.csv':'27567935f91304ef851c1d7497c88aa9','20251127.csv':'3534d3f57a3dfa350a1086054d0a769e','china_obser_stations.csv':'f18af22a35d97c7b4a2a53c312efc208'}
    for name,want in md5.items():
        assert hashlib.md5((RAW/'pm10_case'/name).read_bytes()).hexdigest()==want
    df=pd.concat([pd.read_csv(RAW/'pm10_case'/name) for name in sorted(md5)[:2]],ignore_index=True)
    assert not df.duplicated(['date','hour','type']).any()
    cols=['PM2.5','PM10','AQI','NO2']
    data=df[df.type.isin(cols)].melt(['date','hour','type'],var_name='city',value_name='v')
    data.v=pd.to_numeric(data.v,errors='coerce')
    data['negative']=data.v.lt(0)
    data.loc[data.negative,'v']=np.nan
    qc=data.groupby(['date','type'],as_index=False).agg(cells=('v','size'),valid=('v','count'),negative=('negative','sum'))
    qc['missing_fraction']=1-qc.valid/qc.cells;save(qc,OUT/'case_quality.csv')
    fact=data.pivot(index=['date','hour','city'],columns='type',values='v').reset_index()
    fact['date']=pd.to_datetime(fact.date.astype(str),format='%Y%m%d')
    fact['hour_bjt']=fact.date+pd.to_timedelta(fact.hour,unit='h')
    cities=pd.read_csv(RAW/'pm10_case/china_obser_stations.csv')
    assert cities.city.is_unique
    cities=cities.merge(scope[['city','province','source_group']],on='city',how='left',validate='one_to_one')
    cities['era_lat']=grid(cities.lat);cities['era_lon']=grid(cities.lon)
    save(cities,CLEAN/'case_city_grid.csv')
    fact=fact.merge(cities,on='city',how='left',validate='many_to_one').merge(days,on='date',how='left',validate='many_to_one')
    assert len(fact)==375*48 and not fact.duplicated(['city','hour_bjt']).any()
    event_path=CLEAN/'fire_events/utc_2025.csv.gz'
    chunks=[]
    for chunk in pd.read_csv(event_path,chunksize=200000,parse_dates=['local_slot']):
        segment=chunk[chunk.local_slot.between('2025-11-26','2025-11-27 23:59')].copy()
        if len(segment):
            segment['hour_bjt']=segment.local_slot.dt.floor('h')
            segment['era_lat']=grid((segment.lat_bin+0.5)/100)
            segment['era_lon']=grid((segment.lon_bin+0.5)/100)
            chunks.append(segment)
    pts=pd.concat(chunks)
    grp=pts.groupby(['hour_bjt','era_lat','era_lon'],as_index=False).agg(fire_slots=('detections','size'),fire_detections=('detections','sum'))
    fact=fact.merge(grp,on=['hour_bjt','era_lat','era_lon'],how='left',validate='many_to_one')
    for col in ['fire_slots','fire_detections']:
        fact.loc[fact.era_lat.notna() & fact.era_lon.notna(),col]=fact.loc[fact.era_lat.notna() & fact.era_lon.notna(),col].fillna(0)
    save(fact,JOIN/'case_city_hour.csv.gz')
    nj=fact[fact.city=='南京'].sort_values('hour_bjt')
    save(nj,OUT/'nanjing_hourly.csv')
    summary=fact.melt(id_vars=['date','city'],value_vars=['PM2.5','PM10','NO2'],var_name='pollutant',value_name='concentration').groupby(['date','city','pollutant'],as_index=False).agg(n_valid=('concentration','count'),mean_valid=('concentration','mean'),maximum=('concentration','max'))
    summary['mean_20h']=summary.mean_valid.where(summary.n_valid>=20)
    save(summary,OUT/'case_city_day.csv.gz');save(summary[summary.city=='南京'],OUT/'nanjing_day.csv')
    # 所有候选及滞后全部报出，相关只作 48 小时内部的描述；重复小时和整体趋势会影响相关。
    wide=fact.pivot(index='hour_bjt',columns='city',values='PM10')
    rows=[]
    for city in ['徐州','宿迁','淮安','蚌埠','滁州','扬州']:
        for lag in range(13):
            pair=pd.concat([wide[city].shift(lag).rename('x'),wide['南京'].rename('y')],axis=1).dropna()
            rows.append(dict(city=city,lag_hours=lag,n=len(pair),r=pair.x.corr(pair.y) if len(pair)>=24 else np.nan))
    save(pd.DataFrame(rows),OUT/'case_nanjing_lag_grid.csv')
    stats=dict(city_hours=len(fact),cities=fact.city.nunique(),city_coords=int(fact.drop_duplicates('city').lat.notna().sum()),city_hours_with_local_fire=int((fact.fire_slots>0).sum()),cities_with_local_fire=int(fact.loc[fact.fire_slots>0,'city'].nunique()),annex_months=2,bulletins=36)
    (OUT/'case_summary.json').write_text(json.dumps(stats,indent=2))
if __name__=='__main__':
    case(bulletins(),calendar())
    stations()
