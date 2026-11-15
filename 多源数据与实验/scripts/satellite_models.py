"""四源 NO₂ 回归：按有效过境近似时刻匹配城市小时，两种留出检验。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import duckdb
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error,r2_score
ROOT=Path(__file__).resolve().parents[1]
O=ROOT/'results';C=ROOT/'data/cleaned';I=ROOT/'data/integrated'
def main():
    loc=pd.read_csv(C/'case_city_grid.csv').dropna(subset='source_group')
    rows=[]
    for file in sorted((ROOT/'data/raw/s5p').glob('*.npz')):
        with np.load(file) as d:
            day=pd.to_datetime(file.stem)
            for c in loc.itertuples():
                i=np.abs(d['latitude']-c.lat).argmin();j=np.abs(d['longitude']-c.lon).argmin()
                obs=d['observations'][i,j];v=d['column'][i,j];frac=d['fraction_local_day'][i,j]
                gx=float(d['longitude'][j]);gy=float(d['latitude'][i])
                good=bool(obs>0 and np.isfinite(v) and np.isfinite(frac))
                effective=day+pd.Timedelta(hours=float(frac)*24+8-gx/15) if good else pd.NaT
                rows.append(dict(city=c.city,date=day,grid_lon=gx,grid_lat=gy,observations=obs,effective_time=effective,valid=good,column_1e15=float(v)/1e15,cloud_fraction=d['cloud'][i,j],sigma_1e15=float(d['uncertainty'][i,j])/1e15))
    sat=pd.DataFrame(rows);assert len(sat)==41*90
    sat.to_csv(C/'s5p_city_day.csv',index=False)
    sat.groupby('city').agg(dates=('valid','size'),valid_dates=('valid','sum'),valid_fraction=('valid','mean')).to_csv(O/'s5p_city_coverage.csv')
    air=pd.read_csv(I/'yrd_ground_era5_hour.csv.gz',parse_dates=['time'])
    osm=pd.read_csv(C/'osm_city_features.csv')
    raw=sat[sat.valid].copy()
    # 每个 L3 日格代表多个过境像元；使用格有效地方太阳时，并以最近北京时间整点对齐。
    raw['time']=raw.effective_time.dt.round('h')
    raw=raw.merge(osm,on='city',validate='many_to_one')
    feat_sets={'卫星':['column_1e15'],'卫星+气象':['column_1e15','ws_ms','log_blh'],'卫星+气象+OSM':['column_1e15','ws_ms','log_blh','road_km_per_km2','industrial_area_ratio']}
    metrics=[];predictions=[];mainset=None
    for shift in [0,-1,1]:
        s=raw.copy();s['time']+=pd.Timedelta(hours=shift)
        s=s.merge(air[['time','city','no2','no2_n','ws_ms','blh_m']],on=['time','city'],how='left',validate='many_to_one')
        s['log_blh']=np.log1p(s.blh_m.where(s.blh_m>=0))
        s=s.dropna(subset=['no2',*feat_sets['卫星+气象+OSM']]).reset_index(drop=True)
        groups=s.grid_lon.astype(str)+'_'+s.grid_lat.astype(str)
        if shift==0:
            mainset=s.copy()
            s.to_csv(I/'no2_four_sources.csv',index=False)
            con=duckdb.connect();con.register('t',s)
            con.execute('COPY t TO ? (FORMAT PARQUET, COMPRESSION ZSTD)',[str(I/'no2_four_sources.parquet')])
        cv=list(GroupKFold(n_splits=5).split(s,groups=groups))
        time_split=[(np.flatnonzero(s.date<'2023-03-01'),np.flatnonzero(s.date>='2023-03-01'))]
        for label,splits in [('留出卫星格点',cv),('留出3月',time_split)]:
            for name,cols in feat_sets.items():
                all_y=[];all_pred=[]
                for fold,(train,test) in enumerate(splits):
                    model=make_pipeline(StandardScaler(),Ridge(alpha=1.0))
                    model.fit(s.loc[train,cols],s.no2.iloc[train])
                    pred=model.predict(s.loc[test,cols]);all_pred.extend(pred);all_y.extend(s.no2.iloc[test])
                    if shift==0:
                        predictions.extend(dict(city=s.city.iloc[i],date=str(s.date.iloc[i].date()),fold=fold,scheme=label,model=name,y=s.no2.iloc[i],pred=v) for i,v in zip(test,pred))
                metrics.append(dict(shift_h=shift,scheme=label,model=name,n=len(all_y),mae=mean_absolute_error(all_y,all_pred),r2=r2_score(all_y,all_pred)))
    pd.DataFrame(metrics).to_csv(O/'no2_model_metrics.csv',index=False)
    pd.DataFrame(predictions).to_csv(O/'no2_holdout_predictions.csv.gz',index=False)
    s=mainset
    (O/'no2_summary.json').write_text(json.dumps(dict(eligible_citydays=len(sat),valid_satellite=int(sat.valid.sum()),matched=len(s),days=int(s.date.nunique()),cities=int(s.city.nunique()),grids=len(s[['grid_lon','grid_lat']].drop_duplicates()),source_days=sat.date.nunique(),raw_study_bytes=sum(p.stat().st_size for p in (ROOT/'data/raw/s5p').glob('*.npz')),osm_pbf_bytes=sum(p.stat().st_size for p in (ROOT/'data/raw/osm').glob('*.pbf'))),indent=2))
if __name__=='__main__':main()
