"""默认基础模型与旧模型的行为边界；全为合成数据。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.research_scoring import MODEL_VERSION, LEGACY_VERSION, WEIGHTS, score_fund, score_document
from scripts.research_report import generate, optional_html
from scripts.public_data_sources import PublicCollector, enrich_supplemental, parse_fees

DAY='2026-10-18'

def ev(value,**kw):return dict(value=value,as_of=DAY,source='synthetic',**kw)
def fund(profile='bond',**metrics):return dict(code='000000',profile=profile,metrics=metrics)


class PublicCoreTests(unittest.TestCase):
    def test_two_item_operating_table_preserves_scope_instead_of_inventing_zero(self):
        text='<h4><label>运作费用</label></h4><table><tbody><tr><td>管理费率</td><td>0.15%（每年）</td><td>托管费率</td><td>0.05%（每年）</td></tbody></table>'
        fee=parse_fees(text,DAY,'synthetic')['annual_fee_pct']
        self.assertAlmostEqual(fee['value'],.2)
        self.assertEqual(fee['fee_scope'],'listed_operating_fees')
        self.assertNotIn('销售服务费率',fee['components'])
        self.assertFalse(parse_fees(text.replace('运作费用','其他费用'),DAY,'synthetic'))
        placeholder=text.replace('</tbody>','<td>销售服务费率</td><td>---</td></tbody>')
        self.assertEqual(parse_fees(placeholder,DAY,'synthetic')['annual_fee_pct']['fee_scope'],'listed_operating_fees')
    def test_defaults_to_fixed_basic_dimensions_without_specialist_gaps(self):
        for weights in WEIGHTS.values():self.assertEqual(sum(weights.values()),100)
        row=fund(drawdown_1y_pct=ev(1,period_days=365),annual_fee_pct=ev(.3),
                 gross_assets_ratio=ev(1.1),convertible_pct=ev(0,basis='net_assets'))
        result=score_document(dict(as_of=DAY,funds=[row]))
        self.assertEqual(result['model_version'],MODEL_VERSION)
        self.assertEqual(result['funds'][0]['coverage_pct'],100)
        self.assertNotIn('duration_years',{d['key'] for d in result['funds'][0]['dimensions']})
        self.assertIn('不评价信用质量和久期',result['funds'][0]['score_scope'])

    def test_real_basic_gaps_still_reduce_coverage_and_zero_survives(self):
        r=score_fund(fund(annual_fee_pct=ev(0)),DAY)
        self.assertEqual(r['coverage_pct'],20)
        self.assertEqual(r['reference_score'],100)
        self.assertEqual(r['missing_weight_range'],[20,100])
        self.assertIsNone(score_fund(fund(),DAY)['reference_score'])

    def test_advanced_evidence_is_optional_validated_and_never_changes_score(self):
        row=fund(annual_fee_pct=ev(.3));baseline=score_fund(row,DAY)
        row['metrics'].update(duration_years=ev(3),lower_credit_pct=ev(0,basis='wrong'))
        result=score_fund(row,DAY)
        self.assertEqual(result['reference_score'],baseline['reference_score'])
        self.assertEqual(result['coverage_pct'],baseline['coverage_pct'])
        self.assertEqual([d['key'] for d in result['optional_dimensions']],['duration_years'])
        self.assertFalse(result['optional_dimensions'][0]['included_in_score'])

    def test_index_does_not_claim_tracking_or_valuation_from_basic_score(self):
        r=score_fund(fund('index',drawdown_1y_pct=ev(10,period_days=365),annual_fee_pct=ev(.2)),DAY)
        self.assertEqual(r['coverage_pct'],100)
        self.assertIn('不评价指数便宜程度、跟踪质量',r['score_scope'])
        self.assertEqual(optional_html(r),'')

    def test_money_redemption_needs_nonempty_channel(self):
        for channel in [None,'',42]:
            row=fund('money',redemption_business_days=ev(1,channel=channel))
            self.assertEqual(score_fund(row,DAY)['coverage_pct'],0)
        row=fund('money',redemption_business_days=ev(1,channel='合成渠道普通赎回'))
        self.assertEqual(score_fund(row,DAY)['coverage_pct'],60)

    def test_legacy_retains_original_weights_and_results(self):
        row=fund('active_equity',annual_fee_pct=ev(1.4),drawdown_1y_pct=ev(20,period_days=365))
        result=score_document(dict(as_of=DAY,funds=[row],scoring_model=LEGACY_VERSION))
        self.assertEqual(result['funds'][0]['coverage_pct'],45)
        self.assertEqual(result['funds'][0]['reference_score'],60)
        self.assertEqual(result['model_version'],LEGACY_VERSION)
        with self.assertRaises(ValueError):score_document(dict(as_of=DAY,funds=[row],scoring_model='unknown'))

    def test_report_actual_model_and_cli_override_do_not_mutate_input(self):
        row=fund('active_equity',annual_fee_pct=ev(3))
        document=dict(as_of=DAY,funds=[row])
        with tempfile.TemporaryDirectory() as tmp:
            h,j=generate(document,tmp,scoring_model=LEGACY_VERSION)
            self.assertIn(LEGACY_VERSION,h.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(j.read_text(encoding='utf-8'))['model_version'],LEGACY_VERSION)
        self.assertNotIn('scoring_model',document)

    def test_fresh_collector_also_populates_platform_drawdown_team_and_context(self):
        info={'manager_name':'甲','found_date':'2020-01-01','fund_derived':{'end_date':'2026-10-16'}}
        detail={'manager_list':[{'name':'甲','achievement_list':[{'fund_code':'000000','post_date':'2020-01-01'}]}]}
        achievement={'stage_performance_list':[{'period_time':'近1年','self_max_draw_down':'2.10%'}]}
        def fetch(url):
            if '/fundx/base/fund/achievement/' in url:return json.dumps({'data':achievement}).encode()
            if '/fund/detail/' in url:return json.dumps({'data':detail}).encode()
            if '/djapi/fund/' in url:return json.dumps({'data':info}).encode()
            if '/JJGG?' in url:return b'{"Data":[]}'
            return b'<table></table>'
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(PublicCollector,'fetch',side_effect=fetch):r=PublicCollector().collect('000000',DAY,tmp)
            self.assertEqual(r['metrics']['drawdown_1y_pct']['value'],2.1)
            self.assertTrue(r['metrics']['manager_tenure_years']['team_complete'])
            merged=enrich_supplemental(dict(as_of=DAY,funds=[fund()]),tmp)
            self.assertEqual(merged['funds'][0]['context']['manager_name'],'甲')


if __name__=='__main__':unittest.main()
