"""按用户明确的分组/目标核对本地市值；不选基金、不推断风险承受能力、不执行交易。"""
import argparse
from collections import defaultdict
from datetime import date
import json
import math
import re
from pathlib import Path
from html import escape


def finite_nonnegative(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and value>=0


def diagnose(document):
    funds=document['funds'];date.fromisoformat(document['as_of'])
    policy=document.get('investment_policy') or {}
    if not isinstance(policy,dict):raise ValueError('investment_policy须为对象')
    groups=defaultdict(float);dates=set();currencies=set();unknown=[];unclassified=[];excluded=[]
    total=0;included=0;known=0;problems=[];seen=set();identities=defaultdict(list)
    for i,fund in enumerate(funds):
        code=fund.get('code');key=code or f'unknown-{i}'
        if code is not None:
            if not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code):raise ValueError('基金代码须为六位ASCII数字或未知')
            if code in seen:raise ValueError('代码重复，不能重复计权')
            seen.add(code)
        # 应急/专项资金等只按用户显式配置从再平衡分母排除，不按产品名称猜用途。
        if fund.get('exclude_from_allocation') is True:
            excluded.append(key);continue
        included+=1;value=fund.get('market_value')
        if value is None:unknown.append(key);continue
        if not finite_nonnegative(value):raise ValueError('市值须为有限非负数或未知')
        total+=value;known+=1
        when=fund.get('market_value_as_of') or document.get('holdings_as_of')
        try:
            if not isinstance(when,str) or date.fromisoformat(when)>date.fromisoformat(document['as_of']):raise ValueError()
            dates.add(when)
        except (ValueError,TypeError):problems.append('市值日期缺失、无效或晚于研究日')
        currency=fund.get('currency') or document.get('base_currency')
        if not isinstance(currency,str) or not currency.strip():problems.append('市值币种未核实')
        else:currencies.add(currency)
        group=fund.get('allocation_group')
        if not isinstance(group,str) or not group.strip():unclassified.append(key);group='未分类'
        groups[group]+=value
        underlying=fund.get('underlying_id')
        if isinstance(underlying,str) and underlying.strip() and fund.get('underlying_verified') is True:identities[underlying].append(key)
    if not included:problems.append('没有纳入配置核对的条目')
    if unknown:problems.append('部分纳入条目的市值未知，分母不完整')
    if len(dates)>1:problems.append('市值日期不一致，不能生成目标差额')
    if len(currencies)>1:problems.append('币种未换算到同一基准，不能合计市值或权重')
    if unclassified:problems.append('部分产品配置分组未确认')
    # 混合币种金额连“已知合计”也不展示为可加总值。
    comparable=len(currencies)<=1 and not any('币种' in p for p in problems)
    rows=[{'group':g,'known_value':round(v,2) if comparable else None,
           'known_value_weight_pct':v/total*100 if comparable and total>0 else None}
          for g,v in sorted(groups.items())]
    targets=policy.get('target_allocations_pct')
    drift=[];ready=False
    if targets is not None:
        if not isinstance(targets,dict) or not targets or any(not isinstance(k,str) or not k.strip() or not finite_nonnegative(v) for k,v in targets.items()):
            raise ValueError('目标配置须为非空分组到非负比例的对象')
        if abs(sum(targets.values())-100)>1e-6:raise ValueError('目标配置比例之和须为100%')
        if policy.get('targets_confirmed') is not True:problems.append('目标比例尚未由用户确认')
        if not isinstance(policy.get('source'),str) or not policy['source'].strip():problems.append('目标配置缺少用户决定来源')
        if any(g not in targets for g in groups):problems.append('现有分组未完整映射到目标配置，不默认目标为零')
        ready=not problems and total>0
        if ready:
            for group,target in targets.items():
                current=groups.get(group,0);target_value=total*target/100
                drift.append({'group':group,'current_weight_pct':current/total*100,'target_weight_pct':target,
                              'drift_pct_points':current/total*100-target,'difference_to_target_value':round(target_value-current,2)})
    else:problems.append('未设置已确认目标比例，提供结构核对，不生成配置金额建议')
    return {'as_of':document['as_of'],'status':'可核对目标偏离' if ready else '仅结构核对',
            'known_included_value':round(total,2) if comparable and known else None,
            'denominator_complete':not unknown and included>0 and comparable and len(dates)==1 and not any('市值日期' in p for p in problems),
            'valuation_dates':sorted(dates),'currencies':sorted(currencies),'excluded_entries':excluded,
            'unknown_value_entries':unknown,'unclassified_entries':unclassified,'allocation':rows,'target_drift':drift,
            'shared_underlying':[{'underlying_id':k,'codes':v} for k,v in identities.items() if len(v)>1],
            'limitations':list(dict.fromkeys(problems))+['配置按已声明产品分组，不等于底层资产穿透；同标的提示仅来自已核实的underlying_id',
                '目标差额是静态核对，不是买卖指令；还须考虑新增现金、费用、持有期、额度与结算'],
            'trade_orders':None}


def render_management(document):
    if 'investment_policy' not in document and document.get('management_review') is not True:return ''
    result=diagnose(document);rows=[]
    for item in result['allocation']:
        value='待核币种' if item['known_value'] is None else f"{item['known_value']:,.2f}"
        weight='未知' if item['known_value_weight_pct'] is None else f"{item['known_value_weight_pct']:.1f}%"
        rows.append(f'<tr><td>{escape(item["group"])}</td><td>{value}</td><td>{weight}</td></tr>')
    drift=''
    if result['target_drift']:
        drift='<h3>与已确认目标的静态差额</h3><ul>'+''.join(
            f'<li>{escape(item["group"])}：偏离{item["drift_pct_points"]:+.1f}个百分点；目标金额差{item["difference_to_target_value"]:+,.2f}</li>'
            for item in result['target_drift'])+'</ul>'
    return '<section class="panel"><h2>组合管理核对</h2><p>'+escape(result['status'])+'</p><div class="scroll"><table><thead><tr><th>已声明分组</th><th>已知市值</th><th>已知市值中占比</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'+drift+'<ul>'+''.join('<li>'+escape(v)+'</li>' for v in result['limitations'])+'</ul></section>'


def main():
    parser=argparse.ArgumentParser(description='本地配置与用户目标核对，不生成交易指令')
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=diagnose(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(path.resolve())


if __name__=='__main__':main()
