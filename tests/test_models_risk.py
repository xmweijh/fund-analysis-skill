# tests/test_models_risk.py
import pytest
from scripts.models_risk import RiskMetrics, SentimentMetrics


class TestRiskMetrics:
    def test_risk_metrics_creation(self):
        metrics = RiskMetrics(
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            alpha=0.05,
            beta=0.85,
            info_ratio=0.8,
            volatility=0.15,
            downside_deviation=0.08
        )
        assert metrics.sharpe_ratio == 1.5
        assert metrics.beta == 0.85

    def test_risk_metrics_defaults(self):
        metrics = RiskMetrics()
        assert metrics.sharpe_ratio is None
        assert metrics.volatility is None

    def test_sentiment_metrics_creation(self):
        sentiment = SentimentMetrics(
            market_volatility_score=65.0,
            fund_flow_score=70.0,
            overall_sentiment_score=67.5,
            sentiment_status="中性偏多"
        )
        assert sentiment.overall_sentiment_score == 67.5
        assert sentiment.sentiment_status == "中性偏多"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
