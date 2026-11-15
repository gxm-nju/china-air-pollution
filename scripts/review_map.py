"""Offline point-by-point map workbook from OSM geometries; preserve incomplete checks."""
from pathlib import Path
import json,html
import pandas as pd
import shapely
import numpy as np
from ground import ROOT
Q=ROOT/'扩展实验/核验'
def main():
    s=pd.read_csv(Q/'站点200条空间核验.csv',keep_default_na=False)
    sub={'同安区':'厦门','龙文区':'漳州'}
    s['补核判定']=s.判定;s['补核代码']=''
    ok=(s.判定=='名称需复核') & s.图上县级区.map(sub).eq(s.city)
    s.loc[ok,'补核判定']='区代码支持城市归属'
    s.loc[ok,'补核代码']=s.loc[ok,'图上县级区'].map({'同安区':'350212','龙文区':'350603'})
    s.to_csv(Q/'站点200条含区划补核.csv',index=False)
    f=pd.read_csv(Q/'火点200条空间核验.csv',keep_default_na=False)
    a=pd.read_parquet(Q/'行政区面.parquet');a=a[a.admin_level.isin(['5','6'])].reset_index(drop=True)
    g=shapely.from_wkb(a.wkb.to_numpy());tree=shapely.STRtree(g)
    def draw(x,y):
        if x=='':return ''
        x=float(x);y=float(y);e=.42
        def xy(p,q):return (p-x)/e*150+150,150-(q-y)/e*150
        window=shapely.box(x-e,y-e,x+e,y+e);out=[]
        for i in tree.query(window):
            z=shapely.clip_by_rect(g[i].boundary,x-e,y-e,x+e,y+e).simplify(.003)
            for obj in shapely.get_parts(z):
                if obj.geom_type not in ['LineString','LinearRing']:continue
                pts=' '.join(f'{u:.1f},{v:.1f}' for u,v in [xy(*p) for p in obj.coords]);color='#497e82' if a.admin_level[i]=='5' else '#9dadaa'
                out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.3"/>')
        gx=np.floor(x*4+.5)/4;gy=np.floor(y*4+.5)/4;u,v=xy(gx-.125,gy+.125);w=.25/e*150
        out.append(f'<rect x="{u:.1f}" y="{v:.1f}" width="{w:.1f}" height="{w:.1f}" fill="#5ab3b3" fill-opacity=".10" stroke="#137a78" stroke-dasharray="4 3"/><circle cx="150" cy="150" r="5" fill="#b13619"/>')
        return '<svg viewBox="0 0 300 300" role="img" aria-label="坐标及附近行政区边界">'+''.join(out)+'</svg>'
    records=[]
    for kind,frame in [('站点',s),('火点',f)]:
        for ix,r in frame.reset_index(drop=True).iterrows():
            x,y=(r.lon,r.lat) if kind=='站点' else (r.longitude_center,r.latitude_center)
            title=(r.station+' '+r.city) if kind=='站点' else str(r.local_slot)
            desc=r.补核判定 if kind=='站点' else r.耕地口径+'；'+('四角地级归属一致' if r['四角行政归属稳定'] else '跨行政边界')
            records.append(dict(k=kind,n=ix+1,title=title,coord=f'{x}, {y}' if x!='' else '缺坐标',area=' / '.join(z for z in [r.图上省,r.图上地级区,r.图上县级区] if z),desc=desc,map=draw(x,y)))
    page='''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>站点与火点空间核验</title><style>body{max-width:760px;margin:3em auto;padding:0 1em;font:16px/1.7 system-ui;color:#243736}svg{width:min(100%,440px);background:#f5f4ee;border:1px solid #b8c3be}select,button,input{font:inherit;margin:4px;padding:4px 10px}</style><h1>站点与火点空间核验</h1><label>样本 <select id="kind"><option>站点</option><option>火点</option></select></label><label>序号 <input type=number id="num" min=1 max=200 value=1></label><button id="prev">上一条</button><button id="next">下一条</button><h2 id="title"></h2><main id="pic"></main><p id="summary"></p><p>红点为站点坐标或火点格中心。虚线方框是最近的 ERA5 0.25° 网格。地级和县级边界取自 2026 年 OSM 快照，底图数据 © OpenStreetMap contributors（ODbL）。</p><script>const data=DATA;const el=id=>document.getElementById(id);function show(){const n=Math.max(1,Math.min(200,Number(el('num').value)||1));el('num').value=n;const a=data.find(d=>d.k===el('kind').value&&d.n===n);el('title').textContent=a.k+' '+n+' / 200　'+a.title;el('pic').innerHTML=a.map||'没有可绘制的坐标';el('summary').textContent=[a.coord,a.area,a.desc].filter(Boolean).join(' ｜ ')}el('kind').onchange=show;el('num').onchange=show;el('prev').onclick=()=>{el('num').stepDown();show()};el('next').onclick=()=>{el('num').stepUp();show()};show();</script>'''
    (Q/'400条地图抽样复核.html').write_text(page.replace('DATA',json.dumps(records,ensure_ascii=False).replace('</','<\\/')))
    print(s.补核判定.value_counts().to_dict(),len(records))
if __name__=='__main__':main()
