import json
from pathlib import Path
import re
import tempfile
import unittest

from scripts.operation_report import generate, nav_chart, normalize_action, render


class OperationReportTests(unittest.TestCase):
    def document(self):
        return {'as_of':'2026-10-17','report_date':'2026-10-18','funds':[
          {'code':'000000','name':'合成产品','profile':'active_equity','market_value':100,
           'metrics':{'annual_fee_pct':{'value':3,'as_of':'2026-10-17','source':'synthetic'}},
           'operation_analysis':{'stance':'暂停新增，复核用途','priority':'P1','reasons':['合成重复风险证据'],'next_step':'先核本人可赎日与费用。'}}]}

    def test_single_html_is_only_output_and_all_data_is_embedded(self):
        document=self.document()
        with tempfile.TemporaryDirectory() as directory:
            path=generate(document,Path(directory)/'result.html')
            self.assertEqual([p.name for p in Path(directory).iterdir()],['result.html'])
            text=path.read_text(encoding='utf-8')
            raw=re.search(r'<script type="application/json" id="embedded-research">(.*?)</script>',text,re.S)[1]
            data=json.loads(raw)
            self.assertEqual(data['input'],document)
            self.assertEqual(data['scores']['funds'][0]['reference_score'],0)
            self.assertNotIn('fetch(',text)
            self.assertNotRegex(text,r'<(?:script|img)[^>]+src=')

    def test_missing_action_does_not_turn_low_score_into_sell(self):
        fund=self.document()['funds'][0];fund.pop('operation_analysis')
        self.assertEqual(normalize_action(fund)['stance'],'观察，先核用途')
        self.assertNotIn('清仓',normalize_action(fund)['next_step'])

    def test_action_conditions_and_evidence_are_all_present(self):
        text=render(self.document())
        for heading in ['先看操作结论','组合处理优先级','四种操作方案比较','考虑新增的条件','考虑减持/退出的条件','交易节奏与费用检查','参考评分、覆盖率与缺口']:
            self.assertIn(heading,text)
        self.assertIn('暂停新增，复核用途',text)
        self.assertIn('1项持仓操作总览',text)

    def test_untrusted_text_cannot_close_embedded_data_or_inject_markup(self):
        document=self.document();payload='</script><img src=x onerror=alert(1)>'
        document['funds'][0]['name']=payload
        document['funds'][0]['operation_analysis']['next_step']=payload
        text=render(document)
        self.assertNotIn(payload,text)
        raw=re.search(r'<script type="application/json" id="embedded-research">(.*?)</script>',text,re.S)[1]
        self.assertEqual(json.loads(raw)['input']['funds'][0]['name'],payload)

    def test_chart_handles_invalid_and_irregular_data_without_daily_claim(self):
        self.assertEqual(nav_chart([{'date':'bad','nav':1}]),'')
        text=nav_chart([{'date':'2026-10-16','nav':2},{'date':'2025-10-01','nav':1},{'date':'2026-10-17','nav':float('inf')}])
        self.assertIn('<svg',text)
        self.assertIn('未复权',text)
        self.assertNotIn('nan',text.lower())

    def test_unknown_cash_kept_and_non_html_rejected(self):
        document=self.document();document['funds'].append({'code':None,'name':'未知现金产品','profile':None,'market_value':None})
        text=render(document)
        self.assertIn('未知现金产品',text)
        self.assertIn('2项持仓操作总览',text)
        with self.assertRaises(ValueError):generate(document,'invalid.json')


if __name__=='__main__':unittest.main()
