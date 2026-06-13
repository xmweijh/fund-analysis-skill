# tests/test_deep_portfolio_analyzer.py
import os, sys, pytest
from unittest.mock import patch, MagicMock
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path: sys.path.insert(0, _root)

from scripts.deep_portfolio_analyzer import DeepPortfolioAnalyzer

# 构造 PortfolioEntry-like mock
def _entry(code, name, cost=10000.0, profit=0.0, rate=0.0):
    e = MagicMock()
    e.fund_code = code
    e.fund_name = name
    e.cost_amount = cost
    e.current_profit = profit
    e.current_return_rate = rate
    return e

class TestFilter:
    def test_skip_bond_keywords(self):
        entries = [
            _entry("010011", "景顺长城景顺融华债券A"),
            _entry("022403", "信澳稳悦60天持有债券A"),
            _entry("022807", "创金合信恒睿90天持有债券A"),
            _entry("008269", "大成睿享混合A"),
            _entry("009477", "中银上海金ETF联接A"),
        ]
        analyzer = DeepPortfolioAnalyzer()
        filtered = analyzer._filter_non_fixed_income(entries)
        codes = [e.fund_code for e in filtered]
        assert "010011" not in codes   # 债券
        assert "022403" not in codes   # 稳悦（跳过关键词）
        assert "022807" not in codes   # 恒睿（跳过关键词）
        assert "008269" in codes       # 混合 → 纳入
        assert "009477" in codes       # 黄金 → 纳入

    def test_skip_liutianjin_keywords(self):
        entries = [
            _entry("110018", "易方达增强回报债券A"),
            _entry("022611", "国泰利添120天持有债券A"),
        ]
        analyzer = DeepPortfolioAnalyzer()
        filtered = analyzer._filter_non_fixed_income(entries)
        assert len(filtered) == 0

    def test_keep_qdii(self):
        entries = [
            _entry("012920", "易方达全球成长混合(QDII)A"),
            _entry("000834", "大成纳斯达克100指数(QDII)美元现汇A"),
        ]
        analyzer = DeepPortfolioAnalyzer()
        filtered = analyzer._filter_non_fixed_income(entries)
        assert len(filtered) == 2

class TestTerminalSummary:
    def test_summary_contains_key_sections(self):
        from scripts.risk_diagnostics import RiskReport
        from scripts.rebalance_advisor import RebalanceReport, RebalanceAction

        risk = RiskReport(
            concentration_pct=68.0, concentration_level="high",
            overlap_groups=[{"brand": "大成", "funds": ["大成A", "大成B", "大成C", "大成D"]}],
            qdii_pct=1.6, qdii_level="low",
            max_loss_fund="大成产业趋势", max_loss_amount=-1475.0,
            total_loss_exposure=-5000.0,
            warnings=["⚠️ 集中度偏高", "⚡ 大成系重叠", "💡 QDII不足"],
        )
        rebalance = RebalanceReport(
            reduce=[RebalanceAction("A", "大成产业趋势", "reduce", "high", 30.0, 32.0, -1475.0, -12.3, "止损")],
            add=[RebalanceAction("B", "易方达全球成长", "add", "high", 75.0, 78.0, 645.0, 42.75, "加仓")],
            hold=[],
            total_analyzed=2,
        )
        analyzer = DeepPortfolioAnalyzer()
        summary = analyzer._format_terminal_summary(risk, rebalance)
        assert "风险诊断" in summary
        assert "调仓建议" in summary
        assert "大成产业趋势" in summary
        assert "易方达全球成长" in summary
        assert "共分析" in summary
