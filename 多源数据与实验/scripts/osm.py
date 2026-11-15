"""GDAL/OGR Python（本轮 /usr/bin/python3）由四省级 PBF 生成41个城市的0.25°地表特征。"""
from pathlib import Path
import tempfile
import subprocess
import csv
from osgeo import ogr,osr,gdal
gdal.UseExceptions()
ROOT=Path(__file__).resolve().parents[1]
def grid(x):return int(x*4+0.5)/4
def ref(epsg):
    s=osr.SpatialReference();s.ImportFromEPSG(epsg);s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER);return s
def rect(w,s,e,n):return ogr.CreateGeometryFromWkt(f'POLYGON (({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))')
def main():
    with (ROOT/'data/cleaned/case_city_grid.csv').open() as f:cities=[x for x in csv.DictReader(f) if x['source_group']]
    allowed=('motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','service','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link')
    roads="highway IN ("+','.join("'"+x+"'" for x in allowed)+")"
    with tempfile.TemporaryDirectory() as tmp:
        sources=[]
        for p in sorted((ROOT/'data/raw/osm').glob('*.pbf')):
            gp=Path(tmp)/(p.stem+'.gpkg')
            for lyr,clause,short,sel in [('lines',roads,'roads','osm_id,highway'),('multipolygons',"landuse='industrial'",'industry','osm_id,osm_way_id,landuse')]:
                cmd=['ogr2ogr','-f','GPKG']
                if gp.exists():cmd+=['-update']
                subprocess.run(cmd+[str(gp),str(p),lyr,'-where',clause,'-select',sel,'-nln',short,'-lco','SPATIAL_INDEX=YES'],check=True)
            sources.append(ogr.Open(str(gp)))
        projection=osr.CoordinateTransformation(ref(4326),ref(32650));rows=[]
        for c in cities:
            x,y=grid(float(c['lon'])),grid(float(c['lat']));w,e,s,n=x-.125,x+.125,y-.125,y+.125
            frame=rect(w,s,e,n);met=frame.Clone();met.Transform(projection);area=met.GetArea()/1e6
            length=0.;industry=0.;counts=[]
            for kind in ['roads','industry']:
                seen=set()
                for src in sources:
                    layer=src.GetLayerByName(kind);layer.SetSpatialFilterRect(w,s,e,n)
                    for feature in layer:
                        osm_id=feature.GetField('osm_id')
                        tag='relation' if kind=='industry' and osm_id else 'way'
                        if not osm_id and kind=='industry':osm_id=feature.GetField('osm_way_id')
                        key=(tag,osm_id)
                        if not osm_id or key in seen:continue
                        geom=feature.GetGeometryRef()
                        if not geom or not geom.Intersects(frame):continue
                        if kind=='industry' and not geom.IsValid():geom=geom.MakeValid()
                        seg=geom.Intersection(frame)
                        if not seg or seg.IsEmpty():continue
                        seen.add(key);seg.Transform(projection)
                        if kind=='roads':length+=seg.Length()/1000
                        else:industry+=seg.GetArea()/1e6
                counts.append(len(seen))
            rows.append(dict(city=c['city'],lon_grid=x,lat_grid=y,area_km2=area,roads_n=counts[0],road_length_km=length,road_km_per_km2=length/area,industrial_n=counts[1],industrial_sum_km2=industry,industrial_area_ratio=industry/area))
        out=ROOT/'data/cleaned/osm_city_features.csv'
        with out.open('w') as f:
            z=csv.DictWriter(f,fieldnames=rows[0]);z.writeheader();z.writerows(rows)
        print('OSM cities',len(rows),'road features',sum(x['roads_n'] for x in rows),'industrial features',sum(x['industrial_n'] for x in rows))
if __name__=='__main__':main()
