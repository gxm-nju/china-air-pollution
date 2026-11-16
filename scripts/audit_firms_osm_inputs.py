#!/usr/bin/env python3
"""Read-only input audit; stdout JSON. Does not materialize a new data subset.
Run: python3 audit_inputs.py --root /path/to/中国城市重污染日实验
This matches the observed unquoted numeric FIRMS CSV schema, rejects quotes.
"""
import argparse, hashlib, json
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
COLS=['latitude','longitude','acq_date','acq_time','confidence','type','frp']
def run(root):
    counts=Counter(); manifest=[]
    for p in sorted((root/'多源数据与实验/data/raw/firms').glob('*.csv')):
        digest=hashlib.sha256(); rows=0
        with p.open('rb') as f:
            header=next(f); digest.update(header); names=header.strip().decode().split(',')
            indices=[names.index(k) for k in COLS]
            for line in f:
                digest.update(line); rows+=1
                if b'"' in line: raise ValueError('Quoted CSV requires exact-span parser: '+str(p))
                fields=line.rstrip(b'\r\n').split(b',')
                if len(fields)!=len(names): raise ValueError('Unexpected row schema: '+str(p))
                values=[fields[i] for i in indices]; d=dict(zip(COLS,values))
                # Hypothetical LF CSV: six commas and one LF, no header.
                seven=sum(map(len,values))+7
                counts['all_rows']+=1; counts['all_selected_columns_bytes']+=seven
                lat,lon=float(d['latitude']),float(d['longitude']); hhmm=int(d['acq_time']); hh,mm=divmod(hhmm,100)
                try: dt=datetime.strptime(d['acq_date'].decode(),'%Y-%m-%d')+timedelta(hours=hh+8,minutes=mm)
                except ValueError: continue
                valid=-90<=lat<=90 and -180<=lon<=180 and 0<=hh<24 and 0<=mm<60
                conf=30<=float(d['confidence'])<=100 if p.name.startswith('modis') else d['confidence'] in (b'n',b'h')
                typ=d['type']; inside=datetime(2019,1,1)<=dt<datetime(2026,1,1)
                if valid and conf and typ==b'0' and inside:
                    counts['retained_type0_rows']+=1; counts['retained_type0_original_line_bytes']+=len(line); counts['retained_type0_selected_columns_bytes']+=seven
                if valid and conf and typ==b'2':
                    counts['quality_type2_rows']+=1; counts['quality_type2_original_line_bytes']+=len(line); counts['quality_type2_selected_columns_bytes']+=seven
                # Diagnostic rectangle uses UTC date, unlike the local-year primary filter.
                if valid and conf and typ==b'0' and b'2023-01-01'<=d['acq_date']<=b'2025-12-31' and 27<=lat<35 and 114<=lon<123:
                    counts['rectangle_utc2023_2025_type0_rows']+=1;counts['rectangle_utc2023_2025_type0_original_line_bytes']+=len(line);counts['rectangle_utc2023_2025_type0_selected_columns_bytes']+=seven
        manifest.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest.hexdigest(),'rows':rows})
    counts['file_bytes']=sum(x['bytes'] for x in manifest)
    osm=[]
    for rel in ['data/raw/osm/station_cells.osm.pbf','扩展实验/核验/农业用地参照.osm.pbf','扩展实验/核验/行政区边界.osm.pbf']:
        p=root/rel
        if p.exists():
            with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
            osm.append({'path':rel,'bytes':p.stat().st_size,'sha256':h})
        else: osm.append({'path':rel,'missing':True})
    return {'counts':dict(counts),'firms_manifest':manifest,'osm_subsets':osm,'osm_unadjusted_sum_bytes':sum(x.get('bytes',0) for x in osm),'warnings':['Column bytes are an unmaterialized LF-CSV estimate, not a file size.','Do not add full files, selected rows and derived data together.','OSM sum is not object-deduplicated.','This audit does not establish total course-compliant effective volume.']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();print(json.dumps(run(a.root),ensure_ascii=False,indent=2))
