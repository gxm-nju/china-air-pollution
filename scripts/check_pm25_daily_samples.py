"""Recompute three published city-day values from hashed station-day CSVs."""
import argparse
import csv
import hashlib
import math
from pathlib import Path
from statistics import mean

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SAMPLES = [('2023-01-22', '南京'), ('2024-02-10', '徐州'), ('2025-06-15', '南京')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path, help='含原始地面日档的工程根目录')
    parser.add_argument('--output', type=Path, help='保存逐城市日对照表')
    args = parser.parse_args()
    archive = REPO / '三年地面扩展'
    ledger = pd.read_csv(archive / '分析输入逐日清单.csv').set_index('date', verify_integrity=True)
    mapping = pd.read_csv(REPO / 'data/cleaned/station_city.csv').set_index('station', verify_integrity=True)
    published = pd.read_parquet(archive / '全国城市日.parquet').set_index(['date', 'city'], verify_integrity=True)
    checks = []
    for day, city in SAMPLES:
        item = ledger.loc[day]
        path = args.project / item.path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item.sha256
        stations = mapping.index[mapping.city == city]
        hourly = {}
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row['type'] != 'PM2.5':
                    continue
                hour = int(row['hour'])
                assert row['date'] == day.replace('-', '') and 0 <= hour < 24 and hour not in hourly
                values = [float(row[s]) for s in stations if row.get(s)]
                valid = [v for v in values if math.isfinite(v) and v >= 0]
                hourly[hour] = mean(valid) if valid else None
        hours = [v for v in hourly.values() if v is not None]
        value = mean(hours)
        ref = published.loc[(pd.Timestamp(day), city)]
        qualified = len(hours) >= 20
        heavy = qualified and value > 150
        assert len(hours) == ref.valid_hours and qualified == ref.qualified and heavy == ref.heavy
        assert math.isclose(value, ref.pm25, rel_tol=0, abs_tol=1e-6)
        checks.append({'日期': day, '城市': city, '有效小时': len(hours), '小时均值再平均': value,
                       '发布表PM2.5': ref.pm25, '纳入合格城市日': qualified, '计入超阈值': heavy,
                       '原档SHA256': item.sha256})
    result = pd.DataFrame(checks)
    print(result.drop(columns='原档SHA256').to_string(index=False))
    if args.output:
        result.to_csv(args.output, index=False)


if __name__ == '__main__':
    main()
