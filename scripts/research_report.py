"""离线分类型评分入口：python scripts/research_report.py --input ... --output-dir ..."""
import argparse
import html
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.research_scoring import MODEL_VERSION, score_document
from scripts.research_evidence import enrich_document

def esc(value): return html.escape(str(value),quote=True)
def display(value,suffix=''): return '未知' if value is None else f'{value:,.1f}{suffix}'
def source_link(source):
    if isinstance(source,str) and source and urlsplit(source).scheme in ('http','https'):
        return f'<a href="{esc(source)}" rel="noreferrer">来源</a>'
    return esc(source or '未知')

def render_html(result):
    cards=[]
    for index,row in enumerate(result['funds']):
        dimensions=[]
        for d in row['dimensions']:
            evidence=d.get('evidence') if isinstance(d.get('evidence'),dict) else {}
            dimensions.append(f'<tr><td>{esc(d["label"])}</td><td>{d["weight_pct"]}%</td>'
                f'<td>{esc(evidence.get("value","未知"))} {esc(d["unit"])}</td>'
                f'<td>{display(d["score"])}</td><td>{esc(evidence.get("as_of","未知"))}</td>'
                f'<td>{esc(d["missing_reason"] or ("独立核验" if evidence.get("verified") is True else "披露/平台数据，未独立核验"))}<br>{source_link(evidence.get("source"))}</td></tr>')
        flags=''.join('<li>'+esc(x)+'</li>' for x in row['flags'])
        search=esc(str(row.get('code') or '')+' '+str(row.get('name') or ''))
        lo,hi=row['missing_weight_range']
        context=row.get('context',{})
        performance=[]
        for stage in context.get('stage_performance',[]):
            performance.append('<tr>'+''.join('<td>'+esc(stage.get(key) if stage.get(key) is not None else '未知')+'</td>' for key in ('period_time','self_nav','self_max_draw_down','self_nav_rank'))+'</tr>')
        context_html=''
        if context:
            context_html=f'<h3>已有产品资料与业绩</h3><p>现任经理：{esc(context.get("manager_name") or "未知")}；产品类型：{esc(context.get("fund_type") or "未知")}；成立日：{esc(context.get("founded_date") or "未知")}。<br>公开净值日：{esc(context.get("nav_date") or "见原缓存")}；缓存抓取：{esc(context.get("retrieved_at") or "未知")}。</p>'
            if performance:context_html+='<div class="scroll"><table><thead><tr><th>区间</th><th>平台累计收益（%）</th><th>平台最大回撤</th><th>平台同类名次</th></tr></thead><tbody>'+''.join(performance)+'</tbody></table></div><p>上述收益不是本人收益；名次口径/样本见平台。未把平台展示指数自动认作合同基准。</p>'
            if context.get('benchmark_description'):context_html+='<details><summary>平台列示的基准说明</summary><p>'+esc(context['benchmark_description'])+'</p></details>'
            context_html+='<ul>'+''.join('<li>'+esc(gap)+'</li>' for gap in context.get('data_gaps',[]))+'</ul>'
        cards.append(f'<details class="card" id="score-{esc(row.get("code") or index)}" data-search="{search}" open><summary><span>{esc(row.get("code") or "未确认代码")} · {esc(row.get("name") or "未命名")}</span><b>{display(row["reference_score"])}分</b></summary>'
          f'<div class="body"><div class="badges"><span>{esc(row.get("profile_label") or "类型待核实")}</span><span>{esc(row["status"])}</span><span>模型数据覆盖 {row["coverage_pct"]}%</span><span>独立核验覆盖 {row["verified_coverage_pct"]}%</span></div>'
          f'<p><strong>缺失项范围 {lo:.1f}–{hi:.1f}分</strong>：把缺失维度分别设为0/100所得完整加权分范围，非统计置信区间。点分仅按已知维度权重归一化。</p>'
          '<div class="scroll"><table><thead><tr><th>维度</th><th>原权重</th><th>原始值</th><th>维度分</th><th>数据日期</th><th>证据/缺口</th></tr></thead><tbody>'
          +''.join(dimensions)+'</tbody></table></div>'+context_html+'<ul>'+flags+'</ul></div></details>')
    summary=result['summary']
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>基金研究参考评分</title><style>
body{margin:0;background:#f1f4ef;color:#213d39;font:15px/1.8 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1160px;margin:auto;padding:28px}h1{font-size:30px}.intro,.card{background:#fff;border:1px solid #d9e2d9;border-radius:12px;margin:18px 0;padding:20px}.intro{border-top:5px solid #347c70}.tools{display:flex;gap:10px;position:sticky;top:0;background:#f1f4eff5;padding:12px 0;z-index:1;flex-wrap:wrap}input{flex:1;min-width:180px;padding:12px}input,button{border:1px solid #b7cbbd;border-radius:7px;font:inherit}button{cursor:pointer;background:#e5eee3;color:inherit;padding:8px 14px}.card{padding:0}.card summary{cursor:pointer;display:flex;justify-content:space-between;gap:20px;padding:20px;font-size:17px;font-weight:600}.card summary b{white-space:nowrap;font-size:23px;color:#286d62}.body{padding:0 20px 20px}.badges{display:flex;gap:8px;flex-wrap:wrap}.badges span{font-size:12px;padding:3px 8px;background:#edf2e8;border-radius:5px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:11px;text-align:left;border-bottom:1px solid #dce4d9;min-width:65px}th{background:#edf2e8}a{color:#216f89}.muted{color:#67766f}.card[hidden]{display:none}@media print{.tools{display:none}body{background:#fff}main{padding:0}.card{break-inside:avoid}summary{break-after:avoid}table{font-size:9pt}.scroll{overflow:visible}}</style></head><body><main>'''+f'''
<h1>基金研究参考评分</h1><p class="muted">{esc(result['as_of'])} · {MODEL_VERSION} · 本地离线报告</p>
<section class="intro"><strong>分数偏重风险控制、成本与可验证的产品表现，不是未来收益、买卖时点或保本概率。</strong>
<p>权重和阈值为公开的启发式研究规则，尚未完成预测能力验证。不同基金类型、不同可用维度的分数不直接排名；完整范围越宽，点分越不稳定。零值是真实零值，缺失不补50。</p>
<p><strong>与原技能结果的区别：</strong>本页采用新增的风险/成本研究模型，不是旧V1/V2评分的同口径重跑。原来已有的阶段收益、回撤、同类名次和经理资料列在各基金下方；新模型额外要求的信用、久期、真实估值和基准等，未取得时明确留缺口。</p>
<p>输入{summary['entry_count']}项，{summary['scored_count']}项有参考分；已知市值中可评分条目占比{display(summary['scored_value_share_pct'],'%')}，按市值加权的模型证据覆盖{display(summary['evidence_weighted_value_coverage_pct'],'%')}。市值完整：{'是' if summary['all_values_known'] else '否，分母仅含已知市值'}。<strong>不输出跨类型组合总分或自动仓位。</strong></p></section>
<div class="tools"><input id="search" placeholder="搜索代码或名称" aria-label="搜索基金"><button id="expand">展开全部</button><button id="collapse">收起全部</button><button id="print">打印 / 保存PDF</button></div>
{''.join(cards)}<p class="muted">详细输入、节点、日期与缺失原因保存在同目录 research_scores.json。规则详见技能 references/research-scoring.md。</p>
<script>const cards=[...document.querySelectorAll('.card')];document.getElementById('search').oninput=e=>{{const q=e.target.value.trim().toLowerCase();cards.forEach(c=>c.hidden=!c.dataset.search.toLowerCase().includes(q))}};document.getElementById('expand').onclick=()=>cards.filter(c=>!c.hidden).forEach(c=>c.open=true);document.getElementById('collapse').onclick=()=>cards.forEach(c=>c.open=false);let saved=[];window.addEventListener('beforeprint',()=>{{saved=cards.map(c=>[c.open,c.hidden]);cards.forEach(c=>{{c.open=true;c.hidden=false}})}});window.addEventListener('afterprint',()=>cards.forEach((c,i)=>{{[c.open,c.hidden]=saved[i]}}));document.getElementById('print').onclick=()=>window.print();</script></main></body></html>'''

def generate(document, output_dir, public_data_dir=None):
    if public_data_dir is not None:document=enrich_document(document,public_data_dir)
    result=score_document(document)
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    json_path=output/'research_scores.json';html_path=output/'research_scores.html'
    json_path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    html_path.write_text(render_html(result),encoding='utf-8')
    return html_path,json_path

def main():
    parser=argparse.ArgumentParser(description='分类型研究参考评分：允许部分数据，展示覆盖率和缺口')
    parser.add_argument('--input',required=True,help='本地证据JSON，格式见references/research-scoring.md')
    parser.add_argument('--output-dir',required=True,help='本地报告目录；实际持仓请放Private或被忽略目录')
    parser.add_argument('--public-data-dir',help='可选公开产品缓存目录；补接经理任期并展示阶段业绩')
    args=parser.parse_args()
    document=json.loads(Path(args.input).read_text(encoding='utf-8'))
    for path in generate(document,args.output_dir,args.public_data_dir):print(path.resolve())

if __name__=='__main__': main()
