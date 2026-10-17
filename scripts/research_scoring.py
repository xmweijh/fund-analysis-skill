"""分类型研究参考评分。规则启发式，未作收益预测或样本外有效性验证。"""
from datetime import date
import math

MODEL_VERSION = 'research-v1.0'
LABELS = {
    'bond': '非权益债券', 'enhanced_bond': '增强债券',
    'mixed_allocation': '偏债/配置混合', 'active_equity': '主动权益',
    'index': '股票指数/ETF联接', 'money': '货币基金',
}
# 权重是可审查的研究选择，不是拟合出来的最优参数。
WEIGHTS = {
    'bond': {'drawdown_1y_pct':25, 'annual_fee_pct':15, 'lower_credit_pct':20,
             'duration_years':15, 'gross_assets_ratio':15, 'convertible_pct':10},
    'enhanced_bond': {'drawdown_1y_pct':20, 'annual_fee_pct':15, 'lower_credit_pct':15,
             'duration_years':10, 'gross_assets_ratio':10, 'convertible_pct':10,
             'equity_pct':10, 'benchmark_excess_3y_pct':10},
    'mixed_allocation': {'drawdown_1y_pct':25, 'annual_fee_pct':15, 'lower_credit_pct':15,
             'duration_years':10, 'gross_assets_ratio':15, 'equity_pct':10, 'convertible_pct':10},
    'active_equity': {'drawdown_1y_pct':30, 'annual_fee_pct':15, 'top10_equity_pct':15,
             'manager_tenure_years':15, 'benchmark_excess_3y_pct':25},
    'index': {'drawdown_1y_pct':20, 'annual_fee_pct':20, 'top10_equity_pct':10,
             'tracking_error_1y_pct':25, 'valuation_percentile':25},
    'money': {'drawdown_1y_pct':20, 'annual_fee_pct':20, 'lower_credit_pct':30,
             'redemption_business_days':30},
}
METRICS = {
    'drawdown_1y_pct': ('近一年最大回撤', '%', 0, 100, 45),
    'annual_fee_pct': ('名义年度运作费率', '%/年', 0, 20, 365),
    'lower_credit_pct': ('低于AA+及未评级信用债占净值', '%', 0, 1000, 180),
    'duration_years': ('修正久期', '年', 0, 50, 180),
    'gross_assets_ratio': ('总资产/净资产', '倍', 0, 10, 180),
    'convertible_pct': ('转债/交换债占净值', '%', 0, 1000, 180),
    'equity_pct': ('股票占净值', '%', 0, 1000, 180),
    'top10_equity_pct': ('前十股票占股票资产', '%', 0, 100, 180),
    'manager_tenure_years': ('现任团队共同连续任职', '年', 0, 80, 365),
    'benchmark_excess_3y_pct': ('三年累计超额总回报', '个百分点', -1000, 1000, 45),
    'tracking_error_1y_pct': ('一年日频总回报跟踪误差', '%/年', 0, 100, 45),
    'valuation_percentile': ('准确标的估值历史百分位', '%', 0, 100, 45),
    'redemption_business_days': ('常规赎回到账工作日', '工作日', 0, 100, 365),
}

def interpolate(value, knots):
    """显式节点间线性插值，端点外截断。"""
    if value <= knots[0][0]: return float(knots[0][1])
    for (x0,y0),(x1,y1) in zip(knots,knots[1:]):
        if value <= x1: return y0+(y1-y0)*(value-x0)/(x1-x0)
    return float(knots[-1][1])

def json_safe(value):
    """非法非有限输入在证据输出保留为空，避免缺失数据使报告序列化失败。"""
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list): return [json_safe(v) for v in value]
    return value

