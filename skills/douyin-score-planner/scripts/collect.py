"""Verify actual new downloads. Never drives a browser or calls the store."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile
from planner import read_table, write_json

FIELDS={'reviews':{'订单ID','商品ID','商品评分','签收时间','评价时间'},
        'quality':{'订单ID','品退原因'},
        'service':{'客服ID','不满意率','点评会话总数'}}

def inventory(directory):
    directory=Path(directory).expanduser().resolve()
    if not directory.is_dir(): raise ValueError('下载目录不存在')
    result={}
    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower()=='.xlsx':
            s=p.stat();result[p.name]={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
    return {'directory':str(directory),'files':result,'captured_at_ns':time.time_ns()}

def verify_download(baseline, kind, shop_key, destination, expected_rows=None, timeout=30):
    if kind not in FIELDS or not shop_key: raise ValueError('缺少报表类型或已核对的店铺身份')
    directory=Path(baseline['directory']).resolve()
    dest=Path(destination).expanduser().resolve()
    if dest==directory or directory in dest.parents: raise ValueError('私有归档目录须独立于下载目录')
    until=time.monotonic()+max(0,min(timeout,180)); previous={}
    while True:
        now=inventory(directory)
        candidates=[]
        for name,meta in now['files'].items():
            if name in baseline['files'] and meta==baseline['files'][name]: continue
            if previous.get(name)!=meta: continue
            path=directory/name
            try: rows=read_table(path)
            except (ValueError,OSError,EOFError,zipfile.BadZipFile): continue
            if rows and FIELDS[kind]<=set(rows[0]): candidates.append((path,rows))
        if len(candidates)>1: raise ValueError('有多份新报表符合条件；请由宿主核对本次导出文件，不能猜测')
        if candidates:
            path,rows=candidates[0]
            if expected_rows is not None and len(rows)!=int(expected_rows):
                raise ValueError('新导出行数与后台查询数量不一致，未归档')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            # Store identity comes from the host's observed shop check, not inferred from filenames.
            slug=hashlib.sha256(shop_key.encode()).hexdigest()[:16]
            target_dir=dest/slug;target_dir.mkdir(parents=True,exist_ok=True)
            target=target_dir/(kind+'-'+digest[:16]+'.xlsx')
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError('归档冲突')
            else:
                with path.open('rb') as src,target.open('xb') as out: shutil.copyfileobj(src,out)
            return {'status':'download_verified','kind':kind,'shop_key':shop_key,'rows':len(rows),
                    'sha256':digest,'archived_file':str(target),'original_preserved':True}
        if time.monotonic()>=until: raise ValueError('未观察到本次新下载完成的匹配报表；不能把旧文件当取数成功')
        previous=now['files'];time.sleep(1)

def main():
    p=argparse.ArgumentParser(description='导出前记录基线，导出后验证新文件并归档到私有目录')
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('baseline');b.add_argument('--directory',default=str(Path.home()/'Downloads'));b.add_argument('--out',required=True)
    f=sub.add_parser('finish');f.add_argument('--baseline',required=True);f.add_argument('--kind',choices=list(FIELDS),required=True)
    f.add_argument('--shop-key',required=True);f.add_argument('--destination',required=True)
    f.add_argument('--expected-rows',type=int);f.add_argument('--timeout',type=int,default=30);f.add_argument('--receipt',required=True)
    args=p.parse_args()
    try:
        if args.command=='baseline': write_json(args.out,inventory(args.directory));result={'baseline':args.out}
        else:
            baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
            result=verify_download(baseline,args.kind,args.shop_key,args.destination,args.expected_rows,args.timeout)
            write_json(args.receipt,result)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError) as e:
        print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__': raise SystemExit(main())
