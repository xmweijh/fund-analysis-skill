import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.portfolio_manager import PortfolioManager
from scripts.portfolio_diagnostics import diagnose, render_management


class PortfolioPersistenceTests(unittest.TestCase):
    def test_extra_source_fields_survive_updates_and_unknown_can_be_explicitly_corrected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json'
            path.write_text(json.dumps([{'fund_code':'000000','shares':1,'cost_nav':1.2,'source_record':{'date':'2026-10-17','source':'synthetic'}}]),encoding='utf-8')
            manager=PortfolioManager(str(path));manager.update('000000',shares=2,clear_fields=['cost_nav'])
            saved=json.loads(path.read_text(encoding='utf-8'))[0]
            self.assertIsNone(saved['cost_nav']);self.assertEqual(saved['source_record']['date'],'2026-10-17')
            with self.assertRaises(ValueError):manager.update('000000',clear_fields=['fund_code'])
    def test_corrupt_or_duplicate_source_never_becomes_an_empty_portfolio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json'
            for text in ['not json','{}','[{"fund_code":"000000"},{"fund_code":"000000"}]']:
                path.write_text(text,encoding='utf-8')
                with self.assertRaises(ValueError):PortfolioManager(str(path))
                self.assertEqual(path.read_text(encoding='utf-8'),text)

    def test_updates_preserve_unknown_zero_and_back_up_previous_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json';manager=PortfolioManager(str(path))
            manager.add('000000',shares=0,cost_amount=0)
            old=path.read_bytes();manager.update('000000',shares=12,current_profit=-3)
            self.assertEqual(next(Path(str(path)+'.backups').iterdir()).read_bytes(),old)
            entry=PortfolioManager(str(path)).get('000000')
            self.assertEqual(entry.shares,12);self.assertEqual(entry.current_profit,-3)
            self.assertEqual(entry.cost_amount,0);self.assertIsNone(entry.cost_nav)

    def test_invalid_numbers_do_not_change_disk_or_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json';manager=PortfolioManager(str(path));manager.add('000000',shares=1)
            old=path.read_bytes()
            for value in [-1,True,float('nan'),float('inf')]:
                with self.assertRaises(ValueError):manager.update('000000',shares=value)
                self.assertEqual(path.read_bytes(),old);self.assertEqual(manager.get('000000').shares,1)

    def test_failed_replace_retains_disk_memory_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json';manager=PortfolioManager(str(path));manager.add('000000',shares=1)
            old=path.read_bytes()
            with patch('scripts.portfolio_manager.os.replace',side_effect=OSError('synthetic failure')):
                with self.assertRaises(OSError):manager.update('000000',shares=2)
            self.assertEqual(path.read_bytes(),old);self.assertEqual(manager.get('000000').shares,1)
            self.assertFalse(Path(str(path)+'.lock').exists())

    def test_stale_writer_cannot_overwrite_newer_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'holdings.json';first=PortfolioManager(str(path));first.add('000000',shares=1)
            second=PortfolioManager(str(path));first.update('000000',shares=2)
            with self.assertRaises(RuntimeError):second.update('000000',shares=3)
            self.assertEqual(PortfolioManager(str(path)).get('000000').shares,2)

    def test_returned_records_do_not_mutate_unsaved_state_and_upsert_keeps_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager=PortfolioManager(str(Path(tmp)/'holdings.json'))
            entry=manager.update('000000',shares=0,current_nav=1.2)
            entry.shares=99
            self.assertEqual(manager.get('000000').shares,0)
            self.assertEqual(manager.get('000000').current_nav,1.2)
            self.assertIn('0.00',manager.render_table())


class PortfolioDiagnosticsTests(unittest.TestCase):
    def document(self):
        return {'as_of':'2026-10-18','holdings_as_of':'2026-10-17','base_currency':'CNY','funds':[
            {'code':'000000','market_value':70,'allocation_group':'权益'},
            {'code':'000001','market_value':30,'allocation_group':'债券'}],
            'investment_policy':{'target_allocations_pct':{'权益':60,'债券':40},'targets_confirmed':True,'source':'合成用户决策'}}

    def test_only_explicit_complete_policy_generates_static_target_drift(self):
        r=diagnose(self.document())
        self.assertEqual(r['target_drift'][0]['difference_to_target_value'],-10)
        self.assertIsNone(r['trade_orders'])
        self.assertIn('组合管理核对',render_management(self.document()))

    def test_unknown_values_dates_currency_or_target_block_amount_proposals(self):
        for kind in ['value','date','currency','target','group','source']:
            d=self.document()
            if kind=='value':d['funds'][0]['market_value']=None
            if kind=='date':d['funds'][0]['market_value_as_of']='2026-10-16'
            if kind=='currency':d['funds'][0]['currency']='USD'
            if kind=='target':d['investment_policy']['targets_confirmed']=False
            if kind=='group':d['funds'][0].pop('allocation_group')
            if kind=='source':d['investment_policy'].pop('source')
            self.assertFalse(diagnose(d)['target_drift'],kind)
        d=self.document();d['funds'][0]['currency']='USD'
        self.assertIsNone(diagnose(d)['known_included_value'])

    def test_reserve_exclusion_must_be_explicit_not_inferred_from_fund_name(self):
        d=self.document();d['funds'].append({'code':None,'name':'合成应急金','market_value':100,'allocation_group':'现金'})
        self.assertFalse(diagnose(d)['target_drift'])
        d['funds'][-1]['exclude_from_allocation']=True
        self.assertEqual(diagnose(d)['known_included_value'],100)
        self.assertTrue(diagnose(d)['target_drift'])

    def test_no_policy_does_not_invent_targets_or_shared_underlying(self):
        d=self.document();d.pop('investment_policy')
        for f in d['funds']:f['underlying_id']='synthetic-index'
        r=diagnose(d);self.assertFalse(r['target_drift']);self.assertFalse(r['shared_underlying'])
        for f in d['funds']:f['underlying_verified']=True
        self.assertEqual(len(diagnose(d)['shared_underlying']),1)

    def test_bad_target_sum_and_negative_market_value_are_errors(self):
        d=self.document();d['investment_policy']['target_allocations_pct']['权益']=90
        with self.assertRaises(ValueError):diagnose(d)
        d=self.document();d['funds'][0]['market_value']=-1
        with self.assertRaises(ValueError):diagnose(d)


if __name__=='__main__':unittest.main()
