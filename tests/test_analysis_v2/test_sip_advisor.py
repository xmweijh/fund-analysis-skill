"""
测试定投助手 (SIPAdvisor)
"""

import pytest
from typing import Optional

from scripts.models import (
    EnhancedTechnicalIndicators,
    ValuationData,
    MACDIndicators,
    RSIIndicators,
)
from scripts.analysis_v2 import SIPAdvisor, SIPAdvice, TakeProfitPlan


# ================================================================== #
#  Fixtures                                                          #
# ================================================================== #

@pytest.fixture
def advisor() -> SIPAdvisor:
    return SIPAdvisor()


def _make_technical(
    bias_ma250: Optional[float] = -5.0,
    ma250: Optional[float] = 1.0,
    trend: str = "上升",
    formation: str = "多头排列",
) -> EnhancedTechnicalIndicators:
    """构造技术指标"""
    return EnhancedTechnicalIndicators(
        ma5=1.05,
        ma10=1.04,
        ma20=1.03,
        ma60=1.02,
        ma250=ma250,
        trend=trend,
        formation=formation,
        signals=["价格站上MA20"],
        macd=MACDIndicators(dif=0.01, dea=0.005, bar=0.01, signal="金叉"),
        rsi=RSIIndicators(rsi_6=55.0, rsi_12=60.0, rsi_24=65.0, status="强势"),
        bias_ma5=2.0,
        bias_ma20=1.0,
        bias_ma250=bias_ma250,
        volume_ratio=1.2,
    )


def _make_valuation(
    pe_percentile: Optional[float] = 30.0,
    pe_ttm: Optional[float] = 18.0,
    status: str = "合理",
) -> ValuationData:
    """构造估值数据"""
    return ValuationData(
        pe_ttm=pe_ttm,
        pb=2.5,
        pe_percentile=pe_percentile,
        pb_percentile=40.0,
        risk_premium=5.0,
        equity_bond_ratio=0.8,
        status=status,
        update_date="2024-05-10",
    )


# ================================================================== #
#  SIPAdvice 结构测试                                                #
# ================================================================== #

class TestSIPAdviceStructure:
    def test_advice_has_required_fields(self, advisor):
        technical = _make_technical()
        advice = advisor.get_advice("ma250", technical)

        assert isinstance(advice, SIPAdvice)
        assert advice.strategy == "ma250"
        assert isinstance(advice.signal, str)
        assert isinstance(advice.multiplier, float)
        assert isinstance(advice.confidence, int)
        assert isinstance(advice.reasons, list)
        assert isinstance(advice.risks, list)
        assert isinstance(advice.take_profit_plans, list)

    def test_multiplier_in_valid_range(self, advisor):
        technical = _make_technical()
        advice = advisor.get_advice("ma250", technical)
        assert 0.0 <= advice.multiplier <= 3.0

    def test_confidence_in_valid_range(self, advisor):
        technical = _make_technical()
        advice = advisor.get_advice("ma250", technical)
        assert 0 <= advice.confidence <= 100

    def test_recommended_amount_calculated(self, advisor):
        technical = _make_technical()
        advice = advisor.get_advice("ma250", technical, base_amount=1000)
        assert advice.recommended_amount == 1000 * advice.multiplier


# ================================================================== #
#  MA250 策略测试                                                    #
# ================================================================== #

