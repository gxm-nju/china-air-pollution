"""Measure intersected road centre-lines and industrial polygon union in station cells."""
from collections import defaultdict
import math
import osmium
import pandas as pd
from shapely import from_wkb, STRtree, box, union_all, make_valid
from shapely.affinity import scale
from ground import RAW,CL,OUT,sites,YRD
MOTOR=set('motorway trunk primary secondary tertiary unclassified residential living_street service motorway_link trunk_link primary_link secondary_link tertiary_link'.split())

def run():
    p=RAW/'osm/china-261114.osm.pbf'
    s=sites();g=s[s.city.isin(YRD)][['gx','gy']].drop_duplicates().sort_values(['gy','gx']).reset_index(drop=True)
    cells=[box(x-.125,y-.125,x+.125,y+.125) for x,y in g.to_numpy()]
    tree=STRtree(cells);km=defaultdict(float);industrial=defaultdict(list);records=[];bad=0
    geom=osmium.geom.WKBFactory()
    proc=osmium.FileProcessor(p).with_locations('flex_mem').with_areas(osmium.filter.TagFilter(('landuse','industrial'))).with_filter(osmium.filter.KeyFilter('highway','landuse'))
    d=CL/'osm';d.mkdir(exist_ok=True);extract=d/'used_objects.parquet'
    for o in proc:
        road=o.is_way() and o.tags.get('highway') in MOTOR and o.tags.get('area')!='yes'
        land=o.is_area() and o.tags.get('landuse')=='industrial'
        if not (road or land): continue
        try:
            wkb=geom.create_linestring(o) if road else geom.create_multipolygon(o)
            shape=from_wkb(bytes.fromhex(wkb))
            if land and not shape.is_valid:shape=make_valid(shape)
            matches=tree.query(shape,predicate='intersects')
            if len(matches)==0:continue
            typ='w' if road or o.from_way() else 'r'
            ident=o.id if road else o.orig_id()
            for idx in matches:
                part=shape.intersection(cells[idx])
                x,y=g.iloc[idx]
                if road:
                    length=scale(part,xfact=111.32*math.cos(math.radians(y)),yfact=110.57,origin=(x,y)).length
                    if length<=0:continue
                    km[idx]+=length
                else:
                    if part.area<=0:continue
                    industrial[idx].append(part)
                records.append((typ,ident,int(idx),'road' if road else 'industrial',o.tags.get('highway') if road else 'industrial',part.wkb))
        except (RuntimeError,ValueError) as e:
            bad+=1
    for i,(x,y) in enumerate(g[['gx','gy']].to_numpy()):
        cell_area=.25*.25*111.32*math.cos(math.radians(y))*110.57
        g.loc[i,'road_km']=km[i];g.loc[i,'cell_km2']=cell_area;g.loc[i,'road_km_per_km2']=km[i]/cell_area
        g.loc[i,'industrial_fraction']=union_all(industrial[i]).area/cells[i].area if industrial[i] else 0.
    pd.DataFrame(records,columns=['object_type','osm_id','cell_index','layer','tag','clipped_wkb_wgs84']).to_parquet(extract,index=False)
    g.to_csv(d/'grid.csv',index_label='cell_index')
    dim=s[s.city.isin(YRD)].drop_duplicates(['city','gx','gy']).merge(g,on=['gx','gy'],validate='many_to_one')
    dim.groupby('city')[['road_km_per_km2','industrial_fraction']].mean().reset_index().to_csv(d/'city.csv',index=False)
    print('OSM',p.name,'station cells',len(g),'geometric intersections',len(records),'unreadable geometries in country',bad,flush=True)
if __name__=='__main__':run()
