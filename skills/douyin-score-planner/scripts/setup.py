"""Bootstrap a private venv from pinned PyPI wheels. Never edits store settings."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

SKILL=Path(__file__).resolve().parents[1]

def compatible_python():
    candidates=[sys.executable]
    for name in ('python3.13','python3.12','python3.11','python3.10','python3','python'):
        found=shutil.which(name)
        if found: candidates.append(found)
    # Reuse an existing host-supplied runtime if present; never download a guessed host path.
    cache=Path.home()/'.cache/codex-runtimes'
    if cache.exists():
        candidates.extend(str(p) for p in cache.glob('*/dependencies/python/bin/python3'))
    for exe in dict.fromkeys(candidates):
        try:
            r=subprocess.run([exe,'-c','import sys; print(int(sys.version_info >= (3,10)))'],
                             capture_output=True,text=True,timeout=10)
            if r.returncode==0 and r.stdout.strip()=='1': return exe
        except (OSError,subprocess.TimeoutExpired): pass
    return None

def doctor(host=None):
    python=compatible_python()
    components={}
    for name in ('openpyxl','defusedxml'):
        components[name]=importlib.util.find_spec(name) is not None
    # Shell observation cannot attest to tool access, extension binding, shop identity or login.
    collection={'status':'requires_host_probe','ready':False,
        'next':'由宿主列出 CUA/浏览器工具，实际读取用户指定店铺后记录验证结果；不能通过 pip 安装此权限'}
    if host:
        collection['host_probe_evidence']=host
        collection['status']='host_probe_supplied_requires_review'
    return {'schema':'douyin-skill-doctor/v1','system':platform.system(),
        'python_running':platform.python_version(),'compatible_python':python,
        'components_in_current_python':components,
        'analysis_ready':sys.version_info>=(3,10) and all(components.values()),
        'automatic_collection':collection,
        'python_install_url':None if python else 'https://www.python.org/downloads/',
        'excel_required':False,'git_required':False,
        'store_settings_touched':False}

def _files(root):
    result={}
    for p in root.rglob('*'):
        if any(x in ('__pycache__','.venv','.git') for x in p.relative_to(root).parts): continue
        if p.is_symlink(): raise ValueError('技能包包含符号链接，拒绝复制')
        if p.is_file() and p.suffix!='.pyc':
            result[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def install_skill(source,destination):
    source,destination=Path(source).resolve(),Path(destination).expanduser().absolute()
    if not (source/'SKILL.md').is_file(): raise ValueError('不是完整 Skill 目录')
    if destination.is_symlink(): raise ValueError('安装目标为符号链接，拒绝写入')
    if destination==source: return {'status':'already_installed','path':str(destination)}
    if source in destination.parents or destination in source.parents:
        raise ValueError('安装来源与目标不能互相包含')
    if destination.exists():
        if destination.is_dir() and _files(source)==_files(destination):
            return {'status':'already_installed','path':str(destination)}
        raise ValueError('目标已有其他版本或用户修改，未覆盖；请使用其他目录或先核对差异')
    destination.parent.mkdir(parents=True,exist_ok=True)
    _files(source)
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.venv','.git'))
    return {'status':'installed','path':str(destination)}

def install_dependencies(venv_path):
    exe=compatible_python()
    if not exe:
        raise ValueError('没有 Python 3.10+；请从 https://www.python.org/downloads/ 安装后重试。未改系统环境。')
    env=Path(venv_path).expanduser().absolute()
    if env.is_symlink(): raise ValueError('环境目录不能为符号链接')
    if env.exists() and not (env/'pyvenv.cfg').is_file():
        raise ValueError('指定环境目录已有其他文件，未覆盖')
    if not env.exists(): subprocess.run([exe,'-m','venv',str(env)],check=True,timeout=90)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(python),'-m','pip','--isolated','install','--index-url','https://pypi.org/simple',
                    '--only-binary=:all:','--require-hashes','--disable-pip-version-check',
                    '-r',str(SKILL/'requirements.lock')],check=True,timeout=180)
    check=subprocess.run([str(python),str(Path(__file__)),'doctor'],check=True,capture_output=True,text=True,timeout=30)
    return {'status':'installed','python':str(python),'doctor':json.loads(check.stdout)}

def main():
    parser=argparse.ArgumentParser(description='检查环境、安装隔离依赖和 Skill；不访问抖店')
    sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor');d.add_argument('--host-capabilities')
    i=sub.add_parser('install-deps');i.add_argument('--venv',default=str(SKILL/'.venv'))
    s=sub.add_parser('install-skill');s.add_argument('--destination')
    args=parser.parse_args()
    try:
        if args.command=='doctor':
            host=json.loads(Path(args.host_capabilities).read_text()) if args.host_capabilities else None
            r=doctor(host)
        elif args.command=='install-deps': r=install_dependencies(args.venv)
        else:
            codex_root=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
            r=install_skill(SKILL,args.destination or codex_root/'skills/douyin-score-planner')
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__': raise SystemExit(main())
