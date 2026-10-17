"""新模型的证据处理、分型、部分评分及离线报告契约。只用合成数据。"""
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.research_scoring import WEIGHTS, score_fund, score_document
from scripts.research_report import generate, render_html

AS_OF='2026-10-17'
def evidence(value,**kwargs):
    return dict(value=value,as_of=AS_OF,source='https://example.org/synthetic',**kwargs)
def fund(profile='active_equity',metrics=None):
    return dict(code='000000',name='合成测试产品',profile=profile,metrics=metrics or {})

class ResearchScoringTests(unittest.TestCase):
    def test_weights_sum_and_zero_is_real(self):
        for weights in WEIGHTS.values():self.assertEqual(sum(weights.values()),100)
        r=score_fund(fund(metrics={'annual_fee_pct':evidence(0)}),AS_OF)
        self.assertEqual(r['reference_score'],100)
        self.assertEqual(r['coverage_pct'],15)
        self.assertEqual(r['missing_weight_range'],[15,100])

    def test_real_zero_score_survives(self):
        r=score_fund(fund(metrics={'annual_fee_pct':evidence(3)}),AS_OF)
        self.assertEqual(r['reference_score'],0)
        self.assertEqual(r['missing_weight_range'],[0,85])

    def test_missing_not_imputed_and_formula(self):
        r=score_fund(fund(metrics={'annual_fee_pct':evidence(1.4),
             'drawdown_1y_pct':evidence(20,period_days=365)}),AS_OF)
        self.assertEqual(r['reference_score'],60)
        self.assertEqual(r['coverage_pct'],45)
        self.assertEqual(r['missing_weight_range'],[27,82])
        self.assertIsNone(r['dimensions'][2]['score'])
        self.assertIsNone(r['position_advice'])

    def test_empty_has_no_number(self):
        r=score_fund(fund(),AS_OF)
        self.assertIsNone(r['reference_score']);self.assertEqual(r['coverage_pct'],0)

    def test_bad_numbers_dates_and_sources_do_not_score(self):
        for value in [None,True,float('nan'),float('inf'),-1,21,'0.3']:
            with self.subTest(value=value):
                self.assertIsNone(score_fund(fund(metrics={'annual_fee_pct':evidence(value)}),AS_OF)['reference_score'])
        for extra in [{'as_of':'2028-01-01'},{'as_of':'2020-01-01'},{'as_of':'bad'},{'source':''}]:
            item=evidence(.3);item.update(extra)
            self.assertIsNone(score_fund(fund(metrics={'annual_fee_pct':item}),AS_OF)['reference_score'])

    def test_profiles_have_different_risk_and_cost_rules(self):
        m={'drawdown_1y_pct':evidence(3,period_days=365)}
        self.assertLess(score_fund(fund('bond',m),AS_OF)['reference_score'],score_fund(fund('active_equity',m),AS_OF)['reference_score'])
        with self.assertRaises(ValueError):score_fund(fund('unknown'),AS_OF)

    def test_short_drawdown_sample_does_not_look_safe(self):
        self.assertIsNone(score_fund(fund(metrics={'drawdown_1y_pct':evidence(0,period_days=100)}),AS_OF)['reference_score'])

    def test_invalid_period_metadata_is_missing_not_crash(self):
        for days in ['365',True,float('inf'),-1]:
            item=evidence(3,period_days=days)
            self.assertIsNone(score_fund(fund(metrics={'drawdown_1y_pct':item}),AS_OF)['reference_score'])

    def test_same_known_scores_remain_inside_missing_bounds(self):
        partial=score_fund(fund(metrics={'annual_fee_pct':evidence(1.4)}),AS_OF)
        for value in [0,10,20,35,50]:
            r=score_fund(fund(metrics={'annual_fee_pct':evidence(1.4),'drawdown_1y_pct':evidence(value,period_days=365)}),AS_OF)
            self.assertGreaterEqual(r['missing_weight_range'][0],partial['missing_weight_range'][0])
            self.assertLessEqual(r['missing_weight_range'][1],partial['missing_weight_range'][1])

    def test_invalid_document_code_and_date(self):
        for code in [123456,'１２３４５６',[], '123']:
            row=fund();row['code']=code
            with self.assertRaises(ValueError):score_document(dict(as_of=AS_OF,funds=[row]))
        with self.assertRaises(ValueError):score_document(dict(as_of='bad',funds=[fund()]))

    def test_bond_credit_unknown_not_zero_and_net_basis_required(self):
        m={'annual_fee_pct':evidence(.3),'lower_credit_pct':evidence(0)}
        r=score_fund(fund('bond',m),AS_OF)
        self.assertEqual(r['coverage_pct'],15)
        m['lower_credit_pct']['basis']='net_assets'
        self.assertEqual(score_fund(fund('bond',m),AS_OF)['coverage_pct'],35)

    def test_concentration_requires_equity_denominator_and_complete_list(self):
        m={'top10_equity_pct':evidence(30,basis='net_assets',complete=True)}
        self.assertIsNone(score_fund(fund(metrics=m),AS_OF)['reference_score'])
        m['top10_equity_pct']['basis']='equity_assets'
        self.assertEqual(score_fund(fund(metrics=m),AS_OF)['reference_score'],90)

    def test_benchmark_and_tracking_require_full_identity(self):
        flags=dict(benchmark_verified=True,dates_aligned=True,currency_matched=True,total_return=True,period_days=1095)
        for missing in flags:
            item=evidence(10,**flags);item.pop(missing)
            r=score_fund(fund(metrics={'benchmark_excess_3y_pct':item}),AS_OF)
            self.assertIsNone(r['reference_score'])
        r=score_fund(fund(metrics={'benchmark_excess_3y_pct':evidence(10,**flags)}),AS_OF)
        self.assertEqual(r['reference_score'],75)
        item=evidence(.5,**flags,frequency='weekly',observations=220)
        self.assertIsNone(score_fund(fund('index',{'tracking_error_1y_pct':item}),AS_OF)['reference_score'])
        item['frequency']='daily'
        self.assertEqual(score_fund(fund('index',{'tracking_error_1y_pct':item}),AS_OF)['reference_score'],90)

    def test_valuation_requires_real_target_and_history(self):
        for extra in [{},{'target_verified':True,'history_years':2}]:
            self.assertIsNone(score_fund(fund('index',{'valuation_percentile':evidence(20,**extra)}),AS_OF)['reference_score'])
        self.assertEqual(score_fund(fund('index',{'valuation_percentile':evidence(20,target_verified=True,history_years=10)}),AS_OF)['reference_score'],80)

    def test_qdii_is_overlay_not_new_prediction(self):
        f=fund(metrics={'annual_fee_pct':evidence(.6,verified=True)});f['qdii']=True
        r=score_fund(f,AS_OF)
        self.assertEqual(r['verified_coverage_pct'],15)
        self.assertTrue(any('QDII' in x for x in r['flags']))

    def test_portfolio_keeps_unscorable_cash_and_market_value_coverage(self):
        f=fund(metrics={'annual_fee_pct':evidence(0)});f['market_value']=20
        cash=dict(code=None,name='未确认现金',profile=None,market_value=80)
        r=score_document(dict(as_of=AS_OF,funds=[f,cash]))
        self.assertEqual(len(r['funds']),2)
        self.assertEqual(r['summary']['scored_value_share_pct'],20)
        self.assertEqual(r['summary']['evidence_weighted_value_coverage_pct'],3)
        self.assertIsNone(r['summary']['aggregate_score'])
        cash['market_value']=None
        self.assertFalse(score_document(dict(as_of=AS_OF,funds=[f,cash]))['summary']['all_values_known'])

    def test_duplicates_and_invalid_market_values_rejected(self):
        with self.assertRaises(ValueError):score_document(dict(as_of=AS_OF,funds=[fund(),fund()]))
        for value in [-1,True,float('nan')]:
            f=fund();f['market_value']=value
            with self.assertRaises(ValueError):score_document(dict(as_of=AS_OF,funds=[f]))

    def test_offline_report_escapes_input_and_displays_zero(self):
        f=fund(metrics={'annual_fee_pct':evidence(3)});f['name']='<script>alert(1)</script>'
        f['metrics']['annual_fee_pct']['source']='javascript:alert(2)'
        r=score_document(dict(as_of=AS_OF,funds=[f]))
        content=render_html(r)
        self.assertNotIn('<script>alert(1)',content)
        self.assertNotIn('href="javascript:',content)
        self.assertIn('0.0分',content)
        self.assertNotIn('fetch(',content)
        with tempfile.TemporaryDirectory() as directory:
            h,j=generate(dict(as_of=AS_OF,funds=[f]),directory)
            self.assertTrue(h.exists());self.assertEqual(json.loads(j.read_text(encoding='utf-8'))['summary']['scored_count'],1)

    def test_invalid_evidence_still_generates_strict_json_report(self):
        f=fund(metrics={'annual_fee_pct':evidence(float('nan')),'drawdown_1y_pct':evidence(3,period_days=float('inf'))})
        f['metrics']['annual_fee_pct']['source']=123
        with tempfile.TemporaryDirectory() as directory:
            h,j=generate(dict(as_of=AS_OF,funds=[f]),directory)
            data=json.loads(j.read_text(encoding='utf-8'))
            self.assertIsNone(data['funds'][0]['reference_score'])
            self.assertNotIn('NaN',j.read_text(encoding='utf-8'))
            self.assertTrue(h.exists())

if __name__=='__main__':unittest.main()
