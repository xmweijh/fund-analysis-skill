import json
from pathlib import Path
import tempfile
import unittest

from scripts.research_evidence import current_team_tenure, enrich_document
from scripts.research_report import generate

class ResearchEvidenceTests(unittest.TestCase):
    def sample(self):
        info={'manager_name':'甲 乙','found_date':'2025-01-01','fund_derived':{'end_date':'2026-10-16'}}
        detail={'manager_list':[
            {'name':'甲','achievement_list':[{'fund_code':'000000','post_date':'2020-01-01'}]},
            {'name':'乙','achievement_list':[{'fund_code':'000000','post_date':'2025-10-17'}]},
            {'name':'前任','achievement_list':[{'fund_code':'000000','post_date':'2010-01-01'}]}]}
        return info,detail

    def test_complete_current_team_uses_latest_start_not_career_or_old_manager(self):
        info,detail=self.sample()
        result=current_team_tenure(info,detail,'000000','2026-10-17','synthetic')
        self.assertTrue(result['team_complete'])
        self.assertAlmostEqual(result['value'],365/365.25,places=5)
        self.assertEqual(set(result['member_start_dates']),{'甲','乙'})

    def test_missing_member_wrong_share_class_or_future_start_stays_unknown(self):
        for kind in ['missing','class','future']:
            info,detail=self.sample()
            if kind=='missing':detail['manager_list'].pop(1)
            if kind=='class':detail['manager_list'][1]['achievement_list'][0]['fund_code']='000001'
            if kind=='future':detail['manager_list'][1]['achievement_list'][0]['post_date']='2027-01-01'
            self.assertIsNone(current_team_tenure(info,detail,'000000','2026-10-17','synthetic'))

    def test_enrich_preserves_explicit_evidence_adds_performance_and_is_idempotent(self):
        info,detail=self.sample()
        row={'code':'000000','name':'合成','profile':'active_equity','metrics':{'manager_tenure_years':{'value':7,'as_of':'2026-10-17','source':'manual','team_complete':True}}}
        document={'as_of':'2026-10-17','funds':[row]}
        stage={'period_time':'近一年','self_nav':'12.0','self_max_draw_down':'8%','self_nav_rank':'1/2'}
        data={'retrieved_at':'2026-10-17T18:00:00+08:00','sources':{k:{'url':'synthetic','payload':{'data':v}} for k,v in [('info',info),('detail',detail),('achievement',{'stage_performance_list':[stage]}),('growth_3y',{})]}}
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'000000.json').write_text(json.dumps(data),encoding='utf-8')
            result=enrich_document(document,directory)
            self.assertEqual(result['funds'][0]['metrics']['manager_tenure_years']['value'],7)
            self.assertEqual(result['funds'][0]['context']['stage_performance'][0]['self_nav'],'12.0')
            self.assertNotIn('context',document['funds'][0])
            self.assertEqual(enrich_document(result,directory),result)
            h,j=generate(document,Path(directory)/'report',directory)
            text=h.read_text(encoding='utf-8')
            self.assertIn('已有产品资料与业绩',text)
            self.assertIn('12.0',text)
            self.assertTrue(j.exists())

if __name__=='__main__':unittest.main()
