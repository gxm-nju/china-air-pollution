from pathlib import Path
import sys
import argparse
import os
NEW=Path(__file__).resolve().parents[1]
ROOT=NEW.parent/"网格与过境复算"
sys.path.insert(0,str(ROOT/"程序"))
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.metrics import mean_absolute_error,r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge
project=Path(os.environ.get('POLLUTION_PROJECT_ROOT', ROOT.parents[1]))
out=NEW/'结果'
def city_points():
    return pd.read_csv(project/'多源数据与实验/data/cleaned/case_city_grid.csv').dropna(subset='source_group').sort_values('city')
def xyz(lat,lon):
    lat,lon=np.radians(lat),np.radians(lon)
    return np.column_stack([np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)])
def pixels(manifest):
    cities=city_points()
    rows=[];stats=[]
    ledger=pd.read_csv(manifest)
    assert not ledger.orbit.duplicated().any() and not ledger.sha256.duplicated().any()
    for rec in ledger.itertuples():
        directory=ROOT if rec.month.endswith('-01') else NEW
        p=directory/'原始数据/S5P'/(rec.orbit+'.npz')
        with np.load(p) as d:
            good=(d['qa']>.75)&(d['qa']<=1)&np.isfinite(d['no2'])
            if not good.any():
                stats.append((p.stem,len(good),0,0,0,np.nan));continue
            lat=d['lat'][good];lon=d['lon'][good]; col=d['no2'][good].astype(float)*6.02214076e23/1e19
            time=d['time_ms'][good]
            tree=cKDTree(xyz(lat,lon))
            nearby=tree.query_ball_point(xyz(cities.lat,cities.lon),2*np.sin(15/(2*6371)))
            joined=set()
            for city,ix in zip(cities.city,nearby):
                if not ix:continue
                joined.update(ix)
                t=pd.to_datetime(np.median(time[ix]),unit='ms')+pd.Timedelta(hours=8)
                rows.append(dict(city=city,date=t.normalize(),overpass=t,time=t.round('h'),n_pixels=len(ix),l2=col[ix].mean(),orbit=p.stem))
            stats.append((p.stem,len(good),len(col),len(joined),sum(bool(v) for v in nearby),col.mean()))
    s=pd.DataFrame(stats,columns=['orbit','region_pixels','quality_pixels','city_quality_pixels','city_matches','mean_valid_column_1e15'])
    s.to_csv(out/'逐轨筛选.csv',index=False)
    return pd.DataFrame(rows)
def paired_ci(test,err):
    blocks=pd.DataFrame({'date':test.date,'err':np.asarray(err)}).groupby('date').err.agg(['sum','count']).to_numpy()
    draws=blocks[np.random.default_rng(20261116).integers(len(blocks),size=(3000,len(blocks)))].sum(axis=1)
    return np.quantile(draws[:,0]/draws[:,1],[.025,.975])
def reg(train,test,columns):
    model=make_pipeline(StandardScaler(),Ridge(alpha=1.))
    return model.fit(train[columns],train.no2).predict(test[columns])
def met_at_pass(frame):
    from scipy.interpolate import RegularGridInterpolator
    from scipy.io import netcdf_file
    from era import spec
    coords=city_points().set_index('city')
    obs=frame.overpass-pd.Timedelta(hours=8)
    result=frame.copy()
    for month,group in frame.groupby(obs.dt.to_period('M')):
        xyzcity=coords.loc[group.city,['lat','lon']].to_numpy()
        components={}
        for k,(_,var,_) in spec.items():
            path=ROOT/'原始数据/ERA5'/f'{month}_{k}.nc'
            with netcdf_file(path,mmap=False) as f:
                hours=f.variables['time'].data.astype(float)
                points=(hours,f.variables['latitude'].data,f.variables['longitude'].data)
                arr=f.variables[var].data
                when=(obs.loc[group.index]-pd.Timestamp('1900-01-01'))/pd.Timedelta(hours=1)
                components[k]=RegularGridInterpolator(points,arr,bounds_error=False,fill_value=np.nan)(np.column_stack([when,xyzcity]))
        result.loc[group.index,'grid_ws']=np.hypot(components['u10'],components['v10'])
        result.loc[group.index,'grid_log_blh']=np.log1p(components['blh'])
    return result
