# tests/test_analysis_v2/test_sip_advisor_drawdown.py
import pytest
from scripts.analysis_v2.sip_advisor import SIPAdvisor
from scripts.models_risk import RiskMetrics


class TestSIPAdvisorDrawdown:
    def setup_method(self):
        self.advisor = SIPAdvisor()

    def test_drawdown_strategy_deep_drawdown(self):
        """测试深度回撤时的定投建议"""
        risk_metrics = RiskMetrics(
            max_drawdown_duration=10,
            calmar_ratio=0.3
        )
        # 模拟深度回撤（从当前净值与历史高点计算）
        advice = self.advisor._get_drawdown_advice(
            current_drawdown_pct=25.0,
            risk_metrics=risk_metrics,
            base_amount=1000.0
        )
        assert advice.multiplier == 2.0
        assert advice.signal == "加倍定投"

    def test_drawdown_strategy_moderate_drawdown(self):
        """测试中度回撤时的定投建议"""
        risk_metrics = RiskMetrics(
            max_drawdown_duration=20,
            calmar_ratio=0.8
        )
        advice = self.advisor._get_drawdown_advice(
            current_drawdown_pct=15.0,
            risk_metrics=risk_metrics,
            base_amount=1000.0
        )
        assert advice.multiplier == 1.5
        assert advice.signal == "开始定投"

    def test_drawdown_strategy_shallow_drawdown(self):
        """测试轻度回撤时的定投建议"""
        advice = self.advisor._get_drawdown_advice(
            current_drawdown_pct=8.0,
            risk_metrics=RiskMetrics(),
            base_amount=1000.0
        )
        assert advice.multiplier == 1.0
        assert advice.signal == "正常定投"

    def test_drawdown_strategy_no_drawdown(self):
        """测试无回撤时的定投建议"""
        advice = self.advisor._get_drawdown_advice(
            current_drawdown_pct=0.0,
            risk_metrics=RiskMetrics(),
            base_amount=1000.0
        )
        assert advice.multiplier == 1.0
        assert advice.signal == "正常定投"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
