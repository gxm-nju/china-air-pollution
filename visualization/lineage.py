"""Render the cross-source relationships in the three analyses."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties

def main():
    fonts=['PingFang SC','Noto Sans CJK SC','Microsoft YaHei','Arial Unicode MS']
    available={f.name for f in font_manager.fontManager.ttflist}
    chosen=next((s for s in fonts if s in available),None)
    if chosen:plt.rcParams['font.family']=chosen
    fig,ax=plt.subplots(figsize=(12.2,5),dpi=150)
    fig.patch.set_facecolor('white');ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    x=[.02,.35,.70];width=[.28,.30,.28]
    for i,label in enumerate(['观测来源','跨源关联键','融合结果与研究问题']):
        ax.text(x[i]+.008,.93,label,color='#315c58',size=13,weight='bold')
    data=[
        ['FIRMS 火点、ERA5 风场\n地面 PM₂.₅、OSM 农田面','0.01° 火点归到 0.25° 网格\n北京小时、风向扇区、事件前基线','火点网格 × 小时 × 滞后\n上下风城市增幅差'],
        ['Sentinel-5P NO₂ 柱、地面 NO₂\nERA5 气象、OSM 路网与工业面','站号归城市、城市近邻卫星格\n有效地方太阳时转北京小时','城市 × 有效卫星日\n气象能否改善地面 NO₂ 预测'],
        ['地面 PM₂.₅、ERA5 风场和边界层\n春节与调休日期','同城连续超阈值日切分过程\n上风城市前 6 小时、假期窗口','城市 × 污染过程\n过程分组与春节比较']]
    for row,items in enumerate(data):
        y=.66-row*.29
        for col,label in enumerate(items):
            box=FancyBboxPatch((x[col],y),width[col],.19,boxstyle='round,pad=0.004,rounding_size=.014',facecolor=['#f1f3eb','#e1efea','#f7ede3'][col],edgecolor='none')
            ax.add_patch(box);ax.text(x[col]+.012,y+.095,label,ha='left',va='center',fontsize=10.9,linespacing=1.6,color='#203c39')
            if col<2:ax.annotate('',xy=(x[col+1]-.006,y+.095),xytext=(x[col]+width[col]+.006,y+.095),arrowprops={'arrowstyle':'->','color':'#69817a','lw':1.5})
    fig.savefig(Path(__file__).with_name('跨源关联图.png'),bbox_inches='tight',pad_inches=.12);plt.close(fig)
if __name__=='__main__':main()
