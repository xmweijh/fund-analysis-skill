# tests/test_analysis_v2/test_risk_analyzer.py
import pytest
import numpy as np
from scripts.analysis_v2.risk_analyzer import RiskAnalyzer
from scripts.models import FundNavHistory


class TestRiskAnalyzer:
    def setup_method(self):
        self.analyzer = RiskAnalyzer()
        # 生成模拟净值数据：年化收益约10%，波动约15%
        np.random.seed(42)
        returns = np.random.normal(0.0004, 0.0095, 252)  # 日收益率
        navs = [1.0]
        for r in returns:
            navs.append(navs[-1] * (1 + r))

        self.nav_history = FundNavHistory(
            fund_code="008888",
            navs=navs,
            dates=[f"2024-01-{i+1:02d}" for i in range(len(navs))]
        )

    def test_calculate_sharpe_ratio(self):
        """测试夏普比率计算"""
        returns = np.random.normal(0.0004, 0.0095, 252)
        sharpe = self.analyzer._calculate_sharpe_ratio(returns)
        assert sharpe is not None
        assert -1 < sharpe < 3  # 合理范围

    def test_calculate_volatility(self):
        """测试波动率计算"""
        returns = np.random.normal(0.0004, 0.0095, 252)
        vol = self.analyzer._calculate_volatility(returns)
        assert vol is not None
        assert 0 < vol < 0.5  # 合理范围

    def test_calculate_max_drawdown_duration(self):
        """测试最大回撤持续时间"""
        navs = [1.0, 1.1, 1.05, 1.0, 0.95, 0.9, 0.95, 1.0, 1.1]
        mdd, duration = self.analyzer._calculate_max_drawdown(navs)
        assert mdd < 0  # 回撤为负
        assert duration >= 0

    def test_analyze_with_sufficient_data(self):
        """测试有足够数据时的分析"""
        result = self.analyzer.analyze(self.nav_history)
        assert result is not None
        assert result.sharpe_ratio is not None
        assert result.volatility is not None
        assert result.calmar_ratio is not None

    def test_analyze_with_insufficient_data(self):
        """测试数据不足时的处理"""
        short_navs = FundNavHistory(
            fund_code="008888",
            navs=[1.0, 1.01, 1.02],
            dates=["2024-01-01", "2024-01-02", "2024-01-03"]
        )
        result = self.analyzer.analyze(short_navs)
        assert result is not None
        # 数据不足时返回默认值
        assert result.sharpe_ratio is None

    def test_calculate_fundamental_score(self):
        """测试基本面评分计算"""
        from scripts.models_risk import RiskMetrics

        metrics = RiskMetrics(
            sharpe_ratio=1.5,
            calmar_ratio=2.0,
            alpha=0.05,
            max_drawdown_duration=30
        )
        score = self.analyzer.calculate_fundamental_score(metrics)
        assert 0 <= score <= 100
        # 好的指标应该得高分
        assert score > 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