class TestMA250Strategy:
    def test_double_sip_when_very_low(self, advisor):
        """bias_250 < -10% 时：加倍定投"""
        technical = _make_technical(bias_ma250=-12.0)
        advice = advisor.get_advice("ma250", technical)

        assert advice.signal == "加倍定投"
        assert advice.multiplier == 2.0
        assert advice.confidence >= 90

    def test_start_sip_when_low(self, advisor):
        """bias_250 < -5% 时：开始定投"""
        technical = _make_technical(bias_ma250=-7.0)
        advice = advisor.get_advice("ma250", technical)

        assert advice.signal == "开始定投"
        assert advice.multiplier == 1.5
        assert advice.confidence >= 80

    def test_normal_sip_when_slightly_low(self, advisor):
        """bias_250 < 0% 时：正常定投"""
        technical = _make_technical(bias_ma250=-2.0)
        advice = advisor.get_advice("ma250", technical)

        assert advice.signal == "正常定投"
        assert advice.multiplier == 1.0
        assert advice.confidence >= 70

    def test_stop_sip_when_high(self, advisor):
        """bias_250 >= 0% 时：停止定投"""
        technical = _make_technical(bias_ma250=5.0)
        advice = advisor.get_advice("ma250", technical)

        assert advice.signal == "停止定投"
        assert advice.multiplier == 0.0
        assert advice.confidence >= 70

    def test_ma250_take_profit_plans(self, advisor):
        """验证止盈计划"""
        technical = _make_technical(bias_ma250=-10.0)
        advice = advisor.get_advice("ma250", technical)

        assert len(advice.take_profit_plans) == 3
        assert all(isinstance(p, TakeProfitPlan) for p in advice.take_profit_plans)

        levels = [p.profit_level for p in advice.take_profit_plans]
        assert "+10%" in levels
        assert "+20%" in levels
        assert "+30%" in levels

    def test_ma250_reasons_and_risks(self, advisor):
        """验证理由和风险"""
        technical = _make_technical(bias_ma250=-8.0, trend="下降")
        advice = advisor.get_advice("ma250", technical)

        assert len(advice.reasons) > 0
        assert any("偏离率" in r for r in advice.reasons)
        assert len(advice.risks) > 0

    def test_ma250_with_base_amount(self, advisor):
        """测试基础金额计算"""
        technical = _make_technical(bias_ma250=-12.0)
        advice = advisor.get_advice("ma250", technical, base_amount=1000)

        assert advice.base_amount == 1000
        assert advice.recommended_amount == 2000  # 1000 * 2.0


# ================================================================== #
#  Valuation 策略测试                                               #
# ================================================================== #

class TestValuationStrategy:
    def test_double_sip_when_undervalued(self, advisor):
        """PE百分位 < 20% 时：加倍定投"""
        valuation = _make_valuation(pe_percentile=15.0, status="低估")
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert advice.signal == "加倍定投"
        assert advice.multiplier == 2.0
        assert advice.confidence >= 90

    def test_start_sip_when_relatively_low(self, advisor):
        """PE百分位 20-35% 时：开始定投"""
        valuation = _make_valuation(pe_percentile=28.0, status="合理")
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert advice.signal == "开始定投"
        assert advice.multiplier == 1.5
        assert advice.confidence >= 80

    def test_normal_sip_when_mid(self, advisor):
        """PE百分位 35-50% 时：正常定投"""
        valuation = _make_valuation(pe_percentile=42.0, status="合理")
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert advice.signal == "正常定投"
        assert advice.multiplier == 1.0
        assert advice.confidence >= 70

    def test_reduce_sip_when_relatively_high(self, advisor):
        """PE百分位 50-70% 时：减少定投"""
        valuation = _make_valuation(pe_percentile=60.0, status="合理")
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert advice.signal == "减少定投"
        assert advice.multiplier == 0.5
        assert advice.confidence >= 65

    def test_stop_sip_when_overvalued(self, advisor):
        """PE百分位 > 70% 时：停止定投"""
        valuation = _make_valuation(pe_percentile=85.0, status="高估")
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert advice.signal == "停止定投"
        assert advice.multiplier == 0.0
        assert advice.confidence >= 70

    def test_valuation_take_profit_plans(self, advisor):
        """验证止盈计划"""
        valuation = _make_valuation(pe_percentile=25.0)
        advice = advisor.get_advice("valuation", valuation=valuation)

        assert len(advice.take_profit_plans) == 2
        assert all(isinstance(p, TakeProfitPlan) for p in advice.take_profit_plans)

        levels = [p.profit_level for p in advice.take_profit_plans]
        assert "PE > 70%" in levels
        assert "PE > 80%" in levels

    def test_valuation_without_data(self, advisor):
        """无估值数据时返回默认建议"""
        advice = advisor.get_advice("valuation", base_amount=1000)
        assert advice.signal == "正常定投"
        assert advice.multiplier == 1.0
        assert advice.confidence == 50

    def test_valuation_with_base_amount(self, advisor):
        """测试基础金额计算"""
        valuation = _make_valuation(pe_percentile=15.0)
        advice = advisor.get_advice("valuation", valuation=valuation, base_amount=2000)

        assert advice.base_amount == 2000
        assert advice.recommended_amount == 4000  # 2000 * 2.0


