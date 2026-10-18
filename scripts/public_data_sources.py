"""公开产品补源：天天基金费率/配置及管理人定期报告；个人输入只在本地合并。"""
import argparse
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import time
import urllib.request
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

COLLECTOR_VERSION='public-sources-v2'


class Tables(HTMLParser):
    """只读取单元格文本，不执行网页脚本。"""
    def __init__(self, text):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag=='tr': self.row=[]
        if tag in ('td','th') and self.row is not None: self.cell=[]

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell=None
        if tag in ('tr','tbody','table') and self.row is not None:
            self.rows.append(self.row); self.row=None


def number(text):
    try:
        value=float(str(text).replace(',','').replace('%','').strip())
        return value if math.isfinite(value) and value>=0 else None
    except (ValueError,TypeError): return None


def evidence(value, as_of, source, **extra):
    return dict(value=value, as_of=as_of, source=source, verified=False, **extra)


def parse_fees(text, as_of, source):
    labels={'管理费率','托管费率','销售服务费率'}; rates={}; raw_rates={}
    section=re.search(r'运作费用</label>.*?(<table\b.*?</table>)',text,re.S)
    for row in Tables(section[1] if section else text).rows:
        for i, cell in enumerate(row[:-1]):
            label=re.sub(r'\s+','',cell)
            if label in labels:raw_rates[label]=row[i+1].strip()
            if label in labels and re.fullmatch(r'\s*\d+(?:\.\d+)?%[（(]每年[）)]\s*',row[i+1]):
                rates.setdefault(label,set()).add(number(row[i+1].split('%')[0]))
    complete_three=set(rates)==labels
    # A类/场内ETF经常只列两项；仅完整“运作费用”表允许列示项小计，不声称未列销售服务费=0。
    listed_two=bool(section and set(rates)=={'管理费率','托管费率'}
                    and raw_rates.get('销售服务费率') in (None,'---','--','—','-'))
    if not (complete_three or listed_two) or any(len(v)!=1 for v in rates.values()): return {}
    return {'annual_fee_pct': evidence(sum(next(iter(v)) for v in rates.values()),as_of,source,
            components={k:next(iter(v)) for k,v in rates.items()},
            fee_scope='listed_operating_fees' if listed_two else 'three_listed_components',
            note='完整运作费用表列示项合计；未列销售服务费不等于已核实为0，不是实际总费用' if listed_two else '页面列示三项名义费率，未计豁免与申赎费')}


def parse_allocation(text, as_of, source):
    rows=Tables(text).rows
    # 仅接受有明确“股票占净比”表头的表，不读取图表的总资产分母。
    active=False; candidates=[]
    for row in rows:
        if '报告期' in row and '股票占净比' in row: active=True; continue
        if active and len(row)>=5 and re.fullmatch(r'\d{4}-\d{2}-\d{2}',row[0]):
            if row[0]<=as_of: candidates.append(row)
    if not candidates:return {}
    row=max(candidates,key=lambda r:r[0]); value=number(row[1])
    return {} if value is None else {'equity_pct':evidence(value,row[0],source,basis='net_assets')}


