# tests/test_risk_diagnostics.py
import os, sys, pytest
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path: sys.path.insert(0, _root)

from scripts.risk_diagnostics import RiskDiagnostics, RiskReport

def _make_holding(fund_code, fund_name, cost_amount, stored_profit=0.0, fund_type="主动混合"):
    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "cost_amount": cost_amount,
        "stored_profit": stored_profit,
        "fund_type": fund_type,
    }

class TestConcentration:
    def test_high_concentration(self):
        # Top3 占 80% → level = "high"
        holdings = [
            _make_holding("A", "基金A", 40000),
            _make_holding("B", "基金B", 30000),
            _make_holding("C", "基金C", 10000),
            _make_holding("D", "基金D", 5000),
            _make_holding("E", "基金E", 5000),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        assert report.concentration_pct == pytest.approx(80.0 / 90.0 * 100, abs=0.1)
        # 注意：Top3 = 40000+30000+10000 = 80000，总 = 90000
        assert report.concentration_level == "high"

    def test_medium_concentration(self):
        # Top3 占 65% → level = "medium"
        holdings = [
            _make_holding("A", "基金A", 30000),
            _make_holding("B", "基金B", 20000),
            _make_holding("C", "基金C", 15000),
            _make_holding("D", "基金D", 20000),
            _make_holding("E", "基金E", 15000),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        assert report.concentration_level == "medium"

    def test_low_concentration(self):
        # 6只基金，Top3 = 18000+17000+16000 = 51000 / 106000 ≈ 48.1% → level = "low"
        holdings = [
            _make_holding("A", "基金A", 18000),
            _make_holding("B", "基金B", 17000),
            _make_holding("C", "基金C", 16000),
            _make_holding("D", "基金D", 20000),
            _make_holding("E", "基金E", 19000),
            _make_holding("F", "基金F", 16000),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        assert report.concentration_level == "low"

class TestOverlap:
    def test_detects_brand_overlap(self):
        holdings = [
            _make_holding("010826", "大成产业趋势混合A", 10000),
            _make_holding("000628", "大成高鑫股票A", 10000),
            _make_holding("008269", "大成睿享混合A", 10000),
            _make_holding("010372", "大成成长进取混合A", 10000),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        assert len(report.overlap_groups) >= 1
        group = report.overlap_groups[0]
        assert group["brand"] == "大成"
        assert len(group["funds"]) == 4

    def test_no_overlap_below_threshold(self):
        holdings = [
            _make_holding("A", "大成产业趋势混合A", 10000),
            _make_holding("B", "大成高鑫股票A", 10000),
            _make_holding("C", "易方达蓝筹精选", 10000),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        # 大成只有2只，低于阈值3，不报重叠
        assert len(report.overlap_groups) == 0

class TestQdii:
    def test_qdii_low(self):
        # QDII 占总持仓 1.5% → "low"
        holdings = [
            _make_holding("012920", "易方达全球成长(QDII)", 1500, fund_type="QDII"),
            _make_holding("A", "大成混合", 50000),
            _make_holding("B", "景顺混合", 50000),
        ]
        total_all = 101500
        report = RiskDiagnostics().diagnose(holdings, total_portfolio_cost=total_all)
        assert report.qdii_level == "low"
        assert report.qdii_pct == pytest.approx(1500 / total_all * 100, abs=0.1)

    def test_qdii_ok(self):
        holdings = [
            _make_holding("A", "QDII基金", 10000, fund_type="QDII"),
            _make_holding("B", "混合基金", 80000),
        ]
        report = RiskDiagnostics().diagnose(holdings, total_portfolio_cost=90000)
        assert report.qdii_level == "ok"

class TestLossExposure:
    def test_max_loss_and_total(self):
        holdings = [
            _make_holding("A", "大成产业趋势", 12000, stored_profit=-1475.0),
            _make_holding("B", "大成高鑫股票", 26000, stored_profit=-1461.0),
            _make_holding("C", "景顺新兴成长", 29000, stored_profit=615.0),
        ]
        report = RiskDiagnostics().diagnose(holdings)
        assert report.max_loss_fund == "大成产业趋势"
        assert report.max_loss_amount == pytest.approx(-1475.0)
        assert report.total_loss_exposure == pytest.approx(-2936.0)

    def test_no_loss(self):
        holdings = [_make_holding("A", "基金A", 10000, stored_profit=500.0)]
        report = RiskDiagnostics().diagnose(holdings)
        assert report.max_loss_amount == 0.0
        assert report.total_loss_exposure == 0.0

class TestWarnings:
    def test_warnings_generated(self):
        holdings = [
            _make_holding("A", "大成产业趋势", 40000, stored_profit=-1500.0),
            _make_holding("B", "大成高鑫股票", 30000, stored_profit=-1400.0),
            _make_holding("C", "大成睿享混合", 10000),
            _make_holding("D", "大成成长进取", 10000),
        ]
        report = RiskDiagnostics().diagnose(holdings, total_portfolio_cost=300000)
        assert len(report.warnings) >= 1
        warning_text = " ".join(report.warnings)
        assert "集中度" in warning_text or "重叠" in warning_text
