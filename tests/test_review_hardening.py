import json
from pathlib import Path
import tempfile
import unittest

from scripts.public_data_sources import enrich_supplemental, parse_periodic_report, render_source_audit, PublicCollector
from scripts.research_evidence import current_team_tenure
from scripts.research_scoring import score_fund
from scripts.operation_report import render


class ReviewHardeningTests(unittest.TestCase):
    def test_public_evidence_refreshes_before_old_ttl_and_is_idempotent(self):
        old={'value':.3,'as_of':'2026-10-17','source':'https://fundf10.eastmoney.com/test'}
        candidate=dict(old,as_of='2026-10-18')
        document={'as_of':'2026-10-18','funds':[{'code':'000000','metrics':{'annual_fee_pct':old}}]}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{'annual_fee_pct':candidate}}),encoding='utf-8')
            result=enrich_supplemental(document,tmp)
            self.assertEqual(result['funds'][0]['metrics']['annual_fee_pct']['as_of'],'2026-10-18')
            self.assertEqual(result['funds'][0]['context']['supplemental_audit'][0]['status'],'replaced_fresher')
            self.assertEqual(result,enrich_supplemental(result,tmp))

    def test_bad_cache_does_not_drop_the_rest_of_the_portfolio(self):
        document={'as_of':'2026-10-18','funds':[{'code':'000000'},{'code':'000001'}]}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text('broken',encoding='utf-8')
            (Path(tmp)/'000001.json').write_text(json.dumps({'code':'000001','metrics':{'annual_fee_pct':{'value':.3,'as_of':'2026-10-18','source':'s'}}}),encoding='utf-8')
            result=enrich_supplemental(document,tmp)
            self.assertEqual(len(result['funds']),2)
            self.assertIn('缓存损坏',result['funds'][0]['context']['data_gaps'][0])
            self.assertEqual(result['funds'][1]['metrics']['annual_fee_pct']['value'],.3)

    def test_invalid_candidate_and_publication_are_rejected_without_render_crash(self):
        document={'as_of':'2026-10-18','funds':[{'code':'000000'}]}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'000000.json').write_text(json.dumps({'code':'000000','metrics':{'annual_fee_pct':42}}),encoding='utf-8')
            result=enrich_supplemental(document,tmp)
            self.assertIn('未通过',render_source_audit(result['funds'][0]['context']))
        row={'code':'000000','profile':'bond','metrics':{'annual_fee_pct':{'value':.3,'as_of':'2026-10-18','source':'s','published_at':42}}}
        self.assertIsNone(score_fund(row,'2026-10-18')['reference_score'])

    def test_wrong_cache_identity_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'000000.json';path.write_text(json.dumps({'code':'000001'}),encoding='utf-8')
            with self.assertRaises(ValueError):PublicCollector().collect('000000','2026-10-18',tmp)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['code'],'000001')

    def test_report_identity_does_not_come_from_a_stock_holding(self):
        text='基金代码000001 报告截止日2026年6月30日 股票投资明细 证券代码000000'
        self.assertFalse(parse_periodic_report([text],'2026-10-18','s','000000')[0])
        # 主代码和同产品多个份额代码均可明确匹配；不会被拼成一个长代码。
        text='基金主代码 000001\n下属分级基金的交易代码 000001 000000\n报告截止日2026年6月30日\n6.1 资产负债表\n资产总计 120.00 100.00\n净资产合计 100.00 90.00\n6.2 利润表'
        self.assertEqual(parse_periodic_report([text],'2026-10-18','s','000000')[0]['gross_assets_ratio']['value'],1.2)

    def test_former_manager_is_not_used_as_current_continuous_tenure(self):
        info={'manager_name':'甲'}
        detail={'manager_list':[{'name':'甲','achievement_list':[{'fund_code':'000000','post_date':'2020-01-01','resi_date':'2025-01-01'}]}]}
        self.assertIsNone(current_team_tenure(info,detail,'000000','2026-10-18','s'))

    def test_operation_report_management_remains_conditional(self):
        d={'as_of':'2026-10-18','funds':[{'code':'000000','profile':'bond','market_value':100}]}
        self.assertNotIn('<h2>组合管理核对</h2>',render(d))
        d['management_review']=True
        html=render(d)
        self.assertIn('<h2>组合管理核对</h2>',html)
        self.assertIn('未设置已确认目标比例',html)


if __name__=='__main__':unittest.main()
