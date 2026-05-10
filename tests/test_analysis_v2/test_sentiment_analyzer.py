# tests/test_analysis_v2/test_sentiment_analyzer.py
import pytest
import numpy as np
from scripts.analysis_v2.sentiment_analyzer import SentimentAnalyzer
from scripts.models import FundNavHistory


class TestSentimentAnalyzer:
    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    def test_calculate_volatility_score(self):
        """测试波动率评分"""
        # 低波动 -> 高分
        low_vol_returns = np.random.normal(0, 0.005, 60)
        score_low = self.analyzer._calculate_volatility_score(low_vol_returns)

        # 高波动 -> 低分
        high_vol_returns = np.random.normal(0, 0.02, 60)
        score_high = self.analyzer._calculate_volatility_score(high_vol_returns)

        assert 0 <= score_low <= 100
        assert 0 <= score_high <= 100
        assert score_low > score_high

    def test_analyze_with_fund_flow(self):
        """测试包含资金流向的分析"""
        navs = [1.0 + i * 0.001 for i in range(100)]
        nav_history = FundNavHistory(
            fund_code="008888",
            navs=navs,
            dates=[f"2024-01-{i+1:02d}" for i in range(100)]
        )

        # 模拟近期净值增长（资金流入）
        result = self.analyzer.analyze(nav_history, recent_change_pct=2.0)
        assert result is not None
        assert result.overall_sentiment_score >= 50

    def test_analyze_market_decline(self):
        """测试市场下跌时的资金流向评分"""
        navs = [1.0 + i * 0.001 for i in range(100)]
        nav_history = FundNavHistory(
            fund_code="008888",
            navs=navs,
            dates=[f"2024-01-{i+1:02d}" for i in range(100)]
        )

        # 测试大跌时的资金流向评分
        result = self.analyzer.analyze(nav_history, recent_change_pct=-5.0)
        assert result is not None
        # 大跌应该导致较低的资金流向评分
        assert result.fund_flow_score < 50
        assert "近期大跌" in str(result.factors)

    def test_calculate_overall_score(self):
        """测试综合评分计算"""
        score = self.analyzer._calculate_overall_score(
            volatility_score=70.0,
            fund_flow_score=60.0,
            search_trend_score=50.0,
            new_fund_score=40.0
        )
        assert 0 <= score <= 100
        # 权重: 波动40%, 资金35%, 搜索15%, 新基金10%
        expected = 70.0 * 0.4 + 60.0 * 0.35 + 50.0 * 0.15 + (100 - 40.0) * 0.10
        assert abs(score - expected) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
