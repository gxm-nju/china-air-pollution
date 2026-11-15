"""Verify pilot provenance and restore the three frozen research archives without replacing pilot outputs."""
import csv
import hashlib
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '扩展实验/核验'
BASE = ROOT / '多源数据与实验'

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def verify(p, row):
    ok = p.is_file() and p.stat().st_size == int(row['bytes']) and digest(p) == row['sha256']
    if not ok:
        raise ValueError(f"校验失败 {p}")
    return row

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pilot = list(csv.DictReader((ROOT/'logs/原始文件校验与来源.csv').open(encoding='utf-8-sig')))
    for item in pilot:
        verify(ROOT / item['path'], item)
    archives = sorted((ROOT/'已验证归档').glob('*.zip'))
    if len(archives) != 3:
        raise ValueError('需要三个完整归档')
    seen = set()
    for archive in archives:
        with ZipFile(archive) as z:
            for member in z.infolist():
                path = PurePosixPath(member.filename)
                if path.parts[0] != ROOT.name or '..' in path.parts or member.is_dir():
                    raise ValueError(member.filename)
                rel = Path(*path.parts[1:])
                if rel in seen:
                    raise ValueError(rel)
                seen.add(rel)
                dest = BASE / rel
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_name(dest.name+'.part')
                with z.open(member) as src, tmp.open('wb') as out:
                    shutil.copyfileobj(src, out, length=1024*1024)
                tmp.replace(dest)
    ledger = list(csv.DictReader((BASE/'logs/SHA256SUMS.csv').open(encoding='utf-8-sig')))
    assert {Path(r['path']) for r in ledger} | {Path('logs/SHA256SUMS.csv')} == seen
    for r in ledger:
        verify(BASE/r['path'], r)
    with (OUT/'原始试验与归档校验.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['来源','相对路径','字节','SHA256'])
        for label, rows in [('原10月试验',pilot),('此前扩展归档',ledger)]:
            for r in rows:w.writerow([label,r['path'],r['bytes'],r['sha256']])
        for p in archives:w.writerow(['归档本身',p.name,p.stat().st_size,digest(p)])
    print(f'pilot={len(pilot)} baseline_files={len(seen)} baseline_hashes={len(ledger)} archives={len(archives)}',flush=True)
if __name__=='__main__': main()
