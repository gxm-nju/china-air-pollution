"""从检索文本或官方页面重新提取当月统计。输出仅保留数值、出处和取值证据。"""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import json
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/bulletins'

class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'h1', 'h2'):
            self.parts.append('\n')

def extract(month, region, text):
    n_sites = r'全国(\d+)个地级及以上城市' if region == '全国' else r'长三角地区(\d+)个城市'
    lines = []
    for source_line in text.splitlines():
        line = re.sub(r'^L\d+:','',source_line).strip().replace('_{','').replace('}', '')
        line = re.sub(r'\s+', '', line)
        if not re.search(n_sites,line) or line.startswith(('图','表','注','【')):
            continue
        # 月报经常同段紧随“1—N月”。先截走累计值，再找当月。
        line = re.split(r'(?:20\d\d年)?1[—–~～至\-－]+\d{1,2}月',line)[0]
        if not re.search(rf'(?<![0-9]){int(month[5:])}月',line):
            continue
        lines.append(line)
    body = '。'.join(lines)
    if not body:
        raise ValueError((month,region,'没有定位到月度段落'))
    def metric(pattern):
        match = re.search(pattern, body)
        if not match:
            raise ValueError((month,region,pattern,body[:750]))
        return float(match.group(1)),match.group()
    pm, ep = metric(r'PM2\.5(?:平均)?浓度为?([\d.]+)微克/立方米')
    good, eg = metric(r'(?:平均)?(?:空气质量)?优良天数比例为?([\d.]+)%')
    # 沙尘专属条款另有比例，绝不能拿它代替所有污染物的等级比例。
    before_dust = re.split(r'(?:未出现)?由沙尘天气导致',body)[0]
    heavy_match = re.search(r'(?:平均)?重度及以上污染天数比例为?([\d.]+)%',before_dust)
    zero = re.search(r'未(?:出现|发生)(?:重度及以上污染|重污染)天',before_dust)
    if heavy_match:
        heavy, eh = float(heavy_match[1]), heavy_match[0]
    elif zero:
        heavy, eh = 0.0, zero[0]
    else:
        raise ValueError((month,region,"重度比例不明确",before_dust))
    return dict(region=region,city_count=int(re.search(n_sites,body)[1]),pm25=pm,
                good_pct=good,heavy_pct=heavy,evidence=[ep,eg,eh])

def write_month(month, url, text):
    records=[extract(month,reg,text) for reg in ('全国','长三角')]
    (RAW / f'{month}.json').write_text(json.dumps(dict(month=month,url=url,records=records),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--retrieved', type=Path, help='从已有检索文本导入')
    ap.add_argument('--refresh',action='store_true',help='通过公开网页刷新')
    args=ap.parse_args()
    if args.retrieved:
        for path in sorted(args.retrieved.glob('20??-??.json')):
            record=json.loads(path.read_text())
            write_month(path.stem,record['url'],record['txt'])
    elif args.refresh:
        for path in sorted(RAW.glob('*.json')):
            doc=json.loads(path.read_text())
            with urllib.request.urlopen(doc['url'],timeout=45) as response:
                parser=Paragraphs()
                parser.feed(response.read().decode('utf-8-sig'))
            write_month(doc['month'],doc['url'],''.join(parser.parts))
            time.sleep(1)
    else:
        ap.error('请选择 --retrieved 或 --refresh；分析现有快照可执行 analyze.py')
