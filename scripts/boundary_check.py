"""Extract a reference-complete set of province/prefecture OSM boundaries for point checks."""
import json
from pathlib import Path
import osmium
from shapely import from_wkb, to_wkb, make_valid
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'扩展实验/核验'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'data/raw/osm/china-261114.osm.pbf'
    subset=OUT/'行政区边界.osm.pbf'
    if not subset.exists():
        tmp=OUT/'行政区边界.part.osm.pbf'
        with osmium.BackReferenceWriter(tmp,source,overwrite=True,relation_depth=1) as w:
            for obj in osmium.FileProcessor(source,entities=osmium.osm.RELATION):
                if obj.tags.get('boundary')=='administrative' and obj.tags.get('admin_level') in ('4','5','6'):
                    w.add_relation(obj)
        tmp.replace(subset)
    factory=osmium.geom.WKBFactory()
    geoms=[]; bad=[]
    for a in osmium.FileProcessor(subset).with_areas().with_filter(osmium.filter.EntityFilter(osmium.osm.AREA)):
        level=a.tags.get('admin_level');name=a.tags.get('name:zh-Hans') or a.tags.get('name:zh') or a.tags.get('name')
        if a.from_way() or level not in ('4','5','6') or not name:continue
        try:
            poly=from_wkb(bytes.fromhex(factory.create_multipolygon(a)))
            if not poly.is_valid:poly=make_valid(poly)
            geoms.append((a.orig_id(),name,level,bytes(to_wkb(poly))))
        except (ValueError,RuntimeError) as ex:bad.append((a.orig_id(),name,str(ex)))
    pd.DataFrame(geoms,columns=['osm_id','name','admin_level','wkb']).to_parquet(OUT/'行政区面.parquet',index=False)
    pd.DataFrame(bad,columns=['osm_id','name','error']).to_csv(OUT/'行政区几何错误.csv',index=False)
    print('boundary geometries',len(geoms),'error',len(bad),'reference_bytes',subset.stat().st_size,flush=True)
if __name__=='__main__':main()
