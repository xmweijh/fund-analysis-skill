import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.public_data_sources import (enrich_supplemental,parse_fees,parse_allocation,
    parse_periodic_report,render_source_audit,PublicCollector)


class PublicSourceTests(unittest.TestCase):
    def test_fees_require_all_three_and_preserve_explicit_zero(self):
        text='<table><tr><td>管理费率</td><td>0.30%（每年）</td><td>托管费率</td><td>0.10%（每年）</td><td>销售服务费率</td><td>0.00%（每年）</td></tr></table>'
        self.assertAlmostEqual(parse_fees(text,'2026-10-18','synthetic')['annual_fee_pct']['value'],.4)
        self.assertEqual(parse_fees(text.replace('0.00%（每年）','---'),'2026-10-18','synthetic'),{})

    def test_allocation_net_asset_header_date_and_missing_are_required(self):
        text='<table><tr><th>报告期</th><th>股票占净比</th></tr><tr><td>2026-06-30</td><td>0.00%</td><td>99%</td><td>1%</td><td>1</td></tr><tr><td>2026-12-31</td><td>80%</td><td>1%</td><td>1%</td><td>1</td></tr></table>'
        self.assertEqual(parse_allocation(text,'2026-10-18','s')['equity_pct']['value'],0)
        self.assertEqual(parse_allocation(text.replace('股票占净比','股票占总资产'),'2026-10-18','s'),{})
        self.assertEqual(parse_allocation(text.replace('0.00%','---'),'2026-10-18','s'),{})

    def report(self):
        return ['基金代码基金代码000000 报告截止日：2026年6月30日\n6.1 资产负债表\n其中：股票投资 - -\n资产总计 1,200.00 900.00',
                '净资产合计 1,000.00 800.00\n6.2 利润表\n7.5 债券品种 公允价值 占基金资产净值比例（%）\n7 可转债（可交换债） - -',
                '8 同业存单 100.00 10.00\n9 其他 - -\n10 合计 900.00 90.00']

    def test_report_spanning_pages_has_full_convertible_zero_and_same_date_assets(self):
        metrics,_=parse_periodic_report(self.report(),'2026-10-18','s','000000')
        self.assertEqual(metrics['convertible_pct']['value'],0)
        self.assertEqual(metrics['gross_assets_ratio']['value'],1.2)
        self.assertEqual(metrics['equity_pct']['value'],0)
        self.assertEqual(metrics['gross_assets_ratio']['as_of'],'2026-06-30')

    def test_nonzero_convertible_does_not_consume_next_row_serial(self):
        pages=[s.replace('可转债（可交换债） - -','可转债（可交换债） 45.40 4.54') for s in self.report()]
        self.assertEqual(parse_periodic_report(pages,'2026-10-18','s','000000')[0]['convertible_pct']['value'],4.54)

    def test_wrong_share_future_or_conflicting_report_date_is_rejected(self):
        self.assertFalse(parse_periodic_report(self.report(),'2026-10-18','s','000001')[0])
        self.assertFalse(parse_periodic_report(self.report(),'2026-01-01','s','000000')[0])
        self.assertFalse(parse_periodic_report(self.report()+['报告截止日2025年12月31日'],'2026-10-18','s','000000')[0])

    def test_top_five_bonds_are_not_full_convertible_evidence(self):
        pages=['基金代码000000 报告截止日2026年6月30日 前五名债券投资明细 1 某转债 10.00 1.00']
        self.assertNotIn('convertible_pct',parse_periodic_report(pages,'2026-10-18','s','000000')[0])

    def test_existing_valid_evidence_conflict_stale_and_idempotence(self):
        document={'as_of':'2026-10-18','funds':[{'code':'000000','metrics':{
            'annual_fee_pct':{'value':.3,'as_of':'2026-10-17','source':'manual'}}}]}
        cached={'code':'000000','metrics':{
            'annual_fee_pct':{'value':.6,'as_of':'2026-10-18','source':'s'},
            'convertible_pct':{'value':0,'as_of':'2026-06-30','source':'s','basis':'net_assets'},
            'duration_years':{'value':2,'as_of':'2020-01-01','source':'s'}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps(cached),encoding='utf-8')
            result=enrich_supplemental(document,tmp);fund=result['funds'][0]
            self.assertEqual(fund['metrics']['annual_fee_pct']['value'],.3)
            self.assertEqual(fund['metrics']['convertible_pct']['value'],0)
            self.assertNotIn('duration_years',fund['metrics'])
            self.assertNotIn('context',document['funds'][0])
            self.assertEqual(result,enrich_supplemental(result,tmp))
            self.assertIn('来源存在差异',render_source_audit(fund['context']))

    def test_source_date_and_publication_cannot_leak_future_evidence(self):
        doc={'as_of':'2026-10-18','funds':[{'code':'000000'}]}
        cached={'code':'000000','metrics':{'annual_fee_pct':{'value':.3,'as_of':'2026-10-19','source':'s'},
            'equity_pct':{'value':0,'as_of':'2026-06-30','published_at':'2026-10-19','basis':'net_assets','source':'s'}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps(cached),encoding='utf-8')
            result=enrich_supplemental(doc,tmp)
            self.assertFalse(result['funds'][0]['metrics'])

    def test_collector_only_accepts_public_code_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):PublicCollector().collect('../secret','2026-10-18',tmp)

    def test_offline_refresh_preserves_prior_dated_evidence_and_records_failures(self):
        old={'code':'000000','analysis_as_of':'2026-10-17','metrics':{
            'annual_fee_pct':{'value':.3,'as_of':'2026-10-17','source':'s'}},'sources':{}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps(old),encoding='utf-8')
            with patch.object(PublicCollector,'fetch',side_effect=TimeoutError('synthetic offline')):
                result=PublicCollector().collect('000000','2026-10-18',tmp,True)
            self.assertEqual(result['metrics'],old['metrics'])
            self.assertEqual(result['sources']['fees']['status'],'error')

    def test_manager_report_precedes_same_date_platform_but_keeps_old_evidence(self):
        old={'value':10,'as_of':'2026-06-30','source':'https://danjuanfunds.com/example','basis':'net_assets'}
        candidate=dict(old,value=12,source='https://pdf.dfcfw.com/example',evidence_type='manager_periodic_report')
        document={'as_of':'2026-10-18','funds':[{'code':'000000','metrics':{'equity_pct':old}}]}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{'equity_pct':candidate}}),encoding='utf-8')
            result=enrich_supplemental(document,tmp)
            self.assertEqual(result['funds'][0]['metrics']['equity_pct']['value'],12)
            self.assertEqual(result['funds'][0]['context']['supplemental_audit'][0]['previous'],old)
            self.assertEqual(result,enrich_supplemental(result,tmp))

    def test_full_equity_table_uses_same_report_denominator_and_skips_fund_investment(self):
        values=[10000-i*100 for i in range(10)]
        pages=['基金代码000000 报告截止日2026年6月30日\n6.1 资产负债表\n其中：股票投资 200,000.00 100,000.00\n基金投资 - -\n资产总计 300,000.00 200,000.00\n净资产合计 250,000.00 200,000.00\n6.2 利润表\n7.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细\n序号 公允价值 占基金资产净值比例（%）\n'+''.join(f'{i+1} 合成股票 {v:,.2f} {v/250000*100:.2f}\n' for i,v in enumerate(values))+'7.4 报告期内股票投资组合的重大变动']
        metrics,_=parse_periodic_report(pages,'2026-10-18','s','000000')
        self.assertAlmostEqual(metrics['top10_equity_pct']['value'],sum(values)/200000*100)
        pages=[s.replace('基金投资 - -','基金投资 10,000.00 1,000.00') for s in pages]
        self.assertNotIn('top10_equity_pct',parse_periodic_report(pages,'2026-10-18','s','000000')[0])

    def test_partial_qdii_list_is_not_treated_as_global_top_ten(self):
        row={'code':'000000','qdii':True,'metrics':{'top10_equity_pct':{
            'value':10,'as_of':'2026-06-30','source':'https://danjuanfunds.com/example',
            'basis':'equity_assets','complete':True}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{}}),encoding='utf-8')
            result=enrich_supplemental({'as_of':'2026-10-18','funds':[row]},tmp)
            self.assertNotIn('top10_equity_pct',result['funds'][0]['metrics'])
            self.assertEqual(result,enrich_supplemental(result,tmp))

    def test_both_report_entrypoints_accept_supplemental_cache(self):
        from scripts.operation_report import generate as operation
        from scripts.research_report import generate as research
        document={'as_of':'2026-10-18','holdings_as_of':'2026-10-17','funds':[{'code':'000000','profile':'bond'}]}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{
                'convertible_pct':{'value':0,'as_of':'2026-06-30','source':'s','basis':'net_assets'}}}),encoding='utf-8')
            h,j=research(document,Path(tmp)/'scores',supplemental_data_dir=tmp)
            result=json.loads(j.read_text(encoding='utf-8'))
            self.assertEqual(result['funds'][0]['coverage_pct'],20)
            output=operation(document,Path(tmp)/'result.html',tmp).read_text(encoding='utf-8')
            self.assertIn('补源记录与来源差异',output)
            self.assertIn('持仓记录：2026-10-17',output)


if __name__=='__main__':unittest.main()