def build_matches(manifest):
    obs=pixels(manifest)
    assert not obs.duplicated(['orbit','city']).any()
    # Choose the best regional overpass without consulting pollution labels.
    best=obs.sort_values(['n_pixels','orbit'],ascending=[False,True]).drop_duplicates(['city','date'])
    ground=pd.read_parquet(project/'扩展实验/三年地面补采/多源复算/更新计算/data/integrated/yrd_ground_era5_hour.parquet')
    f=best.merge(ground[['city','time','no2','ws_ms','blh_m','no2_n']],on=['city','time'],how='left',validate='many_to_one')
    f['log_blh']=np.log1p(f.blh_m.where(f.blh_m>=0))
    f=met_at_pass(f)
    f.to_csv(out/'卫星城市日匹配.csv.gz',index=False)
    return f

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=NEW/'记录/最终逐轨核验.csv')
    parser.add_argument('--matched', type=Path, help='Refit published models from the released city-day matches')
    parser.add_argument('--output', type=Path, help='Output directory for the model results')
    args=parser.parse_args()
    global out
    if args.output:
        out=args.output
    out.mkdir(exist_ok=True,parents=True)
    if args.matched:
        f=pd.read_csv(args.matched)
        for k in ('date','time','overpass'):
            f[k]=pd.to_datetime(f[k],format='mixed')
    else:
        f=build_matches(args.manifest)
    assert not f.duplicated(['city','date']).any()
    z=f.dropna(subset=['l2','no2','grid_ws','grid_log_blh']).copy()
    z['year']=z.date.dt.year
    preds=[];metrics=[]
    def evaluate(train,test,run,cols0,cols1,label0,label1):
        if len(train)<10 or len(test)<10:return
        pr0,pr1=[reg(train,test,x) for x in (cols0,cols1)]
        error=np.abs(pr1-test.no2)-np.abs(pr0-test.no2)
        lo,hi=paired_ci(test,error)
        metrics.append(dict(run=run,base=label0,extra=label1,n_train=len(train),n_test=len(test),test_days=test.date.nunique(),test_cities=test.city.nunique(),
                            mae0=mean_absolute_error(test.no2,pr0),mae1=mean_absolute_error(test.no2,pr1),delta=error.mean(),ci_low=lo,ci_high=hi,
                            r2_base=r2_score(test.no2,pr0),r2_extra=r2_score(test.no2,pr1)))
        rec=test[['city','date','time','no2','l2']].copy()
        rec['run']=run;rec['pred0']=pr0;rec['pred1']=pr1;preds.append(rec)
    train=z[z.year.eq(2023)]
    for yr in (2024,2025):
        test=z[z.year.eq(yr)]
        grid_fields=['l2','grid_ws','grid_log_blh']
        evaluate(train,test,str(yr)+'年跨季节外推',['l2'],grid_fields,'仅L2','L2加网格气象')
        for month, monthly in test.groupby(test.date.dt.month):
            evaluate(train,monthly,f'{yr}-{month:02d}月外推',['l2'],grid_fields,'仅L2','L2加网格气象')
    stats=z.groupby('year').agg(city_days=('no2','size'),dates=('date','nunique'),cities=('city','nunique'),local_min=('overpass','min'),local_max=('overpass','max'))
    stats.to_csv(out/'逐年有效样本.csv')
    pd.DataFrame(metrics).to_csv(out/'NO2验证.csv',index=False)
    if preds:pd.concat(preds).to_csv(out/'NO2验证预测.csv.gz',index=False)
    season_names={12:'冬',1:'冬',2:'冬',3:'春',4:'春',5:'春',6:'夏',7:'夏',8:'夏',9:'秋',10:'秋',11:'秋'}
    records=[]
    paired=[]
    for training,train_set in [('全年',train),('仅一月',train[train.date.dt.month.eq(1)])]:
        for year in (2024,2025):
            test=z[z.year.eq(year)].copy()
            if test.empty:continue
            test['season']=test.date.dt.month.map(season_names)
            test['base']=reg(train_set,test,['l2'])
            test['with_met']=reg(train_set,test,['l2','grid_ws','grid_log_blh'])
            test['train_period']=training
            paired.append(test[['train_period','year','season','city','date','time','no2','base','with_met']])
            for season,g in test.groupby('season',sort=False):
                base=(g.base-g.no2).abs()
                extra=(g.with_met-g.no2).abs()
                delta=extra-base
                lo,hi=paired_ci(g,delta)
                # Resample whole calendar weeks as a serial-dependence sensitivity analysis.
                weeks=g.assign(date=g.date.dt.to_period('W-SUN').dt.start_time)
                wl,wh=paired_ci(weeks,delta)
                records.append(dict(train_period=training,year=year,season=season,training_n=len(train_set),
                                    n=len(g),days=g.date.nunique(),cities=g.city.nunique(),
                                    months=','.join(str(x) for x in sorted(g.date.dt.month.unique())),
                                    mae0=base.mean(),mae1=extra.mean(),delta=delta.mean(),
                                    day_low=lo,day_high=hi,week_low=wl,week_high=wh))
    pd.DataFrame(records).to_csv(out/'跨季节误差.csv',index=False)
    pd.concat(paired).to_csv(out/'季节配对预测.csv.gz',index=False)
    print(stats.to_string(),flush=True);print(pd.DataFrame(metrics).round(3).to_string(index=False),flush=True)

if __name__=='__main__':main()
