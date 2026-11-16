"""Resume by month, validate existing orbits and retain per-orbit outcomes."""
import csv
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from catalog import ROOT, catalogue

LOG = ROOT / '记录'
MONTHS = [f'{year}-{month:02d}' for year in (2023, 2024, 2025) for month in range(2, 13)]

def prepare(month):
    path = LOG / f'轨道清单_{month}.csv'
    if not path.is_file():
        try:
            catalogue(month)
        except Exception as exc:
            print(month, '目录检索失败', repr(exc), flush=True)
            return False
    return True

def complete(month):
    table = LOG / f'卫星下载_{month}.csv'
    if not table.exists():
        return False
    with table.open() as f:
        rows = list(csv.DictReader(f))
    with (LOG / f'轨道清单_{month}.csv').open() as f:
        expected = {r['orbit'] for r in csv.DictReader(f)}
    if not expected or {r['orbit'] for r in rows} != expected:
        return False
    for row in rows:
        p = ROOT / '原始数据/S5P' / (row['orbit'] + '.npz')
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != row['sha256']:
            return False
    return True

def main():
    LOG.mkdir(exist_ok=True, parents=True)
    (ROOT/'原始数据/S5P').mkdir(exist_ok=True, parents=True)
    with (LOG/'续采互斥锁').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with ThreadPoolExecutor(2) as pool:
            futures = {m: pool.submit(prepare, m) for m in MONTHS}
            for month in MONTHS:
                if not futures[month].result() or complete(month):
                    continue
                print(datetime.now().isoformat(timespec='seconds'), month, '续采', flush=True)
                with (LOG / f'续采_{month}.log').open('a') as log:
                    subprocess.run([sys.executable, str(ROOT/'程序/sat.py'), month], stdout=log, stderr=log, check=True)
                print(month, '已完整核验' if complete(month) else '有缺轨', flush=True)
if __name__ == '__main__':
    main()