def parse_periodic_report(pages, as_of, source, code):
    """仅提取完整债券分类表及同一份报告资产负债表，失败保留缺口。"""
    text='\n'.join(pages)
    compact=re.sub(r'\s+','',text)
    if code not in compact: return {}, ['报告未找到本份额代码，未自动接入']
    # 报告期须由正文报告截止日确认，抓取日不能替代披露期。
    dates=re.findall(r'报告截止日[：:]?(\d{4})年(\d{1,2})月(\d{1,2})日',compact)
    dates={date(int(y),int(m),int(d)).isoformat() for y,m,d in dates}
    if len(dates)!=1:return {}, ['报告截止日缺失或冲突']
    when=dates.pop()
    if when>as_of:return {}, ['报告截止日晚于研究日期']
    metrics={}; notes=[]; stock_amount=None; fund_amount=None
    # 去掉目录；要求表头、类别、合计同处正文页面。
    for index,page in enumerate(pages):
        flat=re.sub(r'\s+','',page+(pages[index+1] if index+1<len(pages) else ''))
        if '债券品种' in flat and '占基金资产净值比例' in flat and '合计' in flat:
            match=re.search(r'可转债[（(]可交换债[）)]([\d,]+\.\d{2}|-)([\d]+\.\d{2}|-)(?=\d+(?:同业存单|其他))',flat)
            if match:
                amount,pct=match.groups()
                if (amount=='-')==(pct=='-'):
                    metrics['convertible_pct']=evidence(0.0 if pct=='-' else float(pct),when,source,
                        basis='net_assets',page=index+1,excerpt=match.group(),note='完整债券品种分类，不是前五重仓债券')
    # 资产负债表常跨两页；限制到6.1节，避免误取利率期限分布表。
    balances=re.findall(r'6\.1资产负债表(.*?)(?:6\.2利润表)',compact,re.S)
    for section in balances:
        gross=re.search(r'(?<!净)资产总计([\d,]+\.\d{2})',section)
        net=re.search(r'净资产合计([\d,]+\.\d{2})',section)
        if gross and net and float(net[1].replace(',',''))>0:
            ratio=float(gross[1].replace(',',''))/float(net[1].replace(',',''))
            if 1<=ratio<=10:
                metrics['gross_assets_ratio']=evidence(ratio,when,source,excerpt=gross[0]+'；'+net[0])
        stock=re.search(r'其中[：:]股票投资([\d,]+\.\d{2}|-)',section)
        fund=re.search(r'基金投资([\d,]+\.\d{2}|-)',section)
        if fund:fund_amount=0.0 if fund[1]=='-' else float(fund[1].replace(',',''))
        if stock and net and float(net[1].replace(',',''))>0:
            stock_amount=0.0 if stock[1]=='-' else float(stock[1].replace(',',''))
            value=stock_amount/float(net[1].replace(',',''))*100
            metrics['equity_pct']=evidence(value,when,source,basis='net_assets',excerpt=stock[0]+'；'+net[0])
    # 完整股票/权益明细直接使用公允价值分子。联接/基金投资不把少量直持股票冒充穿透。
    if stock_amount and fund_amount==0 and '联接' not in compact[:2500]:
        heading=r'7\.\d+\s+期末按公允价值占基金资产净值比例大小排[序名]的(?:所有|前十名)(?:股票|权益)投资明细'
        for title in re.finditer(heading,text):
            rest=text[title.end():]
            end=re.search(r'(?m)^\s*7\.\d+\s+[^\d\s]',rest)
            body=rest[:end.start()] if end else rest
            flat=re.sub(r'\s+','',body)
            if '公允价值' not in flat or '占基金资' not in flat:continue
            values=[(float(re.sub(r'\s+','',a).replace(',','')),float(p)) for a,p in
                    re.findall(r'(?<![\d,])(\d{1,3}(?:,\d{3})+\.\s*\d{2})\s+(\d+\.\d{2})(?!\d)',body)]
            top=values[:10]
            # 检查排序、分母与每行披露百分比，防止把数量或其他表当金额。
            if (len(top)==10 and all(a>=b for (a,_),(b,_) in zip(top,top[1:]))
                    and sum(a for a,_ in top)<=stock_amount*1.00001
                    and all(abs(a/stock_amount*metrics['equity_pct']['value']-pct)<=.02 for a,pct in top)):
                metrics['top10_equity_pct']=evidence(sum(a for a,_ in top)/stock_amount*100,when,source,
                    basis='equity_assets',complete=True,top10_market_values=[a for a,_ in top],equity_market_value=stock_amount,
                    note='完整权益明细前十公允价值/资产负债表股票投资，逐行与占净值比例复核')
    if 'convertible_pct' not in metrics: notes.append('未匹配完整转债/交换债分类行，未从重仓列表填零')
    if 'AAA以下' in compact and '按长期信用评级' in compact:
        notes.append('已查中报信用表，但AAA以下未细分AA+/AA；未评级项目也需区分国债/政策债，不能直接代入低信用比例')
    if '修正久期' not in compact:
        notes.append('中报未检出明确修正久期；期限分布或利率敏感性不是该字段的直接披露')
    return metrics,notes


