"""资金估算、缺失语义与离线呈现的独立检验；不测试获利能力。"""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.capital_flow_data import PublicClient, build_direction, daily_estimate, fetch_market_flow, national_quantity_bounds, parse_market_flow, parse_szse_xlsx, window_stats
from scripts.capital_flow_report import render


class CapitalFlowTests(unittest.TestCase):
    def test_market_snapshot_is_one_day_not_history(self):
        doc={"rc":0,"data":{"code":"510300","klines":["2026-10-27,-860610576,507763565,352847008,149916288,-1010526864"]}}
        rows=parse_market_flow(doc,"510300","2026-10-27")
        self.assertEqual(list(rows),["2026-10-27"])
        self.assertAlmostEqual(rows["2026-10-27"]["flow"],-8.60610576)
        self.assertIsNone(rows["2026-10-27"]["ratio"])
        self.assertEqual(parse_market_flow(doc,"510330","2026-10-27"),{})
        self.assertEqual(parse_market_flow(doc,"510300","2026-10-26"),{})
        self.assertEqual(parse_market_flow({**doc,"rc":100},"510300","2026-10-27"),{})

    def test_failed_history_uses_snapshot_without_zero_filling(self):
        class Client:
            def __init__(self):self.calls=[]
            def json(self,url,*args):
                self.calls.append(url)
                return None if len(self.calls)==1 else {"data":{"code":"510300","klines":["2026-10-27,100000000,0,0,0,0"]}}
        c=Client();rows=fetch_market_flow(c,"510300","2026-10-27")
        self.assertEqual(len(c.calls),2)
        self.assertEqual(rows["2026-10-27"]["flow"],1)
        self.assertIsNone(window_stats(rows,["2026-10-21","2026-10-22","2026-10-23","2026-10-26","2026-10-27"],5)["value"])

    def test_country_bound_is_quantity_only_and_requires_no_split_and_published_evidence(self):
        row={"huijin_investment_shares":60,"huijin_asset_shares":30,"current_total_shares":20,"split_change":0,
             "previous_source":{"published_at":"2026-03-31"},"current_source":{"published_at":"2026-08-31"}}
        evidence={"as_of":"2026-06-30","rows":[row]}
        self.assertIsNone(national_quantity_bounds(evidence,"2026-07-01"))
        result=national_quantity_bounds(evidence,"2026-10-27")["rows"][0]
        self.assertEqual(result["minimum_decrease_shares"],70)
        self.assertIsNone(result["current_confirmed_shares"])
        row["split_change"]=None
        self.assertIsNone(national_quantity_bounds(evidence,"2026-10-27")["rows"][0]["minimum_decrease_shares"])

    def test_price_change_is_not_subscription(self):
        # 价格翻倍、份额不变，净申购仍为0；资产规模差法会错误地算出1亿元。
        self.assertEqual(daily_estimate(100_000_000,100_000_000,2,1),(0,None))

    def test_estimate_and_redemption_have_correct_units(self):
        self.assertAlmostEqual(daily_estimate(100_000_000,150_000_000,2)[0],1)
        self.assertAlmostEqual(daily_estimate(150_000_000,100_000_000,2)[0],-1)
        self.assertIsNone(daily_estimate(None,0,2)[0])

    def test_possible_split_is_not_money_flow(self):
        self.assertIsNone(daily_estimate(100_000_000,200_000_000,1,2)[0])

    def test_missing_day_does_not_shorten_or_zero_fill_window(self):
        days=["2026-10-21","2026-10-22","2026-10-23","2026-10-26","2026-10-27"]
        rows={d:{"flow":0} for d in days}
        self.assertEqual(window_stats(rows,days,5)["value"],0)
        rows.pop(days[2])
        self.assertIsNone(window_stats(rows,days,5)["value"])
        self.assertEqual(window_stats(rows,days,5)["valid"],4)
        self.assertIsNone(window_stats(rows,days,20)["value"])

    def test_aggregate_uses_each_products_own_nav_and_strict_coverage(self):
        day="2026-10-27"
        def product(flow,market,base):
            return {"daily":{day:{"flow":flow,"market_flow":market,"previous_aum":base,"aum":base}}}
        # 两产品份额同增1亿份，净值1元与10元，合计11亿元，而非22或2亿元。
        rows={"a":product(1,5,10),"b":product(10,-3,100)}
        out=build_direction({"codes":["a","b"]},rows,[day])
        self.assertEqual(out["windows"]["1"]["value"],11)
        self.assertEqual(out["windows"]["1"]["intensity"],10)
        self.assertEqual(out["market_windows"]["1"]["value"],2)
        rows["b"]["daily"][day]["flow"]=None
        self.assertIsNone(build_direction({"codes":["a","b"]},rows,[day])["windows"]["1"]["value"])

    def test_exchange_xlsx_with_wrong_dimension_is_fully_read(self):
        xml='''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1"/><sheetData><row r="2"><c r="A2" t="inlineStr"><is><t>2026-10-27</t></is></c><c r="B2" t="inlineStr"><is><t>159919  </t></is></c><c r="C2" t="inlineStr"><is><t>沪深300ETF嘉实</t></is></c><c r="D2" t="inlineStr"><is><t>100,000,000.00</t></is></c></row></sheetData></worksheet>'''
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            z.writestr("xl/worksheets/sheet1.xml",xml)
        out=parse_szse_xlsx(buf.getvalue())
        self.assertEqual(out["2026-10-27"]["159919"]["shares"],100_000_000)

    def test_offline_does_not_make_a_network_request(self):
        base=Path(__file__).resolve().parents[1]/".pytest_cache"
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as d,patch("urllib.request.urlopen",side_effect=AssertionError("network")):
            c=PublicClient(d,offline=True)
            self.assertIsNone(c.get("https://example.com",{},"https://example.com","missing.json"))
            self.assertEqual(c.audit[0]["mode"],"缓存缺失")

    def test_html_escapes_script_termination_and_has_no_remote_dependencies(self):
        content=render({"schema":"capital-flow-v1","name":"</script><script>alert(1)</script>"})
        self.assertNotIn('"name":"</script>',content)
        self.assertIn(r"\u003c/script\u003e",content)
        self.assertNotIn("<script src=",content)
        self.assertNotIn("fetch(",content)
        self.assertNotIn("__CAPITAL_FLOW_JSON__",content)


if __name__ == "__main__":
    unittest.main()