def knots_for(metric, profile):
    defensive = profile in ('bond','money')
    balanced = profile in ('enhanced_bond','mixed_allocation')
    if metric=='drawdown_1y_pct':
        if defensive: return [(0,100),(.3,85),(1,60),(3,20),(5,0)]
        if balanced: return [(0,100),(3,85),(8,60),(15,20),(25,0)]
        return [(0,100),(10,85),(20,60),(35,25),(50,0)]
    if metric=='annual_fee_pct':
        if defensive: return [(0,100),(.15,95),(.3,70),(.6,30),(1,0)]
        if profile=='index': return [(0,100),(.2,95),(.6,70),(1.2,30),(2,0)]
        return [(0,100),(.6,90),(1.4,60),(2,25),(3,0)]
    return {
        'lower_credit_pct': [(0,100),(5,85),(20,50),(50,0)],
        'duration_years': [(0,100),(1,95),(3,70),(5,40),(10,0)],
        'gross_assets_ratio': [(1,100),(1.1,85),(1.3,45),(1.4,20),(2,0)],
        'convertible_pct': [(0,100),(5,85),(20,40),(40,0)],
        'equity_pct': [(0,100),(10,85),(20,60),(40,20),(60,0)],
        'top10_equity_pct': [(0,100),(30,90),(50,70),(80,20),(100,0)],
        'manager_tenure_years': [(0,0),(1,30),(3,70),(5,90),(8,100)],
        'benchmark_excess_3y_pct': [(-20,0),(-10,25),(0,50),(10,75),(20,100)],
        'tracking_error_1y_pct': [(0,100),(.5,90),(1,70),(2,40),(5,0)],
        'valuation_percentile': [(0,100),(100,0)],
        'redemption_business_days': [(0,100),(1,95),(3,75),(7,40),(15,0)],
    }[metric]

def validate_evidence(metric, evidence, as_of):
    """无来源、失效日期、不匹配口径不能伪装成可用证据。"""
    if not isinstance(evidence,dict): return '未提供数据'
    value=evidence.get('value')
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        return '缺失或非有限数值'
    _,_,lower,upper,max_age=METRICS[metric]
    if not lower<=value<=upper: return '数值超出允许范围'
    if metric=='gross_assets_ratio' and value<1: return '总资产/净资产不能小于1'
    for key in ('period_days','observations','history_years'):
        if key in evidence and (isinstance(evidence[key],bool) or not isinstance(evidence[key],(int,float))
                or not math.isfinite(evidence[key]) or evidence[key]<0):
            return f'{key}必须是有限非负数'
    if not isinstance(evidence.get('source'),str) or not evidence['source'].strip(): return '缺少来源'
    try: age=(as_of-date.fromisoformat(evidence['as_of'])).days
    except (ValueError,TypeError,KeyError): return '缺少有效数据日期'
    if age<0: return '数据日期晚于分析日期'
    if age>max_age: return f'数据过期（{age}天，阈值{max_age}天）'
    if metric in ('lower_credit_pct','convertible_pct','equity_pct') and evidence.get('basis')!='net_assets':
        return '需核实占净资产口径'
    if metric=='drawdown_1y_pct' and evidence.get('period_days',0)<365: return '不足完整一年回撤样本'
    if metric=='manager_tenure_years' and evidence.get('team_complete') is not True: return '团队任期未完整核实'
    if metric=='top10_equity_pct':
        if evidence.get('basis')!='equity_assets' or evidence.get('complete') is not True:
            return '需完整前十及股票资产分母；ETF联接需穿透'
    if metric in ('benchmark_excess_3y_pct','tracking_error_1y_pct'):
        for key in ('benchmark_verified','dates_aligned','currency_matched','total_return'):
            if evidence.get(key) is not True: return '合同基准/日期/币种/总回报口径未核实'
        needed=1095 if metric=='benchmark_excess_3y_pct' else 365
        if evidence.get('period_days',0)<needed: return '完整比较区间不足'
        if metric=='tracking_error_1y_pct' and (evidence.get('frequency')!='daily' or evidence.get('observations',0)<200):
            return '跟踪误差需足够的真实日频样本'
    if metric=='valuation_percentile':
        if evidence.get('target_verified') is not True or evidence.get('history_years',0)<5:
            return '需准确指数身份及至少五年估值历史'
    return None

