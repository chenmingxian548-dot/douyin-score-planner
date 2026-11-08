"""Deterministic, local-only analysis. Does not call store APIs or execute UI actions."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

VERSION = '0.1.0'
GATES = ('brand', 'shop_type', 'average_score', 'saleable_7d',
         'information_quality', 'return_policy', 'violations')
GATE_NAMES = dict(zip(GATES, ('品牌实力', '店铺类型', '30天平均体验分', '7日日均可售商品',
                            '商品信息优秀率', '适用退货政策', '违规及处置')))
MAX_FILE_BYTES = 40 * 1024 * 1024
MAX_ROWS = 200000

def frac(value):
    if isinstance(value, bool):
        raise ValueError('布尔值不能作为分数')
    return Fraction(str(value))

def number(value, low=0, high=100):
    result = frac(value)
    if not low <= result <= high:
        raise ValueError(f'数值必须在 {low}–{high} 之间')
    return result

def integer(value, low=0, high=1000000):
    value = frac(value)
    if value.denominator != 1 or not low <= value <= high:
        raise ValueError('计数必须是范围内的整数')
    return int(value)

def day(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    return date.fromisoformat(str(value).strip()[:10])

def public_number(value):
    return None if value is None else float(value)

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    # Never overwrite another day's report or a pre-existing input.
    with path.open('x', encoding='utf-8') as f: f.write(text + '\n')

def merge_reviews(rows):
    shops = {r['shop_key'] for r in rows}
    if len(shops) > 1: raise ValueError('不能混合不同店铺的数据')
    merged = {}
    for raw in rows:
        r = dict(raw)
        r['star'] = integer(r['star'], 1, 5)
        r['signed'] = day(r['signed']).isoformat()
        r['reviewed'] = day(r['reviewed']).isoformat()
        if r['reviewed'] < r['signed']: raise ValueError('评价时间早于签收时间')
        key = (r['shop_key'], r['order_id'], r['product_id'])
        if not all(key): raise ValueError('缺少去重标识')
        if key in merged and merged[key] != r:
            raise ValueError('同一订单商品出现冲突；请分别分析新旧快照或核实更正依据')
        merged[key] = r
    return list(merged.values())

def review_summary(rows, as_of=None, window_days=30):
    rows = merge_reviews(rows)
    if as_of:
        end = day(as_of)
        start = end - timedelta(days=integer(window_days, 1, 365)-1)
        # as_of is the inclusive signed-date window end, not download/display date.
        rows = [r for r in rows if start <= day(r['signed']) <= end]
    stars = Counter(r['star'] for r in rows)
    total = sum(r['star'] for r in rows)
    by_signed = {}
    for r in rows:
        bucket = by_signed.setdefault(r['signed'], {'count':0, 'points':0})
        bucket['count'] += 1; bucket['points'] += r['star']
    rollout=[]
    if as_of:
        for i in range(window_days+1):
            on=end+timedelta(days=i);cutoff=on-timedelta(days=window_days-1)
            kept=[v for d,v in by_signed.items() if day(d)>=cutoff]
            count=sum(v['count'] for v in kept);points=sum(v['points'] for v in kept)
            rollout.append({'window_end':on.isoformat(),'count':count,'points':points,
                            'mean':points/count if count else None})
    return {'count':len(rows), 'points':total,
            'mean':float(Fraction(total,len(rows))) if rows else None,
            'stars':{str(i):stars[i] for i in range(1,6)},
            'loss_from_all_five':5*len(rows)-total,
            'products':len({r['product_id'] for r in rows}),
            'by_signed':dict(sorted(by_signed.items())),
            'known_rollout':rollout,
            'scope':'仅已知有效首次评价；未评价订单未来评价、追评及免计分变化未包含'}

def minimum_five(count, points, target, new_nonfive=None):
    target = number(target, 1, 5)
    count = integer(count); points = integer(points, 0, count*5)
    for star, amount in (new_nonfive or {}).items():
        star=integer(star,1,4); amount=integer(amount)
        count += amount; points += star*amount
    deficit = target*count-points
    if deficit <= 0: return 0
    if target == 5: return None
    return math.ceil(deficit/(5-target))

def check_gates(gates):
    normalized = {}
    for key in GATES:
        value = gates.get(key)
        if isinstance(value, dict): value = value.get('pass')
        if value is not None and not isinstance(value, bool):
            raise ValueError('准入条件必须为 true、false 或 null，不能用字符串代替')
        normalized[key] = value
    status = ('fail' if False in normalized.values() else
              'pass' if all(v is True for v in normalized.values()) else 'unknown')
    return {'status':status, 'items':normalized,
            'missing':[GATE_NAMES[k] for k,v in normalized.items() if v is None],
            'note':'分数达标不能替代其他准入条件；T+1仅为可能更新时间，不保证打标'}

def _history(config, first):
    h = config['history']
    if h['kind'] == 'daily':
        rows = h.get('days', [])
        values={}
        for r in rows:
            d=day(r['date'])
            if d >= first or d in values: raise ValueError('历史日期重复或与预测重叠')
            values[d] = None if r.get('score') is None else number(r['score'])
        # None must mean confirmed not scored. Unknown dates must not silently disappear.
        start=day(h.get('coverage_start', min(values) if values else first))
        expected=set(start+timedelta(days=i) for i in range((first-start).days))
        if expected != set(values): raise ValueError('逐日历史有缺失日期；明确补充未计分 null 或取得缺失日分')
        return h, values
    if h['kind'] != 'aggregate': raise ValueError('不支持的历史类型')
    count=integer(h['count'],1,365); number(h['mean'])
    start,end=day(h['first_date']),day(h['last_date'])
    if end >= first or start > end or count > (end-start).days+1:
        raise ValueError('历史日期、有效天数不一致')
    return h, None

def _retained(h, daily, on, window):
    cutoff=on-timedelta(days=window-1)
    if daily is not None:
        vals=[v for d,v in daily.items() if cutoff <= d <= on and v is not None]
        return sum(vals, Fraction(0)), len(vals)
    if day(h['last_date']) < cutoff: return Fraction(0),0
    if day(h['first_date']) < cutoff: return None,None
    return frac(h['mean'])*int(h['count']),int(h['count'])

def project(config):
    if not config.get('shop_key'): raise ValueError('必须指定店铺，避免串店')
    first=day(config['first_future_date'])
    window=integer(config.get('window_days',30),1,365)
    target=None if config.get('target') is None else number(config['target'])
    badge=config.get('objective')=='black_badge'
    if badge and (target is None or target < 83):
        raise ValueError('黑标规则为平均体验分≥83；用户目标不能低于准入门槛')
    lag=integer(config.get('badge_lag_days',1),0,30) if badge else 0
    requested=day(config['deadline']) if config.get('deadline') else None
    deadline=requested-timedelta(days=lag) if requested else first+timedelta(days=integer(config.get('horizon_days',60),1,365)-1)
    if deadline < first: raise ValueError('扣除打标等待后，已没有未来计分日；请检查日期口径')
    m=(deadline-first).days+1
    if m > 365: raise ValueError('第一版单次预测最多365天')
    h,daily=_history(config,first)
    hs,hn=_retained(h,daily,deadline,window)
    future_count=min(m,window)
    required=(target*(hn+future_count)-hs)/future_count if target is not None and hs is not None else None
    certainty='exact_arithmetic' if daily is not None and h.get('precision')=='exact' else 'conditional'
    plans=config.get('scenarios')
    if not plans:
        plans=[{'name':'数学上限','daily_score':100}]
        current=config.get('current_score')
        if current is not None:
            plans += [{'name':'当前日分延续','daily_score':current},
                      {'name':'延迟3天后达到数学上限','daily_score':100,'delay_days':3,'delay_score':current}]
        if required is not None and 0 <= required <= 100:
            plans += [{'name':'按期限倒推的恒定日分','daily_score':str(required)},
                      {'name':'向上取整敏感性','daily_score':math.ceil(required)}]
    if len(plans)>100: raise ValueError('情景数过多')
    results=[]
    for p in plans:
        score=number(p['daily_score']); delay=integer(p.get('delay_days',0),0,365)
        delay_score=number(p.get('delay_score',config.get('current_score',score)))
        trajectory=[]; future={}; crossed=None; missing=False
        for i in range(m):
            on=first+timedelta(days=i)
            v=delay_score if i < delay else score
            future[on]=v
            old_sum,old_n=_retained(h,daily,on,window)
            new=[x for d,x in future.items() if d >= on-timedelta(days=window-1)]
            mean=None if old_sum is None else (old_sum+sum(new,Fraction(0)))/(old_n+len(new))
            if mean is None: missing=True
            if crossed is None and not missing and mean is not None and target is not None and mean>=target:
                crossed=on
            trajectory.append({'date':on.isoformat(),'daily_score':float(v),'mean':public_number(mean),
                               'count':None if old_n is None else old_n+len(new)})
        final=trajectory[-1]['mean']
        results.append({'name':str(p['name']), 'daily_score':float(score),'delay_days':delay,
            'final_mean':final,'meets_target':None if target is None or mean is None else mean>=target,
            'first_target_date':crossed.isoformat() if crossed else None,
            'earliest_badge_date':(crossed+timedelta(days=lag)).isoformat() if badge and crossed else None,
            'status':'insufficient_history' if missing else 'conditional' if certainty=='conditional' else 'calculated',
            'trajectory':trajectory})
    return {'target':public_number(target),'objective':config.get('objective','average_score'),
        'requested_deadline':requested.isoformat() if requested else None,
        'score_deadline':deadline.isoformat(),'future_days':m,
        'required_future_average':public_number(required),
        'required_future_average_exact':str(required) if required is not None else None,
        'constant_plan_feasibility':('unknown' if required is None else 'impossible_above_100' if required>100 else 'within_score_range'),
        'certainty':certainty,'scenarios':results,
        'assumptions':config.get('assumptions',[])+[
            '未来日分均为情景条件，不代表已找到可实现这些日分的运营动作或好评数量。',
            '日分滚动均值与商品评价签收窗口是两个不同的窗口。',
            '预测计分日期与后台更新日期须核对；打标等待只是假设最快时间，不是承诺。']+
            (['历史整数均值及有效天数按明确假设代入；不能据此保证精确日期。'] if certainty=='conditional' else [])}

def read_table(path):
    path=Path(path)
    if path.stat().st_size>MAX_FILE_BYTES: raise ValueError('文件超过40MB上限')
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f); rows=[]
            for r in reader:
                if len(rows)>=MAX_ROWS: raise ValueError('文件超过行数上限')
                rows.append(r)
            return rows
    if path.suffix.lower()!='.xlsx': raise ValueError('第一版支持 .xlsx 和 UTF-8 CSV；不执行宏')
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist())>250*1024*1024: raise ValueError('解压后文件过大')
    try:
        import defusedxml  # noqa: F401 -- enable hardened XML parsing in openpyxl
        import openpyxl
    except ImportError as e:
        raise ValueError('缺少表格依赖，请先运行安装向导') from e
    w=openpyxl.load_workbook(path,read_only=True,data_only=True,keep_links=False)
    try:
        s=w.active;s.reset_dimensions()  # Some Douyin exports declare an incorrect sheet dimension.
        it=iter(s.values); headers=None
        for _ in range(20):
            row=next(it,None)
            if row is None: break
            labels=[str(x).strip() if x is not None else '' for x in row]
            if any(x in labels for x in ('订单ID','客服ID','评分日期','日期')):
                headers=labels;break
        if headers is None: raise ValueError('未识别表头，不能猜字段')
        rows=[]
        for row in it:
            if not any(x is not None for x in row): continue
            if len(rows)>=MAX_ROWS: raise ValueError('文件超过行数上限')
            rows.append({k:v for k,v in zip(headers,row) if k})
        return rows
    finally: w.close()

def _identifier(value):
    if value is None or str(value).strip()=='': raise ValueError('缺少订单或商品标识')
    if isinstance(value,float) or isinstance(value,int) and abs(value)>2**53:
        raise ValueError('长ID以数值形式保存，可能已丢精度；请使用后台原始文本ID导出')
    return str(value).strip()

def load_exports(paths,shop_key,as_of=None):
    reviews=[];quality={}; service=[];sources=[];kinds=[]
    for path in paths:
        path=Path(path); before=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=read_table(path)
        fields=set(rows[0]) if rows else set()
        kind='unknown'
        if {'订单ID','商品ID','商品评分','签收时间','评价时间'} <= fields:
            kind='reviews'
            for r in rows:
                reviews.append({'shop_key':shop_key,'order_id':_identifier(r['订单ID']),
                    'product_id':_identifier(r['商品ID']),'star':r['商品评分'],
                    'signed':r['签收时间'],'reviewed':r['评价时间']})
        elif {'订单ID','品退原因'} <= fields:
            kind='quality'
            for r in rows:
                key=_identifier(r['订单ID'])
                quality[key]=str(r['品退原因'])
        elif {'客服ID','不满意率','点评会话总数'} <= fields:
            kind='service'
            # These rows are staff aggregates, not unique sessions. Never add as shop metrics.
            service.append({'rows':len(rows),'staff_rated_sum':sum(integer(r['点评会话总数']) for r in rows)})
        elif not rows:
            kind='empty'
        else: raise ValueError('未知报表字段，不能自动混入计算')
        if before!=hashlib.sha256(path.read_bytes()).hexdigest(): raise ValueError('输入文件在读取期间发生变化')
        sources.append({'filename':path.name,'sha256':before,'rows':len(rows),'kind':kind})
        kinds.append(kind)
    return {'reviews':review_summary(reviews,as_of) if reviews else None,
            'quality':{'orders':len(quality),'reasons':dict(Counter(quality.values()))} if 'quality' in kinds else None,
            'service_staff_exports':service,'sources':sources,
            'warnings':(['客服按员工汇总存在重复归属可能，不能当作全店去重会话指标。'] if service else [])}

def report(config,exports=None):
    exports=exports or {}
    projection=project(config) if config.get('history') else None
    missing=[]
    if projection is None: missing.append('历史每日体验分或带有效天数/日期的均值；无法倒推平均体验分')
    if not exports.get('reviews'): missing.append('有效首次商品评价明细；无法复算商品星分')
    if projection and projection['certainty']=='conditional': missing.append('历史日分精确值、有效计分天数及均值取整口径仍需核实')
    snapshot=config.get('snapshot',{})
    mismatch=None
    if exports.get('reviews') and exports['reviews']['mean'] is not None and snapshot.get('product_rating') is not None:
        mismatch=abs(exports['reviews']['mean']-float(snapshot['product_rating']))>0.00006
        if mismatch: missing.append('评价导出与后台指标不一致，请核对统计窗口、更新时点及有效评价范围')
    out={'schema':'douyin-score-report/v1','version':VERSION,'shop_key':config['shop_key'],
         'goal_description':config.get('goal_description',''), 'snapshot':snapshot,
         'projection':projection,'exports':exports,'eligibility':check_gates(config.get('gates',{})),
         'missing_data':missing,'rating_reconciliation_mismatch':mismatch,
         'data_cutoff':config.get('data_cutoff'),'rule_sources':config.get('rule_sources',[]),
         'generated_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
         'limit':'缺少指标到行业得分映射，不能把好评数量换算成保证达标的体验分。'}
    staff=exports.get('service_staff_exports',[])
    if len(staff)==1 and snapshot.get('service_rated') is not None:
        out['service_reconciliation']={'staff_rated_sum':staff[0]['staff_rated_sum'],
            'shop_rated':snapshot['service_rated'],
            'mismatch':staff[0]['staff_rated_sum']!=snapshot['service_rated'],
            'note':'员工归属汇总与店铺去重口径不同；未经会话级去重不合并'}
    if all(k in snapshot for k in ('product_score','service_score','product_weight','service_weight','current_score')):
        weighted=frac(snapshot['product_score'])*frac(snapshot['product_weight'])+frac(snapshot['service_score'])*frac(snapshot['service_weight'])
        out['component_reconciliation']={'shown_weighted_sum':float(weighted),
            'backend_total':snapshot['current_score'],
            'difference':float(frac(snapshot['current_score'])-weighted),
            'note':'未包含未提供的加减分；内部精度/取整未知，不自行补造修正公式'}
    if config.get('review_target') is not None and exports.get('reviews'):
        r=exports['reviews'];out['explicit_review_target']={'target':config['review_target'],
        'minimum_additional_five':minimum_five(r['count'],r['points'],config['review_target'],config.get('new_nonfive')),
        'assumption':'仅限用户明确指定商品星分目标；已知旧评价不变、所有新增评价有效；不等于黑标方案'}
    if config.get('previous_report'):
        prev=json.loads(Path(config['previous_report']).read_text(encoding='utf-8'))
        if prev.get('shop_key')!=config['shop_key']: raise ValueError('上期报告属于另一家店铺')
        p=prev.get('snapshot',{});out['change_since_previous']={}
        for k,v in snapshot.items():
            if isinstance(v,(float,int)) and not isinstance(v,bool) and isinstance(p.get(k),(float,int)):
                out['change_since_previous'][k]=float(frac(v)-frac(p[k]))
    return out

def markdown(r):
    lines=['# 店铺体验分析', '',f"目标：{r.get('goal_description') or '按本次参数分析'}",'',
           f"数据截止：{r.get('data_cutoff') or '未提供，需核对'}",'']
    labels={'current_score':'当前日分','product_score':'商品体验分','service_score':'服务体验分',
            'product_rating':'商品平均星分','mean_7d_display':'近7天展示均分',
            'mean_14d_display':'近14天展示均分','mean_30d_display':'近30天展示均分'}
    if r.get('snapshot'):
        lines += ['| 后台指标 | 当前值 |','|---|---:|']
        for k,label in labels.items():
            if k in r['snapshot']: lines.append(f"| {label} | {r['snapshot'][k]} |")
        lines += ['']
    p=r.get('projection')
    if p:
        req=p['required_future_average']
        target_label=p['target'] if p['target'] is not None else '未指定，本次比较期末分数'
        lines += [f"目标平均分：{target_label}；计算截止：{p['score_deadline']}；新增计分日：{p['future_days']}。",'',
            f"未来所需恒定平均日分：{req:.6f}。" if req is not None else '历史不足或未设分数目标，无法倒推所需日分。',
            '公式：(目标分×目标窗口有效日数−目标窗口保留历史分之和)÷窗口内未来有效日数。','',
            '| 情景 | 期末平均 | 首次越过目标 | 最快打标机会* | 状态 |',
            '|---|---:|---|---|---|']
        for s in p['scenarios']:
            val='未知' if s['final_mean'] is None else f"{s['final_mean']:.4f}"
            status={'conditional':'条件估算','calculated':'给定条件下的算术结果','insufficient_history':'历史不足'}[s['status']]
            cross=s['first_target_date'] or ('不能判断' if s['status']=='insufficient_history' else '范围内未达到' if p['target'] is not None else '未设目标')
            lines.append(f"| {s['name']} | {val} | {cross} | {s['earliest_badge_date'] or '—'} | {status} |")
        lines += ['','*仅分数条件下的时间估计；其他条件必须同时满足，平台不保证次日打标。','',
                  '计算条件：']+['- '+x for x in p['assumptions']]+['']
    e=r.get('exports',{});v=e.get('reviews')
    if v:
        avg='无计分评价，不能计算平均星分' if v['mean'] is None else f"平均{v['mean']:.6f}"
        lines += [f"已知有效评价：{v['count']}条，星级总分{v['points']}，{avg}。",'']
    if r.get('service_reconciliation'):
        x=r['service_reconciliation'];lines += [f"客服口径：员工汇总{x['staff_rated_sum']}个点评会话，店铺口径{x['shop_rated']}个。{x['note']}。",'']
    if r.get('component_reconciliation'):
        x=r['component_reconciliation'];lines += [f"分项核对：显示分直接加权{x['shown_weighted_sum']}，后台总分{x['backend_total']}。{x['note']}。",'']
    lines += ['准入检查：'+{'fail':'尚未满足','pass':'所提供证据显示各项满足，仍需平台确认','unknown':'资料不足，不能确认满足'}[r['eligibility']['status']],'']
    for k,v in r['eligibility']['items'].items():
        lines.append(f"- {GATE_NAMES[k]}："+('符合' if v is True else '不符合' if v is False else '待核实'))
    if r.get('change_since_previous'):
        lines += ['', '与上次快照变化：']
        for k,label in labels.items():
            value=r['change_since_previous'].get(k)
            if value is not None: lines.append(f"- {label}：{value:+.4f}")
    lines += ['','缺失依据：']+['- '+x for x in r['missing_data']+e.get('warnings',[])]+['',r['limit'],'',
        '本程序仅分析本地文件；后台操作由独立的只读取数流程执行。']
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description='抖店只读数据分析；配置由 Skill 根据用户描述整理')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('analyze');a.add_argument('--config',required=True);a.add_argument('--file',action='append',default=[])
    a.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        config=json.loads(Path(args.config).read_text(encoding='utf-8'))
        exports=load_exports(args.file,config['shop_key'],config.get('review_window_end'))
        r=report(config,exports);out=Path(args.out)
        if out.suffix.lower()!='.json': raise ValueError('报告路径须为 .json')
        md=out.with_suffix('.md')
        if out.exists() or md.exists(): raise ValueError('报告已存在；请使用新的日期/批次文件名，避免覆盖')
        write_json(out,r);md.write_text(markdown(r),encoding='utf-8')
        print(json.dumps({'report':str(out),'readable_report':str(md),'missing_data':r['missing_data']},ensure_ascii=False))
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:
        print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False),file=sys.stderr);return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
