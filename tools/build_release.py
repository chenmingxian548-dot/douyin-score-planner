"""Build a source-only ZIP from a closed allowlist; never include local store data."""
from pathlib import Path
import hashlib
import json
import re
import zipfile
import argparse

ROOT=Path(__file__).resolve().parents[1]
SKILL='skills/douyin-score-planner/'
PUBLIC_FILES=['README.md','WORKBUDDY.md','VALIDATION.md','GITHUB_RELEASE.md','.gitignore',
    'tools/build_release.py','tests/test_planner.py','tests/test_setup.py','tests/test_downloads.py','tests/test_collector.cjs','tests/test_portable.py']+[
    SKILL+p for p in ['SKILL.md','requirements.lock','agents/openai.yaml','assets/example-goal.json',
    'scripts/planner.py','scripts/setup.py','scripts/collect.py','scripts/cua-collector.js',
    'references/data.md','references/rules.md','references/collection.md','references/hosts.md']]

def source_manifest():
    files={}
    patterns=[rb'/Users/[A-Za-z0-9._-]+/',rb'(?<!\d)\d{16,}(?!\d)',
              rb'(?:sk-proj-|ghp_|github_pat_)[A-Za-z0-9_]{15,}']
    for name in sorted(PUBLIC_FILES):
        p=ROOT/name
        if not p.is_file() or p.is_symlink(): raise ValueError('Missing or linked public source: '+name)
        content=p.read_bytes()
        if any(re.search(pattern,content) for pattern in patterns):
            raise ValueError('Possible private content in '+name)
        files[name]=hashlib.sha256(content).hexdigest()
    digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    return {'schema':'douyin-source-manifest/v1','source_digest':digest,'files':files}

def portable_payload(host):
    if host not in ('generic','workbuddy'): raise ValueError('Unsupported host; do not imply unverified compatibility')
    source_manifest()  # same closed allowlist and privacy checks as source distributions
    files={}
    for name in PUBLIC_FILES:
        if not name.startswith(SKILL): continue
        relative=name[len(SKILL):]
        content=(ROOT/name).read_bytes()
        if host=='workbuddy' and relative=='SKILL.md':
            _,header,body=content.decode().split('---',2)
            metadata={'name':'douyin-score-planner','display_name':'抖店体验分与目标分析',
                'display_name_en':'Douyin Shop Score Planner',
                'description':'按店铺目标和期限分析原始报表、体验分及准入差距；只读，不修改后台。',
                'description_zh':'检查资料和环境，复算原始表格并生成多情景报告。',
                'description_en':'Read-only shop data checks and conditional score planning.',
                'version':'0.1.0','author':'douyin-score-planner'}
            content=('---\n'+'\n'.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in metadata.items())+'\n---'+body).encode()
        files['douyin-score-planner/'+relative]=content
    return files

def build():
    manifest=source_manifest();out=ROOT/'dist';out.mkdir(exist_ok=True)
    path=out/('douyin-score-planner-v0.1.0-'+manifest['source_digest'][:10]+'.zip')
    if path.exists(): raise ValueError('Package already exists; do not overwrite')
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(PUBLIC_FILES):
            info=zipfile.ZipInfo('douyin-score-planner/'+name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,(ROOT/name).read_bytes())
        z.writestr('douyin-score-planner/MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return {'archive':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'public_file_count':len(PUBLIC_FILES),'source_digest':manifest['source_digest']}

def build_portable(host):
    files=portable_payload(host)
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
    digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    path=out/('douyin-score-planner-'+host+'-v0.1.0-'+digest[:10]+'.zip')
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(files.items()): z.writestr(name,content)
    return {'archive':str(path),'host':host,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'files':len(files),'source_digest':digest}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--format',choices=['source','generic','workbuddy'],default='source')
    args=p.parse_args()
    print(json.dumps(build() if args.format=='source' else build_portable(args.format),ensure_ascii=False,indent=2))