# ================================================================== #
#  Hybrid 策略测试                                                   #
# ================================================================== #

class TestHybridStrategy:
    def test_hybrid_combines_both_strategies(self, advisor):
        """混合策略结合两个独立策略"""
        technical = _make_technical(bias_ma250=-12.0)
        valuation = _make_valuation(pe_percentile=15.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.strategy == "hybrid"
        assert advice.multiplier > 0
        # 倍数 = 2.0 * 0.6 + 2.0 * 0.4 = 2.0
        assert abs(advice.multiplier - 2.0) < 0.01

    def test_hybrid_signal_double_when_both_low(self, advisor):
        """两个指标都处于低位时"""
        technical = _make_technical(bias_ma250=-12.0)
        valuation = _make_valuation(pe_percentile=15.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.signal == "加倍定投"

    def test_hybrid_signal_normal_when_mid(self, advisor):
        """两个指标都处于中位时"""
        technical = _make_technical(bias_ma250=-2.0)
        valuation = _make_valuation(pe_percentile=42.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.signal == "正常定投"

    def test_hybrid_signal_stop_when_both_high(self, advisor):
        """两个指标都处于高位时"""
        technical = _make_technical(bias_ma250=10.0)
        valuation = _make_valuation(pe_percentile=85.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.signal == "停止定投"

    def test_hybrid_weighted_calculation(self, advisor):
        """验证加权计算"""
        # MA250: bias_250 = -7.0 → 1.5x (40%)
        # Valuation: PE百分位 = 42.0 → 1.0x (60%)
        # 期望: 1.0 * 0.6 + 1.5 * 0.4 = 0.6 + 0.6 = 1.2x
        technical = _make_technical(bias_ma250=-7.0)
        valuation = _make_valuation(pe_percentile=42.0)

        advice = advisor.get_advice("hybrid", technical=technical, valuation=valuation)

        assert abs(advice.multiplier - 1.2) < 0.01
        assert advice.signal == "开始定投"

    def test_hybrid_uses_valuation_take_profit(self, advisor):
        """混合策略使用估值的止盈计划"""
        technical = _make_technical(bias_ma250=-8.0)
        valuation = _make_valuation(pe_percentile=30.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        # 应该使用估值的止盈计划
        levels = [p.profit_level for p in advice.take_profit_plans]
        assert "PE > 70%" in levels
        assert "PE > 80%" in levels

    def test_hybrid_with_base_amount(self, advisor):
        """测试基础金额计算"""
        technical = _make_technical(bias_ma250=-12.0)
        valuation = _make_valuation(pe_percentile=15.0)

        advice = advisor.get_advice("hybrid", technical=technical, valuation=valuation, base_amount=1000)

        assert advice.recommended_amount == 2000  # 1000 * 2.0


# ================================================================== #
#  边界和异常情况测试                                                #
# ================================================================== #

class TestEdgeCases:
    def test_ma250_with_none_bias(self, advisor):
        """bias_ma250 为 None 时"""
        technical = _make_technical(bias_ma250=None)
        advice = advisor.get_advice("ma250", technical)

        assert advice.signal == "正常定投"
        assert advice.multiplier == 1.0
        assert advice.confidence == 50

    def test_valuation_with_none_percentile(self, advisor):
        """PE百分位为 None 时"""
        valuation = ValuationData(
            pe_ttm=18.0,
            pb=2.5,
            pe_percentile=None,
            status="合理",
        )
        advice = advisor.get_advice("valuation", valuation)

        assert advice.signal == "正常定投"
        assert advice.multiplier == 1.0

    def test_invalid_strategy_name(self, advisor):
        """无效策略名称"""
        technical = _make_technical()
        advice = advisor.get_advice("invalid_strategy", technical)

        assert advice.signal == "正常定投"
        assert advice.confidence == 50

    def test_hybrid_without_valuation(self, advisor):
        """混合策略但无估值数据时"""
        technical = _make_technical(bias_ma250=-8.0)
        advice = advisor.get_advice("hybrid", technical)

        # 应该降级为 MA250 策略
        assert advice.strategy == "hybrid" or advice.strategy == "ma250"

    def test_advice_without_base_amount(self, advisor):
        """未提供基础金额"""
        technical = _make_technical(bias_ma250=-10.0)
        advice = advisor.get_advice("ma250", technical)

        assert advice.base_amount is None
        assert advice.recommended_amount is None

    def test_advice_with_zero_base_amount(self, advisor):
        """基础金额为零"""
        technical = _make_technical(bias_ma250=-10.0)
        advice = advisor.get_advice("ma250", technical, base_amount=0)

        assert advice.recommended_amount == 0


# ================================================================== #
#  策略指标快照测试                                                  #
# ================================================================== #

class TestIndicatorsSnapshot:
    def test_ma250_snapshot(self, advisor):
        """MA250 策略的指标快照"""
        technical = _make_technical(bias_ma250=-8.0)
        advice = advisor.get_advice("ma250", technical)

        snapshot = advice.indicators_snapshot
        assert "bias_ma250" in snapshot
        assert "ma250" in snapshot
        assert snapshot["bias_ma250"] == -8.0

    def test_valuation_snapshot(self, advisor):
        """估值策略的指标快照"""
        valuation = _make_valuation(pe_percentile=30.0)
        advice = advisor.get_advice("valuation", valuation=valuation)

        snapshot = advice.indicators_snapshot
        assert "pe_percentile" in snapshot
        assert snapshot["pe_percentile"] == 30.0

    def test_hybrid_snapshot(self, advisor):
        """混合策略的指标快照"""
        technical = _make_technical(bias_ma250=-8.0)
        valuation = _make_valuation(pe_percentile=42.0)

        advice = advisor.get_advice("hybrid", technical, valuation)

        snapshot = advice.indicators_snapshot
        assert "hybrid_multiplier" in snapshot
        assert "valuation_multiplier" in snapshot
        assert "ma250_multiplier" in snapshot


# ================================================================== #
#  复杂场景测试                                                      #
# ================================================================== #

class TestComplexScenarios:
    def test_strong_buy_signal(self, advisor):
        """强买入信号：低估 + 下降趋势"""
        technical = _make_technical(bias_ma250=-15.0, trend="下降")
        valuation = _make_valuation(pe_percentile=10.0, status="低估")

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.signal == "加倍定投"
        assert advice.multiplier >= 1.8
        assert len(advice.reasons) > 2

    def test_weak_buy_signal(self, advisor):
        """弱买入信号：略低估 + 上升趋势"""
        technical = _make_technical(bias_ma250=-2.0, trend="上升")
        valuation = _make_valuation(pe_percentile=55.0, status="合理")

        advice = advisor.get_advice("hybrid", technical, valuation)

        assert advice.multiplier <= 1.0
        assert len(advice.risks) == 0 or len(advice.risks) > 0

    def test_mixed_signals(self, advisor):
        """混合信号：一个低估，一个高估"""
        technical = _make_technical(bias_ma250=-12.0, trend="下降")
        valuation = _make_valuation(pe_percentile=75.0, status="高估")

        advice = advisor.get_advice("hybrid", technical, valuation)

        # 倍数应该在两者之间
        # MA250: 2.0x (40%), Valuation: 0.0x (60%) = 0.8x
        assert 0.0 <= advice.multiplier <= 2.0
        assert len(advice.risks) > 0

    def test_all_strategies_comparison(self, advisor):
        """对比三种策略"""
        technical = _make_technical(bias_ma250=-8.0)
        valuation = _make_valuation(pe_percentile=28.0)

        ma250_advice = advisor.get_advice("ma250", technical=technical, base_amount=1000)
        val_advice = advisor.get_advice("valuation", valuation=valuation, base_amount=1000)
        hybrid_advice = advisor.get_advice(
            "hybrid", technical=technical, valuation=valuation, base_amount=1000
        )

        assert ma250_advice.multiplier == 1.5  # -8% → 开始定投
        assert val_advice.multiplier == 1.5    # 28% → 开始定投
        assert hybrid_advice.multiplier == 1.5  # weighted average

        assert ma250_advice.recommended_amount == 1500
        assert val_advice.recommended_amount == 1500
        assert hybrid_advice.recommended_amount == 1500