def score_fund(fund, as_of):
    """按可用权重归一化；区间来自缺失维度0–100，不是统计置信区间。"""
    as_of=date.fromisoformat(as_of)
    profile=fund.get('profile')
    if not isinstance(profile,str) or profile not in WEIGHTS: raise ValueError(f'需要明确支持的研究类型: {profile!r}')
    metrics=fund.get('metrics',{})
    if not isinstance(metrics,dict): raise ValueError('metrics必须是对象')
    dimensions=[];weight=0;weighted=0;reported=0
    for key,w in WEIGHTS[profile].items():
        evidence=metrics.get(key)
        reason=validate_evidence(key,evidence,as_of)
        if reason=='未提供数据':
            explanation=fund.get('missing_explanations',{}).get(key)
            if isinstance(explanation,str) and explanation.strip():reason=explanation
        score=None if reason else interpolate(evidence['value'],knots_for(key,profile))
        if score is not None:
            weight+=w;weighted+=w*score/100
            if evidence.get('verified') is not True: reported+=w
        dimensions.append({'key':key,'label':METRICS[key][0],'unit':METRICS[key][1],
             'weight_pct':w,'score':None if score is None else round(score,1),
             'evidence':json_safe(evidence),'missing_reason':reason,'knots':knots_for(key,profile)})
    flags=list(fund.get('flags',[]))
    if fund.get('qdii'):
        flags.append('QDII需另核汇率暴露、海外日历、限购及实际到账；当前参考分未覆盖这些风险')
    if reported: flags.append(f'{reported}%模型权重使用未独立核验的披露/平台数据')
    flags.append('规则阈值未经收益预测或样本外回测验证；只在相同研究类型、相同证据集内比较')
    return {'model_version':MODEL_VERSION,'code':fund.get('code'),'name':fund.get('name'),
        'profile':profile,'profile_label':LABELS[profile],'as_of':as_of.isoformat(),
        'reference_score':round(weighted*100/weight,1) if weight else None,
        'coverage_pct':weight,'verified_coverage_pct':weight-reported,
        'missing_weight_range':[round(weighted,1),round(weighted+100-weight,1)],
        'status':'无可评分数据' if not weight else '局部参考' if weight<50 else '暂定参考' if weight<80 else '较完整参考',
        'dimensions':dimensions,'flags':flags,'context':json_safe(fund.get('context',{})),
        'position_advice':None,'return_forecast':None}

def score_document(document):
    """组合保留每个输入条目；不把不同类型参考分平均成组合风险等级。"""
    as_of=document['as_of']
    date.fromisoformat(as_of)
    rows=document['funds']
    for row in rows:
        code=row.get('code')
        if code is not None and (not isinstance(code,str) or len(code)!=6 or not code.isascii() or not code.isdigit()):
            raise ValueError('基金代码必须为六位ASCII数字或null')
    codes=[row.get('code') for row in rows if row.get('code') is not None]
    if len(codes)!=len(set(codes)): raise ValueError('基金代码重复，不能重复计权')
    results=[];value_total=0;value_scored=0;known=0;weighted_coverage=0
    for row in rows:
        value=row.get('market_value')
        if value is not None:
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('市值必须是有限非负数或null')
            known+=1;value_total+=value
        try: result=score_fund(row,as_of)
        except ValueError as exc:
            result={'code':row.get('code'),'name':row.get('name'),'profile':row.get('profile'),
                'reference_score':None,'coverage_pct':0,'verified_coverage_pct':0,'missing_weight_range':[0,100],
                'status':'类型待核实','dimensions':[],'flags':[str(exc)],'position_advice':None,'return_forecast':None}
        result['market_value']=value
        if value is not None:
            if result['reference_score'] is not None:value_scored+=value
            weighted_coverage+=value*result['coverage_pct']/100
        results.append(result)
    return {'model_version':MODEL_VERSION,'as_of':as_of,'funds':results,
        'summary':{'entry_count':len(rows),'scored_count':sum(r['reference_score'] is not None for r in results),
           'known_market_value':round(value_total,2) if known else None,'all_values_known':known==len(rows),
           'scored_value_share_pct':100*value_scored/value_total if value_total else None,
           'evidence_weighted_value_coverage_pct':100*weighted_coverage/value_total if value_total else None,
           'aggregate_score':None,'note':'不同类型和证据集的分数不直接排名或平均；覆盖率分母仅为已知市值，不代表回撤约束。'}}
