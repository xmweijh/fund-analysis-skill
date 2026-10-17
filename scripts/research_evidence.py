"""把已有产品缓存接入研究报告；不发起网络请求，不以缺失值造数据。"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re


def current_team_tenure(info, detail, code, as_of, source):
    """现任名单与该份额任职记录全部匹配后，取当前团队共同任职时长。"""
    names=set(filter(None,re.split(r'[\s、,，;/]+',info.get('manager_name') or '')))
    managers=detail.get('manager_list',[])
    if not names or not managers: return None
    current=[m for m in managers if m.get('name') in names]
    if len(current)!=len(names) or {m.get('name') for m in current}!=names: return None
    starts={}
    for manager in current:
        matching={r.get('post_date') for r in manager.get('achievement_list',[]) if r.get('fund_code')==code}
        if len(matching)!=1: return None
        try: start=date.fromisoformat(matching.pop())
        except (TypeError,ValueError): return None
        if start>date.fromisoformat(as_of): return None
        starts[manager['name']]=start.isoformat()
    days=(date.fromisoformat(as_of)-max(date.fromisoformat(d) for d in starts.values())).days
    return dict(value=round(days/365.25,6),as_of=as_of,source=source,verified=False,
                team_complete=True,member_start_dates=starts,
                note='现任名单与相同基金代码逐一匹配；团队共同任期取最晚到任日，不取从业年限')


def enrich_document(document, public_data_dir):
    """保留手工证据优先级，补接缓存任期，并恢复不参与新分数的原有业绩展示。"""
    document=deepcopy(document)
    for fund in document['funds']:
        code=fund.get('code')
        if not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code):continue
        path=Path(public_data_dir)/(code+'.json')
        if not path.exists():continue
        cached=json.loads(path.read_text(encoding='utf-8'))
        sources=cached.get('sources',{})
        def data(key):return sources.get(key,{}).get('payload',{}).get('data',{}) or {}
        info,detail,achievement,growth=[data(key) for key in ('info','detail','achievement','growth_3y')]
        if not all(isinstance(x,dict) for x in (info,detail,achievement,growth)):continue
        as_of=cached.get('retrieved_at','')[:10]
        try:date.fromisoformat(as_of)
        except ValueError:as_of=document['as_of']
        team=current_team_tenure(info,detail,code,as_of,sources.get('detail',{}).get('url',''))
        if team is not None:
            fund.setdefault('metrics',{}).setdefault('manager_tenure_years',team)
        context=fund.setdefault('context',{})
        context.setdefault('manager_name',info.get('manager_name'))
        context.setdefault('fund_type',info.get('type_desc'))
        context.setdefault('founded_date',info.get('found_date'))
        context.setdefault('nav_date',info.get('fund_derived',{}).get('end_date'))
        context.setdefault('retrieved_at',cached.get('retrieved_at'))
        context.setdefault('source',sources.get('achievement',{}).get('url'))
        performance=[]
        for item in achievement.get('stage_performance_list',[]):
            performance.append({key:item.get(key) for key in ('period_time','self_nav','self_max_draw_down','self_nav_rank')})
        context.setdefault('stage_performance',performance)
        context.setdefault('benchmark_description',growth.get('performance_remark'))
        explanations=fund.setdefault('missing_explanations',{})
        for key,reason in {
            'lower_credit_pct':'需定期报告完整信用分布；当前缓存尚未采集，不是信用风险为零',
            'duration_years':'当前基础接口没有修正久期，需补充定期报告或专门数据源',
            'convertible_pct':'当前仅有部分重仓债券，不足以推算全部转债/交换债比例',
            'benchmark_excess_3y_pct':'尚未取得同币种、分段基准和复权总回报的完整三年对齐数据',
            'tracking_error_1y_pct':'尚未接入真实日频标的指数与基金总回报；不能用抽样走势替代',
            'valuation_percentile':'准确标的估值历史尚未完整接入；旧版涨跌/排名近似不是实际估值',
            'top10_equity_pct':'ETF穿透、完整前十股票或股票资产分母仍缺证据',
            'equity_pct':'平台未提供明确股票净值比例，不能因无股票行自动填零',
            'gross_assets_ratio':'当前产品详情缺总资产/净资产金额，不能用债券仓位代替',
        }.items():explanations.setdefault(key,reason)
        gaps=context.setdefault('data_gaps',[])
        if not team:gaps.append('缓存未能完整匹配现任团队与本份额任职日期，保留任期缺口')
        founded=info.get('found_date')
        if founded:
            try:
                if (date.fromisoformat(document['as_of'])-date.fromisoformat(founded)).days<1095:
                    gaps.append('本份额成立不足三年；三年超额回报不能补造，已有短期业绩另列展示')
                    explanations['benchmark_excess_3y_pct']='本份额成立不足三年，达不到本模型三年要求；不是基础行情获取失败'
            except ValueError:pass
        gaps.append('新分数偏风险/成本，与旧技术/基本面/估值/资金/情绪分口径不同；阶段收益不冒充估值')
        context['data_gaps']=list(dict.fromkeys(gaps))
    return document
