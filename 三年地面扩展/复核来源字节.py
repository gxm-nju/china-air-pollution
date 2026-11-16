"""逐文件验证旧清单与新增日窗。参数为完整原工程根目录。"""
import hashlib
from pathlib import Path
import sys
import pandas as pd
root=Path(sys.argv[1]).resolve()
out=Path(__file__).resolve().parent
extension=root/'扩展实验/三年地面补采'
checks={}
def add(group,path,expected=None,n=None):
    if path in checks: return
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    size=path.stat().st_size
    assert (expected is None or expected==digest) and (n is None or n==size), path
    checks[path]=(group,str(path.relative_to(root)),size,digest)
old=pd.read_csv(root/'扩展实验/规模核算/原始文件按内容去重.csv')
for g,scope,path,n,h,_ in old.itertuples(index=False,name=None):
    if g=='地面':continue
    add(g,(root if scope=='原10月试验' else root/'多源数据与实验')/path,h,n)
ground_rows=0
for r in pd.read_csv(out/'分析输入逐日清单.csv').itertuples():
    path=root/r.path
    add('地面',path,r.sha256,r.bytes)
    with path.open('rb') as f:
        ground_rows+=sum(len(line) for line in f if line.split(b',',3)[2:3] in ([b'PM2.5'],[b'NO2']))
for r in pd.read_csv(out/'已核实新增日窗.csv').itertuples():
    add('卫星',extension/f'卫星扩月/区域日窗/{r.day}.npz',r.regional_sha256,r.regional_bytes)
for r in pd.read_csv(out/'原始区域窗口清单.csv').itertuples():
    add('气象',extension/f'多源复算/ERA5边界层补采/{r.month}.nc',r.sha256,r.bytes)
ledger=pd.DataFrame(checks.values(),columns=['source','path','bytes','sha256'])
ledger.to_csv(out/'更新原始输入校验.csv.gz',index=False,compression=dict(method='gzip',mtime=0))
summary=ledger.drop_duplicates('sha256').groupby('source').bytes.sum()
summary.to_csv(out/'更新原始文件字节.csv')
print('SHA去重文件（含超出时空或指标范围部分）',summary,summary.sum())
print('地面两种指标原始行（含时间、空站列、未映射列等）',ground_rows)
print('Q2 区域日窗',ledger[ledger.path.str.endswith('.npz')&ledger.source.eq('卫星')].bytes.sum())
