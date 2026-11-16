from catalog import ROOT
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.metrics import mean_absolute_error,r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge
project=ROOT.parents[1]
out=ROOT/'结果';out.mkdir(exist_ok=True)
cities=pd.read_csv(project/'多源数据与实验/data/cleaned/case_city_grid.csv').dropna(subset='source_group').sort_values('city')
def xyz(lat,lon):
    lat,lon=np.radians(lat),np.radians(lon)
    return np.column_stack([np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)])
def pixels():
    rows=[];stats=[]
    for p in sorted((ROOT/'原始数据/S5P').glob('*.npz')):
        if '.part' in p.name: continue
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
    coords=cities.set_index('city')
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
def main():
    obs=pixels()
    assert not obs.duplicated(['orbit','city']).any()
    # Choose the best regional overpass without consulting pollution labels.
    best=obs.sort_values(['n_pixels','orbit'],ascending=[False,True]).drop_duplicates(['city','date'])
    ground=pd.read_parquet(project/'扩展实验/三年地面补采/多源复算/更新计算/data/integrated/yrd_ground_era5_hour.parquet')
    f=best.merge(ground[['city','time','no2','ws_ms','blh_m','no2_n']],on=['city','time'],how='left',validate='many_to_one')
    f['log_blh']=np.log1p(f.blh_m.where(f.blh_m>=0))
    f=met_at_pass(f)
    f.to_csv(out/'卫星城市日匹配.csv.gz',index=False)
    z=f.dropna(subset=['l2','no2','log_blh','ws_ms','grid_ws','grid_log_blh']).copy()
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
    met=['ws_ms','log_blh']
    train=z[z.year.eq(2023)]
    for yr in (2024,2025):
        test=z[z.year.eq(yr)]
        grid_fields=['l2','grid_ws','grid_log_blh']
        evaluate(train,test,str(yr)+'年1月外推',['l2'],grid_fields,'仅L2','L2加网格气象')
        evaluate(train,test,str(yr)+'年1月气象表对照',['l2',*met],grid_fields,'L2加旧城市气象','L2加网格气象')
    legacy=pd.read_parquet(project/'扩展实验/三年地面补采/卫星扩月/滚动留出/模型实际使用的城市小时.parquet')
    j=train.merge(legacy[['city','date','column_1e15','time']].rename(columns={'time':'l3_time'}),on=['city','date'],validate='one_to_one')
    same=j[j.time.eq(j.l3_time)]
    evaluate(same[same.date.dt.day<=20],same[same.date.dt.day>20],'2023年1月同城同小时共同样本',['column_1e15',*met],['l2',*met],'L3加气象','L2加气象')
    stats=z.groupby('year').agg(city_days=('no2','size'),dates=('date','nunique'),cities=('city','nunique'),local_min=('overpass','min'),local_max=('overpass','max'))
    stats.to_csv(out/'逐年有效样本.csv')
    pd.DataFrame(metrics).to_csv(out/'NO2验证.csv',index=False)
    if preds:pd.concat(preds).to_csv(out/'NO2验证预测.csv.gz',index=False)
    print(stats.to_string(),flush=True);print(pd.DataFrame(metrics).round(3).to_string(index=False),flush=True)
    print('overlap rows, exact hour',len(j),len(same))
if __name__=='__main__':main()
