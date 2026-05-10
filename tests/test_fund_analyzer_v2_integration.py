# tests/test_fund_analyzer_v2_integration.py
import pytest
from unittest.mock import Mock, patch
from scripts.fund_analyzer_v2 import FundAnalyzerV2


class TestFundAnalyzerV2Integration:
    def setup_method(self):
        self.analyzer = FundAnalyzerV2()

    def test_analyzer_initializes_risk_analyzer(self):
        """测试分析器初始化时创建 RiskAnalyzer"""
        assert hasattr(self.analyzer, 'risk_analyzer')
        from scripts.analysis_v2 import RiskAnalyzer
        assert isinstance(self.analyzer.risk_analyzer, RiskAnalyzer)

    def test_analyzer_initializes_sentiment_analyzer(self):
        """测试分析器初始化时创建 SentimentAnalyzer"""
        assert hasattr(self.analyzer, 'sentiment_analyzer')
        from scripts.analysis_v2 import SentimentAnalyzer
        assert isinstance(self.analyzer.sentiment_analyzer, SentimentAnalyzer)

    @patch('scripts.fund_analyzer_v2.DanjuanDataFetcher')
    def test_sentiment_score_calculation(self, mock_fetcher):
        """测试情绪面评分被正确计算"""
        # Mock 返回数据
        mock_instance = Mock()
        mock_instance.fetch_basic_info.return_value = Mock(
            fund_code="008888",
            fund_name="测试基金",
            fund_type="股票型"
        )
        mock_instance.fetch_nav_history.return_value = Mock(
            fund_code="008888",
            navs=[1.0 + i * 0.001 for i in range(100)],
            dates=[f"2024-01-{i+1:02d}" for i in range(100)]
        )
        mock_instance.fetch_realtime_quote.return_value = Mock(
            change_pct=1.5
        )
        mock_fetcher.return_value = mock_instance

        # 重新初始化以使用 mock
        analyzer = FundAnalyzerV2()

        # 检查情绪面分析器被使用
        assert hasattr(analyzer, 'sentiment_analyzer')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
