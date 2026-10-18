"""单文件操作研究报告：整合组合判断、条件方案、逐项操作、评分和证据。"""
import argparse
from datetime import date
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.research_scoring import json_safe, score_document


def esc(value): return html.escape(str(value),quote=True)
def number(value,digits=2): return '未知' if value is None else f'{value:,.{digits}f}'
def items(values): return '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in values)+'</ul>'
def link(source):
    if isinstance(source,str) and urlsplit(source).scheme in ('https','http'):
        return f'<a href="{esc(source)}" rel="noreferrer">公开来源 ↗</a>'
    return esc(source or '未提供')


def normalize_action(fund):
    """操作判断由研究证据显式提供，不能由参考分或浮亏自动推导。"""
    supplied=fund.get('operation_analysis') or {}
    if not isinstance(supplied,dict):raise ValueError('operation_analysis必须是对象')
    return {
        'stance':supplied.get('stance') or '观察，先核用途',
        'priority':supplied.get('priority') or '待核',
        'role':supplied.get('role') or '用途待确认',
        'reasons':supplied.get('reasons') or ['尚无组合用途、风险重叠和个人交易条件证据；参考分不单独触发交易。'],
        'next_step':supplied.get('next_step') or '先确认资金用途、个人可赎日期、费用及该基金在组合中的独立作用。',
        'add_condition':supplied.get('add_condition') or '用途与目标比例明确、组合风险可接受、交易条件核实后，再讨论新增。',
        'reduce_condition':supplied.get('reduce_condition') or '出现用途不符、重复风险过大或承受能力变化时，再评估降低；不只看浮亏或分数。',
        'cost_checks':supplied.get('cost_checks') or ['个人确认日、实际赎回费及到账日未知，尚不具备下单所需信息。'],
        'alternative':supplied.get('alternative') or '可先保持现状、补齐交易条件，避免为了操作而操作。',
    }


def nav_chart(history):
    """按实际日期绘制抽样单位净值，仅作展示，不计算日频技术信号。"""
    clean=[]
    for point in history or []:
        try:
            d=date.fromisoformat(point['date']);value=float(point['nav'])
            if value>0 and value<float('inf'):clean.append((d,value))
        except (ValueError,TypeError,KeyError):continue
    clean=sorted(dict(clean).items())
    if len(clean)<2:return ''
    lo=min(v for _,v in clean);hi=max(v for _,v in clean);span=(clean[-1][0]-clean[0][0]).days
    if not span:return ''
    coords=' '.join(f'{12+(d-clean[0][0]).days/span*776:.1f},{115-(v-lo)/(hi-lo or 1)*95:.1f}' for d,v in clean)
    return f'<figure class="chart"><svg viewBox="0 0 800 142" role="img" aria-label="抽样单位净值走势"><path d="M12 115 H788" stroke="#d9e3db"/><polyline points="{coords}" fill="none" stroke="#237d73" stroke-width="2.5"/><text x="12" y="137">{clean[0][0]}</text><text x="690" y="137">{clean[-1][0]}</text><text x="12" y="13">净值区间 {lo:.4f}—{hi:.4f}</text></svg><figcaption>抽样单位净值，未复权；含分红影响，非完整日频样本，不据此给精确买卖点。</figcaption></figure>'


