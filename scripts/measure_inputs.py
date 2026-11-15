from pathlib import Path
import hashlib, csv
import pandas as pd
import duckdb
from ground import ROOT
E=ROOT/'扩展实验';A=E/'跨期分析';B=ROOT/'多源数据与实验';M=E/'多源复算';D=E/'规模核算'
def size(paths):return sum(p.stat().st_size for p in paths)
def main():
    D.mkdir(exist_ok=True)
    checks=pd.read_csv(E/'核验/原始试验与归档校验.csv')
    ledger=[];lookup={'air':'地面','ground':'地面','firms':'火点','era5':'气象','s5p':'卫星','osm':'地图'}
    for r in checks.itertuples(index=False,name=None):
        scope,path,n,h=r
        if not path.startswith('data/raw/'):continue
        p=Path(path);group=lookup.get(p.parts[2])
        if group is None or p.name=='station_cells.osm.pbf' or 'catalog' in p.name:continue
        ledger.append([group,scope,path,n,h])
    l=pd.DataFrame(ledger,columns=['来源','阶段','路径','字节','sha256']);l['重复字节内容']=l.duplicated(['sha256'])
    l.to_csv(D/'原始文件按内容去重.csv',index=False)
    raw=l[~l.重复字节内容].groupby('来源').字节.sum()
    con=duckdb.connect()
    stations=A/'有效站点观测';ids=con.execute("SELECT count(DISTINCT station),count(*),count(\"PM2.5\"),count(\"NO2\") FROM read_parquet(?)",[str(stations/'*.parquet')]).fetchone()
    (D/'有效站点行数.txt').write_text(f'至少一个分析指标有值的不同站号={ids[0]}，站点小时行={ids[1]}，PM2.5非空={ids[2]}，NO2非空={ids[3]}\n')
    fact=pd.read_parquet(M/'data/integrated/yrd_ground_era5_hour.parquet')
    metpath=D/'模型对应城市气象.parquet'
    fact[['city','time','t2m_c','sp_hpa','ws_ms','wind_from_deg','blh_m']].to_parquet(metpath,index=False)
    sat=pd.read_csv(M/'data/cleaned/s5p_city_day.csv').drop_duplicates(['date','grid_lon','grid_lat'])
    sat=sat[sat.valid].drop(columns=['city','valid']);sp=D/'有效卫星观测格.parquet';sat.to_parquet(sp,index=False)
    l2=pd.read_parquet(ROOT/'data/cleaned/satellite_city_orbit.parquet').dropna(subset='no2_mol_m2')
    sp2=D/'十月有效L2城市轨道.parquet';l2.to_parquet(sp2,index=False)
    paths=[('地面',list(stations.glob('*.parquet')),'已匹配站号且PM₂.₅或NO₂有观测的站点小时，两列浓度各保留一次'),('火点',list((B/'data/cleaned/fire_events').glob('*.gz')),'用于全国季节分布的七年去重火点时空格，排除原始年表和重复派生表'),('气象',[metpath],'与长三角实测地面小时匹配的五个气象量'),('卫星',[sp,sp2],'长三角有效L3格日按同格去重，加不同日期的十月有效L2城市轨道'),('地图',[ROOT/'data/raw/osm/station_cells.osm.pbf'],'十月道路和工业地块的引用完整子集；其余快照、农业核验和行政区文件不累加')]
    rows=[[k,raw[k],size(pp),note] for k,pp,note in paths]
    pd.DataFrame(rows,columns=['来源','实际原始文件字节_同摘要去重','保守研究子集落盘字节','研究子集口径']).to_csv(D/'五源实际体量.csv',index=False)
    months=pd.period_range('2023-01','2025-12',freq='M');q=pd.read_csv(A/'逐日补采队列.csv',parse_dates=['date']);q['month']=q.date.dt.to_period('M')
    cov=q.groupby('month').ground.agg(['sum','size']).reindex(months);cov.columns=['地面日数','月份日数']
    l3=pd.read_csv(B/'logs/satellite_daily_windows.csv',dtype={'day':str});cov['L3研究窗口日数']=l3.day.str[:6].apply(lambda s:pd.Period(s[:4]+'-'+s[4:6])).value_counts().reindex(months,fill_value=0)
    cov['L2柱及QA轨道数']=0
    for p in (ROOT/'data/raw/s5p').rglob('*_PRODUCT_qa_value_4326.tif'):
        prefix=p.name.split('_PRODUCT_')[0];day=prefix.split('____')[1][:8]
        if p.with_name(prefix+'_PRODUCT_nitrogendioxide_tropospheric_column_4326.tif').exists():cov.loc[pd.Period(day[:4]+'-'+day[4:6]),'L2柱及QA轨道数']+=1
    ec=pd.read_csv(M/'results/era5_coverage.csv');ec['month']=pd.PeriodIndex(ec.month,freq='M');cov['ERA5四要素有效城市小时']=ec.groupby('month')[['t2m_c','sp_hpa','ws_ms','wind_from_deg']].sum().min(axis=1);cov['ERA5边界层有效城市小时']=ec.groupby('month').blh_m.sum()
    cov['三传感器年度文件数']=3;cov.to_csv(D/'来源逐月覆盖.csv',index_label='月份')
    print(pd.read_csv(D/'五源实际体量.csv').to_string(index=False),flush=True)
if __name__=='__main__':main()
