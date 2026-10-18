"""独立试跑发现的序号漏读、限流与原文缓存回退回归。全部使用合成数据。"""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from scripts.public_data_sources import (PublicCollector,SourceRateLimited,
    parse_periodic_report,enrich_supplemental,REPORT_PARSER_VERSION,render_source_audit)
from scripts.operation_report import disclosed_exposures


def report_rows(missing=None,duplicate=False):
    rows=[]
    for rank in range(1,21):
        if rank==missing:continue
        amount=200000-rank*5000
        money=f'{amount:,.2f}'
        # 同一页既有小数点前换行，也有小数点后换行（小数00不得误作序号）。
        if rank<5:money=money.replace('.', '\n.')
        elif rank<10:money=money.replace('.', '.\n')
        serial=1 if duplicate and rank==2 else rank
        rows.append(f'{serial} 合成证券 {money} {amount/4000000*100:.2f}\n')
    return ['基金代码000000 报告截止日2026年6月30日\n6.1 资产负债表\n'
            '其中：股票投资 3,000,000.00 2,000,000.00\n基金投资 - -\n'
            '资产总计 4,200,000.00 3,000,000.00\n净资产合计 4,000,000.00 3,000,000.00\n6.2 利润表\n'
            '7.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细\n'
            '序号 公允价值 占基金资产净值比例（%）\n'+''.join(rows)+
            '7.4 报告期内股票投资组合的重大变动']


