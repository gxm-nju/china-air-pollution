"""Reference-complete OSM subset for the station-cell objects actually counted."""
import osmium
import pandas as pd
from ground import CL,RAW
def run():
    source=RAW/'osm/china-261114.osm.pbf';target=RAW/'osm/station_cells.osm.pbf'
    selected=pd.read_parquet(CL/'osm/used_objects.parquet',columns=['object_type','osm_id']).drop_duplicates()
    w=set(selected[selected.object_type=='w'].osm_id.astype(int));r=set(selected[selected.object_type=='r'].osm_id.astype(int))
    local=target.with_name('station_cells.part.osm.pbf')
    with osmium.BackReferenceWriter(local,source,overwrite=True,relation_depth=2) as writer:
        fp=osmium.FileProcessor(source,entities=osmium.osm.WAY | osmium.osm.RELATION)
        for obj in fp:
            if obj.is_way() and obj.id in w: writer.add_way(obj)
            elif obj.is_relation() and obj.id in r: writer.add_relation(obj)
    local.replace(target);print('original ways',len(w),'relations',len(r),'bytes with referenced geometry',target.stat().st_size)
if __name__=='__main__':run()
