"""Rebuild matched hourly samples from verified daily CSVs or rerun episode summaries offline."""
from pathlib import Path
import argparse
import hashlib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BASE = REPO / "三年地面扩展"
GASES = ["PM2.5","PM10","CO","NO2","SO2","O3"]
PM, PM10, CO, NO2, SO2, O3 = GASES
SCENARIOS = {"宽松": (.45,.40,.35,.60), "主规则": (.50,.50,.50,.65), "严格": (.60,.60,.75,.70)}


def write(df, out, name):
    df.to_csv(out/name,index=False, float_format="%.10g",compression={"method":"gzip","mtime":0} if name.endswith(".gz") else None)


def source_hours(project, episodes, out):
    manifest = pd.read_csv(BASE/"分析输入逐日清单.csv",parse_dates=["date"]).set_index("date")
    mapping = pd.read_csv(REPO/"data/cleaned/station_city.csv").set_index("station").city.dropna()
    targets = {}
    for ep in episodes.itertuples():
        for day in pd.date_range(ep.start-pd.Timedelta(days=3),ep.end):
            targets.setdefault(day,set()).add(ep.city)
    hours, files = [], []
    day_hours = np.arange(24)
    for day, cities in sorted(targets.items()):
        if day not in manifest.index:
            files.append(dict(date=day.date(),status="清单范围之外"))
            continue
        rec = manifest.loc[day]
        path=project/rec.path
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=rec.sha256 or path.stat().st_size!=rec.bytes:
            raise ValueError(f"清单核验失败 {path}")
        needed=mapping[mapping.isin(cities)]
        allowed=set(needed.index)|{"date","type","hour"}
        data=pd.read_csv(path,usecols=lambda x:x in allowed)
        if data.duplicated(["hour","type"]).any() or not data.date.eq(int(day.strftime("%Y%m%d"))).all():
            raise ValueError(f"键或日期不符 {path}")
        files.append(dict(date=day.date(),status="使用",path=rec.path,sha256=digest,bytes=rec.bytes))
        data=data.set_index(["type","hour"])
        for city, selected in needed.groupby(needed):
            stations=selected.index.intersection(data.columns)
            vals=[data.reindex(pd.MultiIndex.from_product([[p],day_hours]))[stations].to_numpy(dtype=float) for p in GASES]
            for v in vals:v[(v<0)|~np.isfinite(v)]=np.nan
            p,m,c,n,s,o=vals
            particles=np.isfinite(p)&np.isfinite(m)
            paired=particles&(m>=p)&(m>0)&np.isfinite(c)
            gases=np.isfinite(n)&np.isfinite(s)
            frame=pd.DataFrame({"city":city,"time":day+pd.to_timedelta(day_hours,unit="h"),"n_pm25":np.isfinite(p).sum(axis=1),"n_pm_pair":particles.sum(axis=1),"n_inverted":(particles&(m<p)).sum(axis=1),"n_joint":paired.sum(axis=1),"n_gas_pair":gases.sum(axis=1),"n_o3":np.isfinite(o).sum(axis=1)})
            for name,v,mask in [(PM,p,paired),(PM10,m,paired),(CO,c,paired),(NO2,n,gases),(SO2,s,gases),(O3,o,np.isfinite(o)),("pm25_all",p,np.isfinite(p)),("coarse_all_pairs",m-p,particles)]:
                denom=mask.sum(axis=1)
                frame[name]=np.divide(np.nansum(np.where(mask,v,np.nan),axis=1),denom,out=np.full(24,np.nan),where=denom>0)
            hours.append(frame)
    write(pd.DataFrame(files),out,"涉及日档.csv")
    return pd.concat(hours,ignore_index=True).sort_values(["city","time"])


def clock_pairs(event, pre, cols):
    # At least two preceding days with observations at the same clock hour.
    base = pre.dropna(subset=cols)
    g=base.groupby(base.index.hour)
    ref=g[cols].mean().loc[g.size().ge(2)]
    obs=event.dropna(subset=cols)
    obs=obs[obs.index.hour.isin(ref.index)]
    comparable=ref.reindex(obs.index.hour).set_axis(obs.index)
    return obs,comparable


