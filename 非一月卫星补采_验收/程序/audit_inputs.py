"""Freeze unique, validated regional inputs against both catalogues and download ledgers."""
from pathlib import Path
import argparse
import csv
import json
import hashlib
from sat import validate

ROOT = Path(__file__).resolve().parents[1]
JAN = ROOT.parent / '网格与过境复算'

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def save(path, records, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'记录')
    dest = parser.parse_args().output
    dest.mkdir(parents=True, exist_ok=True)
    accepted, coverage, issues = [], [], []
    seen_orbits, seen_hashes = set(), set()
    empty = []
    for year in range(2023, 2026):
        for m in range(1, 13):
            month = f'{year}-{m:02d}'
            directory = JAN if m == 1 else ROOT
            catalog = directory / '记录' / f'轨道清单_{month}.csv'
            ledger = directory / '记录' / f'卫星下载_{month}.csv'
            if not (catalog.is_file() and ledger.is_file()):
                issues.append(dict(month=month, reason='catalogue or download ledger missing'))
                continue
            downloads = {r['orbit']:r for r in rows(ledger)}
            targets = rows(catalog)
            monthly = []
            empty_count = 0
            for target in targets:
                orbit = target['orbit']
                record = downloads.get(orbit, {})
                path = directory / '原始数据/S5P' / (orbit + '.npz')
                try:
                    if not path.is_file():
                        raise ValueError(record.get('error') or 'file missing')
                    n, q = validate(path)
                    size = path.stat().st_size
                    sha = hashlib.sha256(path.read_bytes()).hexdigest()
                    if (sha != record.get('sha256') or size != int(float(record['bytes'])) or n != int(float(record['pixels'])) or q != int(float(record['valid']))):
                        raise ValueError('ledger mismatch')
                    if orbit in seen_orbits:
                        raise ValueError('duplicate orbit')
                    seen_orbits.add(orbit)
                    if not n:
                        empty_count += 1
                        empty.append(dict(month=month,orbit=orbit,source=record['url'],bytes=size,sha256=sha))
                        continue
                    if sha in seen_hashes:
                        raise ValueError('repeated nonempty file content')
                    seen_hashes.add(sha)
                    monthly.append(dict(month=month, orbit=orbit, source=record['url'], catalogue=target['CDSE'],
                                        bytes=size, sha256=sha, region_pixels=n, quality_pixels=q))
                except Exception as exc:
                    issues.append(dict(month=month, orbit=orbit, reason=str(exc)))
            accepted.extend(monthly)
            coverage.append(dict(month=month, expected=len(targets), verified=len(monthly)+empty_count, nonempty=len(monthly), empty=empty_count, bytes=sum(r['bytes'] for r in monthly),
                                 region_pixels=sum(r['region_pixels'] for r in monthly), quality_pixels=sum(r['quality_pixels'] for r in monthly)))
    save(dest/'最终逐轨核验.csv', accepted, list(accepted[0]))
    save(dest/'区域无像元轨道.csv', empty, ['month','orbit','source','bytes','sha256'])
    save(dest/'最终逐月覆盖.csv', coverage, list(coverage[0]))
    (dest/'未完成项.json').write_text(json.dumps(issues, ensure_ascii=False, indent=2))
    print(len(coverage), len(accepted), sum(r['bytes'] for r in accepted), len(issues), flush=True)

if __name__ == '__main__':
    main()
