# tests/test_rebalance_advisor.py
import os, sys, pytest
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path: sys.path.insert(0, _root)

from scripts.rebalance_advisor import RebalanceAdvisor, RebalanceAction, RebalanceReport

def _make_analysis(
    fund_code, fund_name,
    v2_score=50.0, tech_score=50.0,
    stored_profit=0.0, stored_return_rate=0.0,
    cost_amount=20000.0,
):
    """构造 FundHoldingAnalysis-like dict（避免依赖 dataclass）"""
    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "v2_score": v2_score,
        "tech_score": tech_score,
        "stored_profit": stored_profit,
        "stored_return_rate": stored_return_rate,
        "cost_amount": cost_amount,
    }

class TestRebalanceScore:
    def test_score_formula(self):
        # v2=60, return_rate=0(→归一化50), tech=60(→归一化60)
        # return_rate_score = clamp((0 + 15) / 30 * 100, 0, 100) = 50
        # momentum_score = clamp(60, 0, 100) = 60
        # score = 60*0.5 + 50*0.3 + 60*0.2 = 30+15+12 = 57
        a = _make_analysis("A", "基金A", v2_score=60.0, tech_score=60.0,
                           stored_return_rate=0.0)
        advisor = RebalanceAdvisor()
        score = advisor._calc_rebalance_score(a)
        assert score == pytest.approx(57.0, abs=1.0)

class TestReduceCandidate:
    def test_reduce_high_priority(self):
        # v2 < 40, 亏损率 > 8% → 高优先级减仓
        analyses = [
            _make_analysis("A", "基金A", v2_score=32.0, stored_profit=-1500.0,
                           stored_return_rate=-12.3),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.reduce) == 1
        assert report.reduce[0].priority == "high"
        assert report.reduce[0].action == "reduce"

    def test_reduce_medium_priority(self):
        # v2 < 50, 亏损率 -6% → 中优先级减仓
        analyses = [
            _make_analysis("A", "基金A", v2_score=45.0, stored_profit=-600.0,
                           stored_return_rate=-6.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.reduce) == 1
        assert report.reduce[0].priority == "medium"

    def test_no_reduce_when_profitable(self):
        # v2 < 40 但盈利 → 不减仓
        analyses = [
            _make_analysis("A", "基金A", v2_score=38.0, stored_profit=200.0,
                           stored_return_rate=2.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.reduce) == 0

class TestAddCandidate:
    def test_add_high_priority(self):
        # v2 > 70 → 高优先级加仓
        analyses = [
            _make_analysis("A", "基金A", v2_score=75.0, tech_score=65.0,
                           stored_return_rate=42.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.add) == 1
        assert report.add[0].priority == "high"
        assert report.add[0].action == "add"

    def test_add_medium_light_position(self):
        # v2 > 60, 仓位 < 5000 → 中优先级加仓
        analyses = [
            _make_analysis("A", "基金A", v2_score=63.0, tech_score=55.0,
                           cost_amount=1500.0, stored_return_rate=5.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.add) == 1
        assert report.add[0].priority == "medium"

class TestHold:
    def test_hold_when_no_signal(self):
        # 评分中等，无明显信号 → 持有
        analyses = [
            _make_analysis("A", "基金A", v2_score=55.0, stored_profit=100.0,
                           stored_return_rate=1.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert len(report.hold) == 1
        assert len(report.reduce) == 0
        assert len(report.add) == 0

class TestReportCounts:
    def test_total_analyzed(self):
        analyses = [
            _make_analysis("A", "A", v2_score=30.0, stored_profit=-2000.0, stored_return_rate=-10.0),
            _make_analysis("B", "B", v2_score=75.0, tech_score=70.0, stored_return_rate=5.0),
            _make_analysis("C", "C", v2_score=55.0),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert report.total_analyzed == 3
        assert len(report.reduce) + len(report.add) + len(report.hold) == 3

class TestReasonNotEmpty:
    def test_reason_is_populated(self):
        analyses = [
            _make_analysis("A", "大成产业趋势", v2_score=32.0,
                           stored_profit=-1475.0, stored_return_rate=-12.3),
        ]
        report = RebalanceAdvisor().advise(analyses)
        assert report.reduce[0].reason != ""
        assert len(report.reduce[0].reason) > 5