def render(document):
    scored=score_document(document)
    review=document.get('portfolio_review') or {}
    funds=document['funds'];total=scored['summary']['known_market_value']
    overview=[];cards=[]
    for i,(fund,row) in enumerate(zip(funds,scored['funds'])):
        action=normalize_action(fund)
        code=fund.get('code') or 'cash-'+str(i)
        anchor='fund-'+str(code)
        point=number(row['reference_score'],1)
        amount=row.get('market_value')
        weight=amount/total*100 if amount is not None and total else None
        overview.append(f'<tr data-find="{esc(str(code)+str(fund.get("name")))}"><td>{esc(action["priority"])}</td><td><a href="#{esc(anchor)}">{esc(fund.get("name") or "未命名")}<small>{esc(fund.get("code") or "代码未知")}</small></a></td><td>{number(amount)}</td><td>{number(weight)}%</td><td><strong>{esc(action["stance"])}</strong></td><td>{point}<small>覆盖{row["coverage_pct"]}%</small></td></tr>')
        context=row.get('context') or {}
        evidence=[]
        for d in row['dimensions']:
            e=d.get('evidence') if isinstance(d.get('evidence'),dict) else {}
            evidence.append('<tr>'+f'<td>{esc(d["label"])}</td><td>{d["weight_pct"]}%</td><td>{esc(e.get("value") if e.get("value") is not None else "未知")} {esc(d["unit"])}</td><td>{number(d["score"],1)}</td><td>{esc(e.get("as_of") or "未知")}</td><td>{esc(d["missing_reason"] or "披露/平台数据，核验状态见原证据")}<br>{link(e.get("source"))}</td></tr>')
        stages=context.get('stage_performance') or []
        stage_rows=[]
        for stage in stages:
            stage_rows.append('<tr>'+''.join('<td>'+esc(stage.get(key) if stage.get(key) is not None else '未知')+'</td>' for key in ('period_time','self_nav','self_max_draw_down','self_nav_rank'))+'</tr>')
        fee_rows=[]
        for fee in fund.get('redemption_fees',[]):
            fee_rows.append(f'<tr><td>{esc(fee.get("name") or "区间未知")}</td><td>{esc(fee.get("value") if fee.get("value") is not None else "未知")}%</td></tr>')
        lo,hi=row['missing_weight_range']
        cards.append(f'''<details class="fund" id="{esc(anchor)}" data-find="{esc(str(code)+str(fund.get('name')))}">
<summary><span><small>{esc(action['priority'])} · {esc(action['role'])}</small>{esc(fund.get('name') or '未命名')} <em>{esc(fund.get('code') or '代码未知')}</em></span><b>{esc(action['stance'])}</b></summary>
<div class="fund-body"><div class="facts"><span>金额 <strong>{number(amount)}元</strong></span><span>账户占比 <strong>{number(weight)}%</strong></span><span>参考分 <strong>{point}</strong> · 覆盖{row['coverage_pct']}%</span></div>
<div class="action"><h3>现在怎么处理</h3><p>{esc(action['next_step'])}</p>{items(action['reasons'])}</div>
<div class="conditions"><section><h3>考虑新增的条件</h3><p>{esc(action['add_condition'])}</p></section><section><h3>考虑减持/退出的条件</h3><p>{esc(action['reduce_condition'])}</p></section></div>
<h3>交易节奏与费用检查</h3>{items(action['cost_checks'])}<p class="muted">替代方案：{esc(action['alternative'])}</p>
<p>现任经理：{esc(context.get('manager_name') or '未知')}；成立日：{esc(context.get('founded_date') or '未知')}；公开净值日：{esc(context.get('nav_date') or '见来源说明')}。</p>
{nav_chart(fund.get('nav_history'))}
<details class="support"><summary>阶段业绩与经理资料</summary><p>平台区间累计收益，非本人收益；不同区间/类型不直接排名。</p><div class="scroll"><table><thead><tr><th>区间</th><th>累计收益%</th><th>最大回撤</th><th>同类名次</th></tr></thead><tbody>{''.join(stage_rows)}</tbody></table></div><p>{link(context.get('source'))}</p><p>{esc(context.get('benchmark_description') or '合同基准说明尚待补充')}</p></details>
<details class="support"><summary>参考评分、覆盖率与缺口</summary><p>{point}分；覆盖{row['coverage_pct']}%，独立核验覆盖{row['verified_coverage_pct']}%；缺失项范围{lo}—{hi}分。范围是缺失维度取0/100的敏感性边界，不是置信区间。分数偏风险/成本，不是旧V1/V2同口径评分，也不直接生成操作。</p><div class="scroll"><table><thead><tr><th>维度</th><th>权重</th><th>原始值</th><th>得分</th><th>日期</th><th>依据/缺口</th></tr></thead><tbody>{''.join(evidence)}</tbody></table></div>{items(row['flags'])}{items(context.get('data_gaps',[]))}</details>
<details class="support"><summary>平台列示赎回费率（并非本人实际适用费率）</summary><p>个人买入日、确认日、持有份额和到账条件未完整核验；持有期/滚动期规则优先，不能因下列0费率就推断现在可赎。费率来源截至原抓取日。</p><table><thead><tr><th>持有区间</th><th>列示费率</th></tr></thead><tbody>{''.join(fee_rows) or '<tr><td colspan="2">当前缓存无完整费率表，需以个人交易确认页核实</td></tr>'}</tbody></table></details></div></details>''')
    plan_rows=''.join('<tr>'+''.join('<td>'+esc(step.get(k,''))+'</td>' for k in ('priority','scope','action','condition'))+'</tr>' for step in review.get('plan',[]))
    allocation=[]
    for group in review.get('allocation',[]):
        p=float(group['account_pct'])
        allocation.append(f'<div class="allocation"><span>{esc(group["label"])}</span><i><b style="width:{min(100,max(0,p))}%"></b></i><strong>{p:.2f}%</strong></div>')
    stress_rows=''.join(f'<tr><td>{esc(s["label"])}</td><td>{esc(" / ".join(str(x)+"%" for x in s["shocks_pct"]))}</td><td>{float(s["loss"]):,.0f}元</td><td>{float(s["loss_account_pct"]):.2f}%</td><td>{float(s["loss_fund_only_pct"]):.2f}%</td></tr>' for s in review.get('stress',[]))
    alternative_rows=''.join('<tr>'+''.join('<td>'+esc(a.get(k,''))+'</td>' for k in ('name','when','benefit','cost'))+'</tr>' for a in review.get('alternatives',[]))
    sources=''.join('<li>'+link(url)+'</li>' for url in review.get('sources',[]))
    embedded=json.dumps(json_safe({'input':document,'scores':scored}),ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>持仓分析与操作方案</title><style>
:root{--ink:#203d38;--green:#26786b;--line:#dce4da;--paper:#fffef9}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:80px}body{margin:0;background:#eef2ec;color:var(--ink);font:15px/1.85 system-ui,"Microsoft YaHei",sans-serif}header{padding:40px max(24px,calc((100vw - 1200px)/2));background:#193f38;color:#fff}header small{letter-spacing:3px;color:#bed3b8}h1{font-size:clamp(27px,4vw,40px);margin:9px 0}header p{color:#d1dfd0}nav{position:sticky;top:0;background:#f7faf3f5;backdrop-filter:blur(8px);display:flex;gap:18px;padding:12px max(20px,calc((100vw - 1200px)/2));overflow:auto;white-space:nowrap;z-index:5;border-bottom:1px solid var(--line)}a{color:#286b83;text-underline-offset:3px}nav a{text-decoration:none;color:var(--green)}main{max-width:1240px;margin:auto;padding:24px}.panel,.fund{background:var(--paper);border:1px solid var(--line);border-radius:13px;margin-bottom:22px}.panel{padding:25px}h2{font-size:23px;margin:0 0 14px}h3{font-size:17px;margin:16px 0 8px}.lead{background:#e8f0df;border-left:4px solid var(--green);padding:18px 22px;border-radius:7px;font-size:17px}.muted,figcaption{color:#6b786e;font-size:13px}.facts{display:flex;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding:10px 0 16px}.facts strong{font-size:19px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;min-width:70px}th{background:#eaf0e2}td small,summary small{display:block;font-size:12px;color:#6d7a6e}.fund>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:20px;gap:15px;font-weight:650;font-size:17px}.fund>summary b{font-size:14px;background:#e7eee0;padding:5px 10px;border-radius:5px}.fund em{font-style:normal;font-size:12px;color:#748071}.fund-body{padding:0 24px 24px}.action{background:#f3eddc;border-left:3px solid #bd914d;padding:8px 18px;margin:18px 0}.conditions{display:grid;grid-template-columns:1fr 1fr;gap:18px}.conditions section{background:#f0f5ea;padding:7px 16px;border-radius:8px}.support{margin:12px 0;border-top:1px solid var(--line);padding-top:10px}.support>summary{cursor:pointer;color:#436c5c}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}input{flex:1;min-width:180px}input,button{padding:9px 13px;font:inherit;border:1px solid #b9cdb9;border-radius:7px;background:#fff}button{cursor:pointer;color:var(--green);background:#eaf1e2}.allocation{display:grid;grid-template-columns:minmax(160px,1.2fr) 2fr 75px;gap:15px;align-items:center;margin:10px 0;font-size:13px}.allocation i{height:10px;background:#edf1e7;border-radius:10px;overflow:hidden}.allocation b{display:block;height:100%;background:#6a9b7b;border-radius:10px}.chart{margin:15px 0}.chart svg{width:100%;max-height:180px}.chart text{font:11px system-ui;fill:#728174}.fund[hidden],tr[hidden]{display:none}footer{color:#748071;font-size:12px;text-align:center;padding:24px}@media(max-width:650px){main{padding:14px}.panel{padding:18px}.conditions{grid-template-columns:1fr}.fund>summary{align-items:start;flex-direction:column}.fund-body{padding:0 16px 20px}.allocation{grid-template-columns:1fr 1fr 60px;gap:7px}header{padding:26px 22px}}@media print{body{background:white;font-size:10pt}nav,.tools{display:none}header{background:white;color:var(--ink);padding:15px}header p{color:var(--ink)}main{padding:0}.panel{padding:12px;border:0}.scroll{overflow:visible}table{font-size:9pt}.fund>summary{break-after:avoid}.fund-body{display:block}.support{break-inside:avoid}a{color:inherit;text-decoration:none}}
</style></head><body>'''+f'''
<header><small>LIFEOS · PORTFOLIO DECISION REVIEW</small><h1>持仓分析与操作方案</h1><p>报告生成：{esc(document.get('report_date') or document['as_of'])} · 持仓记录：{esc(document['as_of'])} · 私密本地报告</p><p>{esc(review.get('data_note') or '数据日期见各项来源；建议未执行。')}</p></header>
<nav><a href="#decision">操作结论</a><a href="#plan">处理顺序</a><a href="#risk">结构与压力</a><a href="#alternatives">方案比较</a><a href="#holdings">逐只分析</a><a href="#method">依据与边界</a></nav><main>
<section class="panel" id="decision"><h2>先看操作结论</h2><p class="lead">{esc(review.get('headline') or '先明确组合用途与交易条件，再根据证据讨论操作。')}</p><div class="facts"><span>已知持仓 <strong>{number(total)}元</strong></span><span>持仓条目 <strong>{len(funds)}</strong></span><span>有参考分 <strong>{scored['summary']['scored_count']}</strong></span></div>{items(review.get('conclusions',[]))}<p class="muted">以下为研究建议及条件方案，未记为采纳、未执行交易。分数是辅助信息；操作判断另看用途、重叠、期限与交易成本。</p></section>
<section class="panel" id="plan"><h2>组合处理优先级</h2><div class="scroll"><table><thead><tr><th>优先级</th><th>涉及方向</th><th>建议动作</th><th>执行前条件</th></tr></thead><tbody>{plan_rows}</tbody></table></div>{items(review.get('execution_rules',[]))}</section>
<section class="panel" id="risk"><h2>账户结构与风险承受</h2>{''.join(allocation)}<h3>15%约束的假设压力检查</h3><p>{esc(review.get('stress_note') or '人为情景，非预测、回测或概率；历史回撤与剩余预算未核实。')}</p><div class="scroll"><table><thead><tr><th>情景</th><th>分组收益假设</th><th>损失量级</th><th>全账户</th><th>剔除余额宝</th></tr></thead><tbody>{stress_rows}</tbody></table></div></section>
<section class="panel" id="alternatives"><h2>四种操作方案比较</h2><div class="scroll"><table><thead><tr><th>方案</th><th>适用条件</th><th>好处</th><th>成本与风险</th></tr></thead><tbody>{alternative_rows}</tbody></table></div></section>
<section class="panel" id="holdings"><h2>{len(funds)}项持仓操作总览</h2><p>先看处理倾向，点击名称展开完整理由、加减仓条件、费用、走势图及评分证据。</p><div class="tools"><input id="search" type="search" placeholder="输入代码或基金名称" aria-label="搜索基金"><button id="expand">展开基金</button><button id="collapse">收起基金</button><button id="print">打印 / 保存PDF</button></div><div class="scroll"><table><thead><tr><th>优先级</th><th>产品</th><th>金额（元）</th><th>账户占比</th><th>操作倾向</th><th>参考分</th></tr></thead><tbody>{''.join(overview)}</tbody></table></div></section>
{''.join(cards)}<section class="panel" id="method"><h2>依据、数据时点与边界</h2>{items(review.get('limitations',[]))}<p>六类规则评分偏风险与成本，缺失不填50；不同类型与不同证据集不直接排名。操作分析为显式研究判断，分数、单次跌幅和浮亏不能直接触发买卖。本HTML已内嵌本次输入及评分，复制单个文件即可阅读；不用外部JSON、字体、脚本或本机服务。</p><ul>{sources}</ul></section>
<script type="application/json" id="embedded-research">{embedded}</script><script>
const funds=[...document.querySelectorAll('.fund')],rows=[...document.querySelectorAll('tr[data-find]')];document.getElementById('search').oninput=e=>{{const q=e.target.value.trim().toLowerCase();[...funds,...rows].forEach(c=>c.hidden=!c.dataset.find.toLowerCase().includes(q))}};
document.getElementById('expand').onclick=()=>funds.filter(c=>!c.hidden).forEach(c=>c.open=true);document.getElementById('collapse').onclick=()=>funds.forEach(c=>c.open=false);
function reveal(){{const target=document.getElementById(location.hash.slice(1));if(target?.matches('.fund')){{target.hidden=false;target.open=true}}}}window.addEventListener('hashchange',reveal);document.querySelectorAll('a[href^="#fund-"]').forEach(a=>a.addEventListener('click',()=>{{const target=document.getElementById(a.getAttribute('href').slice(1));if(target){{target.hidden=false;target.open=true}}}}));reveal();
let saved=[];const details=[...document.querySelectorAll('details')];window.addEventListener('beforeprint',()=>{{saved=details.map(c=>[c.open,c.hidden]);details.forEach(c=>{{c.open=true;c.hidden=false}});rows.forEach(c=>c.hidden=false)}});window.addEventListener('afterprint',()=>{{details.forEach((c,i)=>{{[c.open,c.hidden]=saved[i]}});document.getElementById('search').dispatchEvent(new Event('input'))}});document.getElementById('print').onclick=()=>window.print();
</script></main><footer>单文件离线报告 · 个人数据仅本地保存 · 建议未执行</footer></body></html>'''


def generate(document, output_html):
    path=Path(output_html)
    if path.suffix.lower()!='.html':raise ValueError('输出文件须为.html')
    content=render(document)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content,encoding='utf-8')
    return path


def main():
    parser=argparse.ArgumentParser(description='生成一个包含操作分析、组合方案和评分证据的离线HTML')
    parser.add_argument('--input',required=True,help='本地证据和显式研究判断JSON')
    parser.add_argument('--output',required=True,help='唯一成品HTML路径')
    args=parser.parse_args()
    print(generate(json.loads(Path(args.input).read_text(encoding='utf-8')),args.output).resolve())


if __name__=='__main__':main()
