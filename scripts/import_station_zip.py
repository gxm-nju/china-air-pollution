"""Import only missing, validated station-day CSV files from a supplied annual archive."""
import argparse
import fcntl
import re
import shutil
from datetime import date
from pathlib import Path
from zipfile import ZipFile
from collect import EXT,BASE,ROOT,RAW,verified_paths,validated,sha,log
def main(archives):
    checks=verified_paths();added=skipped=0
    for archive in archives:
        src_hash=sha(archive)
        with ZipFile(archive) as z:
            for i in z.infolist():
                n=Path(i.filename).name
                if not re.fullmatch(r'china_sites_20(?:23|24|25)\d{4}\.csv',n):continue
                date.fromisoformat(n[-12:-4]);target=RAW/'air'/n
                old=next((p for p in [target,BASE/'data/raw/ground'/n] if p.is_file()),None)
                if old is not None:
                    if old not in checks or checks[old]!=(old.stat().st_size,sha(old)):raise ValueError(f'现有文件需核对 {old}')
                    skipped+=1;continue
                tmp=target.with_name(target.name+'.zip.part')
                with z.open(i) as src,tmp.open('wb') as out:shutil.copyfileobj(src,out,1024*1024)
                validated(tmp,'air');h=sha(tmp);tmp.replace(target);checks[target]=(target.stat().st_size,h)
                log(status='ok',path=str(target.relative_to(ROOT)),bytes=target.stat().st_size,sha256=h,url=archive.name,archive_sha256=src_hash,member=i.filename);added+=1
    print('新增',added,'已校验复用',skipped)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archives',type=Path,nargs='+');a=p.parse_args();EXT.mkdir(exist_ok=True)
    with (EXT/'采集.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main(a.archives)