def evaluate(row, hours):
    start,end=row.start,row.end+pd.Timedelta(days=1)
    city=hours.loc[row.city]
    ev=city[(city.index>=start)&(city.index<end)]
    pre=city[(city.index>=start-pd.Timedelta(days=3))&(city.index<start)]
    e,b=clock_pairs(ev,pre,[PM,PM10,CO])
    n_by_date=e.groupby(e.index.normalize()).size().reindex(pd.date_range(start,row.end),fill_value=0)
    base=pre.dropna(subset=[PM,PM10,CO])
    iq=base[CO].quantile(.75)-base[CO].quantile(.25)
    rho=e[PM].round(8).corr(e[CO].round(8),method='spearman') if len(e)>1 and min(e[PM].nunique(),e[CO].nunique())>1 else np.nan
    stats=dict(n_event_hours=len(ev.dropna(subset=[PM,PM10,CO])),n_reference_hours=len(base),n_paired_hours=len(e),min_paired_hours_daily=n_by_date.min(),
               usable=(n_by_date.min()>=20 and len(base)>=48 and pd.notna(rho)),rho_pm25_co=rho,baseline_co_iqr=iq)
    # Period-only descriptors remain visible even when the study starts too late for a baseline.
    observed=ev.dropna(subset=[PM,PM10,CO])
    stats["observed_fine_fraction"]=observed[PM].mean()/observed[PM10].mean() if observed[PM10].mean()>0 else np.nan
    stats["observed_rho_pm25_co"]=observed[PM].round(8).corr(observed[CO].round(8),method="spearman") if min(observed[PM].nunique(),observed[CO].nunique())>1 else np.nan
    stats["observed_no2_so2"]=ev[NO2].mean()/ev[SO2].mean() if ev[SO2].mean()>0 else np.nan
    for v,tag in [(PM,"pm25"),(PM10,"pm10"),(CO,"co")]:
        stats[tag+"_event"]=e[v].mean();stats[tag+"_base"]=b[v].mean()
        stats["delta_"+tag]=stats[tag+"_event"]-stats[tag+"_base"]
    stats['fine_fraction']=e[PM].mean()/e[PM10].mean() if e[PM10].mean()>0 else np.nan
    stats['delta_coarse']=stats['delta_pm10']-stats['delta_pm25']
    for cols,tag in [([NO2,SO2],"gas"),([O3],"ozone")]:
        eg,bg=clock_pairs(ev,pre,cols)
        stats[f'n_{tag}_hours']=len(eg)
        if tag=="gas":
            for v in cols:
                stats[v+'_event']=eg[v].mean(); stats[v+'_base']=bg[v].mean()
            stats['no2_so2_event']=eg[NO2].mean()/eg[SO2].mean() if eg[SO2].mean()>0 else np.nan
            stats['no2_so2_base']=bg[NO2].mean()/bg[SO2].mean() if bg[SO2].mean()>0 else np.nan
        else:stats['o3_event']=eg[O3].mean();stats['o3_base']=bg[O3].mean()
    stats['n_unpaired_event_hours']=len(ev)-len(e)
    return stats


def labels(data, scenario):
    # Evidence flags, not source classes. "Fine only" is mutually exclusive with "co-rise".
    coarse,rho,k,fine=SCENARIOS[scenario]
    usable=data.usable
    dust=usable & ((1-data.fine_fraction)>=coarse) & (data.delta_coarse>0)
    rise=usable & (data.delta_pm25>0) & (data.delta_co>k*data.baseline_co_iqr) & (data.rho_pm25_co>=rho)
    fineflag=usable & (data.fine_fraction>=fine) & (data.delta_pm25>0) & (data.delta_co<=k*data.baseline_co_iqr)
    labels=np.select([~usable, dust&rise,dust,rise,fineflag],['资料不足','混合：粗颗粒与CO同升','粗颗粒占优并增强','PM₂.₅与CO同升','细颗粒占优且CO未明显升高'],default='其余或信号不一致')
    return labels,dust,rise,fineflag


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,help='有原始地面日档时指定工程目录，用以重建城市小时表')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output;out.mkdir(parents=True,exist_ok=True)
    ep=pd.read_csv(BASE/'episode_cluster.csv',parse_dates=['start','end'])
    if ep.duplicated(['city','start']).any():raise ValueError("过程键重复")
    if args.project:
        hourly=source_hours(args.project,ep,out)
        write(hourly,out,'过程窗城市小时.csv.gz')
    hourly=pd.read_csv((out if args.project else HERE)/'过程窗城市小时.csv.gz',parse_dates=['time']).set_index(['city','time']).sort_index()
    stats=pd.concat([ep,pd.DataFrame([evaluate(row,hourly) for row in ep.itertuples()])],axis=1)
    for scenario in SCENARIOS:
        l,dust,rise,fine=labels(stats,scenario);stats[scenario]=l
        if scenario=='主规则':
            stats['coarse_signature']=dust;stats['co_signature']=rise;stats['fine_signature']=fine
    write(stats,out,'逐城市过程.csv')
    cats=["粗颗粒占优并增强","PM₂.₅与CO同升","细颗粒占优且CO未明显升高","混合：粗颗粒与CO同升","其余或信号不一致","资料不足"]
    counts=pd.DataFrame({k:stats[k].value_counts().reindex(cats,fill_value=0) for k in SCENARIOS}).rename_axis("特征").reset_index()
    write(counts,out,'规则敏感性.csv')
    for name,key in [('按月分布','month'),('按城分布','city')]:
        panel=pd.crosstab(stats.assign(month=stats.start.dt.month)[key],stats['主规则']).reset_index()
        write(panel,out,name+'.csv')
    print(counts.to_string(index=False))
    print("seg",len(stats),"eligible",stats.usable.sum(),"cities",stats.city.nunique())
    print(stats[stats.start.eq("2023-03-23")][['city','fine_fraction','delta_coarse','delta_co','rho_pm25_co','主规则']].to_string(index=False))
    print('unchanged',sum(stats.宽松.eq(stats.主规则)&stats.严格.eq(stats.主规则)))

if __name__=='__main__': main()