class PublicCollector:
    def __init__(self, proxy=None, timeout=25):
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':proxy,'http':proxy}) if proxy else urllib.request.ProxyHandler())
        self.timeout=timeout

    def fetch(self,url):
        for attempt in range(3):
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://fundf10.eastmoney.com/'})
                with self.opener.open(request,timeout=self.timeout) as response: return response.read()
            except Exception:
                if attempt==2:raise
                time.sleep(.5*(attempt+1))

    def collect(self,code,as_of,cache_dir,refresh=False):
        if not re.fullmatch(r'[0-9]{6}',code):raise ValueError('只接受六位公开基金代码')
        directory=Path(cache_dir);directory.mkdir(parents=True,exist_ok=True)
        path=directory/(code+'.json')
        cached=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if (cached and not refresh and cached.get('analysis_as_of')==as_of
                and cached.get('collector_version')==COLLECTOR_VERSION):return cached
        result={'code':code,'collector_version':COLLECTOR_VERSION,'analysis_as_of':as_of,'retrieved_at':datetime.now(timezone.utc).isoformat(),'metrics':{},'sources':{},'notes':[]}
        today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        # 新用户不需要先手工建立历史蛋卷缓存，基础字段直接采集。
        public={}
        for key,endpoint in [('info',f'fund/{code}'),('detail',f'fund/detail/{code}'),
                             ('achievement',f'fundx/base/fund/achievement/{code}')]:
            url='https://danjuanfunds.com/djapi/'+endpoint
            try:
                payload=json.loads(self.fetch(url));data=payload.get('data')
                if not isinstance(data,dict):raise ValueError('接口未返回产品数据对象')
                public[key]=data
                result['sources'][key]={'url':url,'status':'ok','payload':payload}
            except Exception as exc:result['sources'][key]={'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:160]}
        for key,slug,parser in [('fees','jjfl',parse_fees),('allocation','zcpz',parse_allocation)]:
            url=f'https://fundf10.eastmoney.com/{slug}_{code}.html'
            try:
                raw=self.fetch(url);text=raw.decode('utf-8-sig')
                (directory/f'{code}_{key}.html').write_bytes(raw)
                # 当前费率页面不能回填为历史日期。
                metrics=parser(text,today if key=='fees' else as_of,url)
                result['metrics'].update(metrics);result['sources'][key]={'url':url,'status':'ok' if metrics else 'no_matching_fields'}
            except Exception as exc:result['sources'][key]={'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:160]}
        if not public.get('info'):
            # 场内ETF在蛋卷基础接口可能没有数据，使用公开档案与有完整日期的净值接口。
            fallback={}
            fee_path=directory/f'{code}_fees.html'
            if fee_path.exists():
                plain=unescape(re.sub('<[^>]+>',' ',fee_path.read_text(encoding='utf-8')))
                for key,pattern in [('found_date',r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})'),
                                    ('manager_name',r'基金经理[：:]\s*(.*?)\s*类型[：:]'),
                                    ('type_desc',r'类型[：:]\s*(.*?)\s*管理人[：:]')]:
                    match=re.search(pattern,plain,re.S)
                    if match:fallback[key]=re.sub(r'\s+',' ',match[1]).strip()
            url=f'https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=1'
            try:
                payload=json.loads(self.fetch(url));latest=payload.get('Data',{}).get('LSJZList',[])
                if latest:fallback['fund_derived']={'end_date':latest[0]['FSRQ']}
                result['sources']['nav_latest']={'url':url,'status':'ok' if latest else 'no_matching_fields','payload':payload}
            except Exception as exc:result['sources']['nav_latest']={'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:160]}
            if fallback:public['info']=fallback
        info=public.get('info',{});detail=public.get('detail',{});achievement=public.get('achievement',{})
        nav_date=(info.get('fund_derived') or {}).get('end_date')
        try:
            age=(date.fromisoformat(nav_date)-date.fromisoformat(info.get('found_date'))).days
            stage=next((s for s in achievement.get('stage_performance_list',[]) if s.get('period_time') in ('近1年','近一年')),None)
            value=number(stage.get('self_max_draw_down')) if stage else None
            if age>=365 and value is not None:
                result['metrics']['drawdown_1y_pct']=evidence(value,nav_date,result['sources']['achievement']['url'],period_days=365,
                    note='平台明确标注近一年最大回撤；份额成立满一年，非从稀疏净值自行推算')
        except (TypeError,ValueError):pass
        if info and detail:
            from scripts.research_evidence import current_team_tenure
            try:team=current_team_tenure(info,detail,code,today,result['sources']['detail']['url'])
            except (TypeError,ValueError,AttributeError):team=None
            if team:result['metrics']['manager_tenure_years']=team
        result['context']={'manager_name':info.get('manager_name'),'fund_type':info.get('type_desc'),
            'founded_date':info.get('found_date'),'nav_date':nav_date,'retrieved_at':result['retrieved_at'],
            'stage_performance':[{k:s.get(k) for k in ('period_time','self_nav','self_max_draw_down','self_nav_rank')}
                                 for s in achievement.get('stage_performance_list',[])],
            'source':result['sources'].get('achievement',{}).get('url')}
        index_url=f'https://api.fund.eastmoney.com/f10/JJGG?fundcode={code}&pageIndex=1&pageSize=20&type=3'
        try:
            index=json.loads(self.fetch(index_url));result['sources']['report_index']={'url':index_url,'status':'ok'}
            (directory/f'{code}_report_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
            reports=[r for r in index.get('Data',[]) if r.get('FUNDCODE')==code and r.get('PUBLISHDATEDesc','9999')<=as_of
                     and re.search(r'中期报告|年度报告',r.get('TITLE','')) and '摘要' not in r['TITLE']]
            if reports:
                report=max(reports,key=lambda r:r['PUBLISHDATEDesc']);rid=report['ID']
                if not re.fullmatch(r'AN[0-9]+',rid):raise ValueError('公告ID格式异常')
                url=f'https://pdf.dfcfw.com/pdf/H2_{rid}_1.pdf'
                raw=self.fetch(url)
                from pypdf import PdfReader
                pages=[p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages]
                (directory/f'{code}_{rid}.pdf').write_bytes(raw)
                metrics,notes=parse_periodic_report(pages,as_of,url,code)
                for item in metrics.values():
                    item['published_at']=report['PUBLISHDATEDesc']
                    item['evidence_type']='manager_periodic_report'
                for key,item in metrics.items():
                    if result['metrics'].get(key,{}).get('as_of','')<=item['as_of']:result['metrics'][key]=item
                result['notes']+=notes
                result['sources']['periodic_report']={'url':url,'status':'ok','title':report['TITLE'],'published_at':report['PUBLISHDATEDesc']}
            else: result['notes'].append('未找到研究日期以前的完整中期/年度报告')
        except Exception as exc:result['sources']['periodic_report']={'url':index_url,'status':'error','error':type(exc).__name__+': '+str(exc)[:160]}
        for key,item in cached.get('metrics',{}).items():
            if key not in result['metrics']:
                result['metrics'][key]=item
                result['notes'].append(f'{key}本次未获取到新值，保留原日期缓存，合并时仍检查有效期')
        if cached:result['previous_sources']=cached.get('sources',{})
        temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
        return result


def enrich_supplemental(document,cache_dir):
    """有效同口径证据才补入；有效手工证据优先，冲突保留审计记录。"""
    from scripts.research_scoring import METRICS,validate_evidence
    result=deepcopy(document);when=date.fromisoformat(result['as_of'])
    for fund in result['funds']:
        code=fund.get('code')
        if not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code):continue
        path=Path(cache_dir)/(code+'.json')
        if not path.exists():continue
        cached=json.loads(path.read_text(encoding='utf-8'))
        if cached.get('code')!=code:continue
        context=fund.setdefault('context',{});audit=context.setdefault('supplemental_audit',[])
        for key,value in cached.get('context',{}).items():
            if context.get(key) is None:context[key]=value
        metrics=fund.setdefault('metrics',{})
        for key,candidate in cached.get('metrics',{}).items():
            if key not in METRICS:continue
            reason=validate_evidence(key,candidate,when)
            if candidate.get('published_at','0000')>result['as_of']:reason='公告晚于研究日期'
            old=metrics.get(key)
            if reason:entry={'metric':key,'status':'rejected','reason':reason,'candidate':candidate}
            elif old is not None and validate_evidence(key,old,when) is None:
                differs=abs(old['value']-candidate['value'])>=.05
                # 同期平台转载与管理人原始报表冲突时，使用可追溯原文；手工证据仍优先。
                if (differs and candidate.get('evidence_type')=='manager_periodic_report'
                        and candidate.get('as_of')==old.get('as_of')
                        and str(old.get('source','')).startswith('https://danjuanfunds.com/')):
                    metrics[key]=candidate
                    entry={'metric':key,'status':'replaced_platform','previous':old,'candidate':candidate}
                else:entry={'metric':key,'status':'existing_kept' if not differs else 'conflict_existing_kept','candidate':candidate}
            else:
                metrics[key]=candidate
                entry={'metric':key,'status':'added','previous':old,'candidate':candidate}
            if entry not in audit and not any(e.get('metric')==key and e.get('status') in ('added','replaced_platform') and e.get('candidate')==candidate for e in audit):audit.append(entry)
        gaps=context.setdefault('data_gaps',[])
        for note in cached.get('notes',[]):
            if note not in gaps:gaps.append(note)
        concentration=metrics.get('top10_equity_pct',{})
        if (fund.get('qdii') and str(concentration.get('source','')).startswith('https://danjuanfunds.com/')
                and concentration.get('global_equities_complete') is not True):
            reason='QDII原平台列表未核实涵盖全部海外股票；需完整权益明细及基金投资穿透，暂停原集中度评分'
            entry={'metric':'top10_equity_pct','status':'invalidated_partial','previous':concentration,
                   'candidate':concentration,'reason':reason}
            if entry not in audit:audit.append(entry)
            metrics.pop('top10_equity_pct',None)
            fund.setdefault('missing_explanations',{})['top10_equity_pct']=reason
            if reason not in gaps:gaps.append(reason)
        context['supplemental_sources']=cached.get('sources',{})
    return result


def render_source_audit(context):
    """补源成功、拒绝及冲突都可见，不只藏在嵌入JSON中。"""
    from html import escape
    from scripts.research_scoring import METRICS
    entries=context.get('supplemental_audit',[])
    if not entries:return ''
    labels={'added':'已补入','existing_kept':'与已有证据一致，保留原值',
            'conflict_existing_kept':'来源存在差异，保留原值待核','rejected':'未通过证据校验',
            'replaced_platform':'已采用管理人同期原文纠正平台值，旧值保留在证据中',
            'invalidated_partial':'原集中度证据不完整，已暂停计分并保留旧值'}
    rows=[]
    for entry in entries:
        candidate=entry.get('candidate',{})
        metric_label=METRICS.get(entry['metric'],(entry['metric'],))[0]
        description=f"{metric_label}：{labels.get(entry['status'],entry['status'])}；候选值 {candidate.get('value')}；数据日 {candidate.get('as_of')}"
        if entry.get('previous') is not None:description+=f"；旧值 {entry['previous'].get('value')}"
        if entry.get('reason'):description+='；'+entry['reason']
        url=candidate.get('source','')
        rows.append('<li>'+escape(description)+(f' <a href="{escape(url,quote=True)}" rel="noreferrer">补充来源</a>' if url.startswith('https://') else '')+'</li>')
    return '<details class="support"><summary>补源记录与来源差异</summary><ul>'+''.join(rows)+'</ul></details>'


def main():
    parser=argparse.ArgumentParser(description='公开产品补源；仅把六位基金代码发送到外部接口')
    parser.add_argument('--codes',nargs='+',required=True)
    parser.add_argument('--as-of',default=datetime.now(timezone(timedelta(hours=8))).date().isoformat())
    parser.add_argument('--cache-dir',required=True)
    parser.add_argument('--proxy',default=None,help='可选HTTP代理，不内置个人电脑地址')
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args();date.fromisoformat(args.as_of)
    collector=PublicCollector(args.proxy)
    for code in dict.fromkeys(args.codes):
        result=collector.collect(code,args.as_of,args.cache_dir,args.refresh)
        print(json.dumps({'code':code,'metrics':list(result['metrics']),'sources':result['sources']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