class SourceTrialRegressions(unittest.TestCase):
    def test_wrapped_leading_amounts_are_not_skipped_for_later_rows(self):
        metrics,_=parse_periodic_report(report_rows(),'2026-10-18','s','000000')
        item=metrics['top10_equity_pct']
        self.assertAlmostEqual(item['value'],sum(200000-i*5000 for i in range(1,11))/3000000*100)
        self.assertEqual(item['top10_ranks'],list(range(1,11)))
        self.assertEqual(item['parser_version'],REPORT_PARSER_VERSION)

    def test_missing_or_duplicate_rank_cannot_be_replaced_by_later_valid_rows(self):
        for pages in (report_rows(missing=1),report_rows(missing=5),report_rows(duplicate=True)):
            metrics,notes=parse_periodic_report(pages,'2026-10-18','s','000000')
            self.assertNotIn('top10_equity_pct',metrics)
            self.assertTrue(any('序号' in n for n in notes))

    def test_standalone_rank_and_glued_quantity_across_pages(self):
        pages=report_rows()
        for rank in range(1,11):
            pages[0]=pages[0].replace(f'{rank} 合成证券 ',f'{rank}\n合成证券 10,000.00')
        pages[0]=pages[0].replace('6\n合成证券','合成中报\n第44页 共60页\n6\n合成证券')
        metrics,_=parse_periodic_report(pages,'2026-10-18','s','000000')
        self.assertEqual(metrics['top10_equity_pct']['top10_ranks'],list(range(1,11)))

    def test_rate_limit_stops_host_without_retry_and_other_host_continues(self):
        for status in (429,514):
            collector=PublicCollector(min_interval=0)
            response=MagicMock()
            response.__enter__.return_value.read.return_value=b'ok'
            with patch.object(collector.opener,'open',side_effect=[HTTPError('u',status,'limited',{},io.BytesIO()),response]) as request:
                with self.assertRaises(SourceRateLimited):collector.fetch('https://one.example/a')
                with self.assertRaises(SourceRateLimited):collector.fetch('https://one.example/b')
                self.assertEqual(collector.fetch('https://two.example/a'),b'ok')
                self.assertEqual(request.call_count,2)

    def test_per_host_pacing_and_non_retryable_error(self):
        collector=PublicCollector(min_interval=1)
        response=MagicMock();response.__enter__.return_value.read.return_value=b'ok'
        with patch.object(collector.opener,'open',return_value=response),patch('scripts.public_data_sources.time.monotonic',return_value=10),patch('scripts.public_data_sources.time.sleep') as sleep:
            collector.fetch('https://one.example/a');collector.fetch('https://one.example/b')
            sleep.assert_called_once_with(1)
        with patch.object(collector.opener,'open',side_effect=HTTPError('u',404,'missing',{},None)) as request:
            with self.assertRaises(HTTPError):collector.fetch('https://two.example/a')
            self.assertEqual(request.call_count,1)

    def test_offline_index_and_original_pdf_are_reparsed_not_old_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            index={'Data':[{'FUNDCODE':'000000','PUBLISHDATEDesc':'2026-08-31','TITLE':'2026年中期报告','ID':'AN123'}]}
            (root/'000000_report_index.json').write_text(json.dumps(index),encoding='utf-8')
            (root/'000000_AN123.pdf').write_bytes(b'synthetic pdf')
            old={'code':'000000','collector_version':'public-sources-v3','metrics':{'top10_equity_pct':{'value':1}},'sources':{}}
            (root/'000000.json').write_text(json.dumps(old),encoding='utf-8')
            fake=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:report_rows()[0])])
            with patch.object(PublicCollector,'fetch',side_effect=TimeoutError('offline')),patch('pypdf.PdfReader',return_value=fake):
                result=PublicCollector().collect('000000','2026-10-18',root)
            self.assertGreater(result['metrics']['top10_equity_pct']['value'],50)
            self.assertEqual(result['sources']['report_index']['status'],'cached')
            self.assertEqual(result['sources']['periodic_report']['status'],'cached')
            self.assertEqual(result['metrics']['top10_equity_pct']['as_of'],'2026-06-30')
            self.assertEqual(result['metrics']['top10_equity_pct']['published_at'],'2026-08-31')
            history=next(h for h in result['metric_history'] if h['metric']=='top10_equity_pct')
            self.assertEqual(history['previous']['value'],1)

    def test_legacy_auto_concentration_is_retired_but_manual_is_preserved(self):
        old={'value':40,'as_of':'2026-06-30','source':'https://pdf.dfcfw.com/example',
             'basis':'equity_assets','complete':True,'evidence_type':'manager_periodic_report'}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{'top10_equity_pct':old}}),encoding='utf-8')
            doc={'as_of':'2026-10-18','funds':[{'code':'000000','metrics':{'top10_equity_pct':old}}]}
            result=enrich_supplemental(doc,tmp)
            self.assertNotIn('top10_equity_pct',result['funds'][0]['metrics'])
            self.assertEqual(enrich_supplemental(result,tmp),result)
            doc['funds'][0]['metrics']['top10_equity_pct']=dict(old,manual=True)
            self.assertEqual(enrich_supplemental(doc,tmp)['funds'][0]['metrics']['top10_equity_pct']['value'],40)

    def test_source_failures_visible_without_successful_metric_audit(self):
        out=render_source_audit({'supplemental_sources':{'fees':{'status':'rate_limited','error':'HTTP 514'},'periodic_report':{'status':'cached'}}})
        self.assertIn('HTTP 514',out)
        self.assertIn('非本次实时确认',out)

    def test_actual_exposures_visible_outside_scoring_and_future_hidden(self):
        fund={'metrics':{'convertible_pct':{'value':15.75,'as_of':'2026-06-30','source':'s','basis':'net_assets'},
                         'equity_pct':{'value':99,'as_of':'2026-12-31','source':'s','basis':'net_assets'}}}
        out=disclosed_exposures(fund,'2026-10-18')
        self.assertIn('15.75%',out)
        self.assertNotIn('99.00%',out)

    def test_old_automatic_concentration_is_rejected_without_supplemental_loader(self):
        from datetime import date
        from scripts.research_scoring import validate_evidence
        old={'value':40,'as_of':'2026-06-30','source':'s','basis':'equity_assets',
             'complete':True,'evidence_type':'manager_periodic_report'}
        self.assertIsNotNone(validate_evidence('top10_equity_pct',old,date(2026,10,18)))
        self.assertIsNone(validate_evidence('top10_equity_pct',dict(old,manual=True),date(2026,10,18)))


if __name__=='__main__':unittest.main()
