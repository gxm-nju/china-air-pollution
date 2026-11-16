"""Check sample attrition, seasonal scores, and the historical winter result."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
out = root/'结果'
def main():
    inputs = pd.read_csv(root/'记录/最终逐轨核验.csv')
    coverage = pd.read_csv(root/'记录/最终逐月覆盖.csv')
    screened = pd.read_csv(out/'逐轨筛选.csv')
    hits = inputs.merge(screened, on='orbit', how='outer', validate='one_to_one', indicator=True)
    assert hits['_merge'].eq('both').all()
    for field in ('region_pixels', 'quality_pixels'):
        assert hits[field+'_x'].eq(hits[field+'_y']).all()
    assert len(coverage) == 36 and not inputs.sha256.duplicated().any()
    frame = pd.read_csv(out/'卫星城市日匹配.csv.gz',parse_dates=['date'])
    assert not frame.duplicated(['city','date']).any()
    good = frame.dropna(subset=['l2','no2','grid_ws','grid_log_blh'])
    flags = hits.assign(selected=hits.orbit.isin(frame.orbit), used=hits.orbit.isin(good.orbit))
    months = flags.groupby('month').agg(orbits_with_city=('city_matches',lambda g:int((g>0).sum())),
        city_quality_pixels=('city_quality_pixels','sum'), best_orbits=('selected','sum'), model_orbits=('used','sum'))
    for group,key in ((frame,'satellite_city_days'),(good,'model_city_days')):
        monthkey=group.date.dt.to_period('M').astype(str)
        months[key]=group.groupby(monthkey).size()
        months[key+'_dates']=group.groupby(monthkey).date.nunique()
    cov=coverage.merge(months.fillna(0),on='month',how='left')
    cov.to_csv(out/'逐月有效样本.csv',index=False)
    preds = pd.read_csv(out/'季节配对预测.csv.gz', parse_dates=['date'])
    seasons = pd.read_csv(out/'跨季节误差.csv')
    assert len(seasons)==16
    assert not preds.duplicated(['train_period','city','date']).any()
    assert (preds.year==preds.date.dt.year).all()
    for row in seasons.itertuples():
        subset=preds.loc[(preds.train_period==row.train_period)&(preds.year==row.year)&(preds.season==row.season)]
        obs=good.loc[(good.date.dt.year==row.year)&good.date.dt.month.isin(list(map(int, row.months.split(','))))]
        assert len(subset)==len(obs)==row.n and subset.date.nunique()==row.days and subset.city.nunique()==row.cities
        assert set(zip(subset.city,subset.date))==set(zip(obs.city,obs.date))
        for column,target in [('base',row.mae0),('with_met',row.mae1)]:
            assert np.isclose((subset[column]-subset.no2).abs().mean(),target,rtol=0,atol=1e-9)
        assert abs(row.mae1-row.mae0-row.delta)<1e-9
    # Same models and samples in the historical one-January experiment.
    old = pd.read_csv(root.parent/'网格与过境复算/结果/NO2验证.csv')
    ref = old[old['base'].eq('仅L2')] if 'base' in old else pd.DataFrame()
    assert len(ref)==2
    for year in (2024,2025):
        r=ref[ref.run.str.contains(str(year))].iloc[0]
        test=preds[(preds.train_period=='仅一月') & (preds.year==year) & (preds.date.dt.month==1)]
        assert len(test)==r.n_test
        for field,v in [('base',r.mae0),('with_met',r.mae1)]:
            assert np.isclose((test[field]-test.no2).abs().mean(),v,rtol=0,atol=1e-6)
    result=dict(months=len(coverage),catalog_orbits=int(coverage.expected.sum()),valid_orbits=int(coverage.verified.sum()),nonempty_orbits=len(inputs),empty_orbits=int(coverage['empty'].sum()),
                bytes=int(inputs.bytes.sum()),region_pixels=int(inputs.region_pixels.sum()),
                quality_pixels=int(inputs.quality_pixels.sum()),city_quality_pixels=int(screened.city_quality_pixels.sum()),
                satellite_city_days=len(frame),matched_city_days=len(good),dates_used=int(good.date.nunique()),
                selected_orbits=int(flags.selected.sum()),model_orbits=int(flags.used.sum()),
                model_orbit_file_bytes=int(flags.loc[flags.used,'bytes'].sum()),
                seasonal_comparisons=len(seasons),historical_january_tests_reproduced=2)
    (root/'记录/结果核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result,flush=True)
if __name__=='__main__':
    main()
