"""Spatially cross-check 200 national roster IDs and 200 fire cells against an independent map."""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import osmium
import shapely
from shapely.geometry import Point,box
from shapely.strtree import STRtree
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'多源数据与实验'
OUT=ROOT/'扩展实验/核验'
def polygon_assignment(boundary, x,y):
    if not np.isfinite(x+y):return '', '', ''
    p=Point(x,y); groups={}
    for i in boundary[1].query(p,predicate='intersects'):
        z=boundary[0].iloc[i];groups.setdefault(z.admin_level,[]).append(z['name'])
    return tuple('|'.join(sorted(set(groups.get(k,[])))) for k in ['4','5','6'])
def normalize(x):
    return re.sub(r'(市|地区)$','',x) if isinstance(x,str) else ''
def main():
    areas=pd.read_parquet(OUT/'行政区面.parquet');bound=(areas,STRtree(shapely.from_wkb(areas.wkb.to_numpy())))
    roster=pd.read_csv(ROOT/'扩展实验/跨期分析/站点匹配明细.csv')
    sample=roster.sort_values('station').sample(n=200,random_state=20261115).copy()
    def assign(df,xcol,ycol):
        df[['图上省','图上地级区','图上县级区']]=[polygon_assignment(bound,x,y) for x,y in zip(df[xcol],df[ycol])]
    assign(sample,'lon','lat')
    sample['网格经度']=np.floor(sample.lon*4+.5)/4;sample['网格纬度']=np.floor(sample.lat*4+.5)/4
    sample['落入最近四分之一度格']=((sample.lon-sample['网格经度']).abs()<=.125)&((sample.lat-sample['网格纬度']).abs()<=.125)
    def match(row):
        if pd.isna(row.lon) or pd.isna(row.city):return '无可核对站点归属'
        if not any([row.图上省,row.图上地级区,row.图上县级区]):return '边界缺失'
        names=[normalize(v) for c in ['图上地级区','图上县级区'] for v in row[c].split('|')]
        if row.图上省 in ['北京市','天津市','上海市','重庆市']:names.append(normalize(row.图上省))
        return '名称一致' if normalize(row.city) in names else '名称需复核'
    sample['判定']=sample.apply(match,axis=1)
    sample.to_csv(OUT/'站点200条空间核验.csv',index=False)
    fire=pd.read_csv(BASE/'results/fire_map_sample_200.csv').drop(columns='manual_review')
    assign(fire,'longitude_center','latitude_center')
    fire['网格经度']=np.floor(fire.longitude_center*4+.5)/4;fire['网格纬度']=np.floor(fire.latitude_center*4+.5)/4
    fire['原0.01度格重算一致']=(np.floor(fire.longitude_center*100)==fire.lon_bin)&(np.floor(fire.latitude_center*100)==fire.lat_bin)
    fire['四角行政归属稳定']=[len({polygon_assignment(bound,x+dx,y+dy)[:2] for dx in [-.00499,.00499] for dy in [-.00499,.00499]})==1 for x,y in zip(fire.longitude_center,fire.latitude_center)]
    fpath=OUT/'农业用地参照.osm.pbf';src=ROOT/'data/raw/osm/china-261114.osm.pbf'
    if not fpath.exists():
        temp=OUT/'农业用地.part.osm.pbf'
        with osmium.BackReferenceWriter(temp,src,overwrite=True) as w:
            for o in osmium.FileProcessor(src,entities=osmium.osm.WAY|osmium.osm.RELATION):
                if o.tags.get('landuse') in ('farmland','orchard','vineyard'):
                    if o.is_way():w.add_way(o)
                    else:w.add_relation(o)
        temp.replace(fpath)
    wz=shapely.points(fire.longitude_center,fire.latitude_center);tree=STRtree(wz);hits={}; land=[]
    factory=osmium.geom.WKBFactory()
    for a in osmium.FileProcessor(fpath).with_areas().with_filter(osmium.filter.EntityFilter(osmium.osm.AREA)):
        tag=a.tags.get('landuse')
        if tag not in ('farmland','orchard','vineyard'):continue
        try:g=shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(a)))
        except (RuntimeError,ValueError):continue
        if not g.is_valid:g=shapely.make_valid(g)
        kind='w' if a.from_way() else 'r'
        if g.bounds[2]>=113 and g.bounds[0]<=125 and g.bounds[3]>=26 and g.bounds[1]<=37:
            land.append([kind,a.orig_id(),tag,bytes(shapely.to_wkb(g))])
        for ix in tree.query(g,predicate='intersects'):hits.setdefault(ix,[]).append(f'{kind}{a.orig_id()}:{tag}')
    fire['农业面图斑']=['|'.join(hits.get(i,[])) for i in range(len(fire))]
    fire['耕地口径']=np.where(fire['农业面图斑'].str.contains(':farmland'),'中心命中已绘制农田','中心未命中已绘制农田')
    fire.to_csv(OUT/'火点200条空间核验.csv',index=False)
    pd.DataFrame(land,columns=['type','id','landuse','wkb']).to_parquet(OUT/'华东农业面.parquet',index=False)
    print('stations',sample.判定.value_counts().to_dict(),'fire prefectures / province / district',*[int(fire[c].ne('').sum()) for c in ['图上地级区','图上省','图上县级区']],'cropland tags',fire.耕地口径.value_counts().to_dict(),'agri east',len(land),flush=True)
if __name__=='__main__':main()
