"""
测试扩展的数据模型
"""

import pytest
from scripts.models import (
    ValuationData, MACDIndicators, RSIIndicators, EnhancedTechnicalIndicators,
    PositionConfig, PositionAdvice, SIPAdvice, FiveDimensionScores
)


def test_valuation_data():
    """测试估值数据模型"""
    data = ValuationData(
        pe_ttm=12.5,
        pb=1.35,
        pe_percentile=25.5,
        pb_percentile=30.2,
        status="低估"
    )
    assert data.pe_ttm == 12.5
    assert data.pb == 1.35
    assert data.pe_percentile == 25.5
    assert data.status == "低估"


def test_macd_indicators():
    """测试MACD指标"""
    macd = MACDIndicators(
        dif=0.5,
        dea=0.3,
        bar=0.4,
        signal="金叉"
    )
    assert macd.dif == 0.5
    assert macd.signal == "金叉"


def test_rsi_indicators():
    """测试RSI指标"""
    rsi = RSIIndicators(
        rsi_6=65.5,
        rsi_12=58.2,
        rsi_24=52.1,
        status="强势"
    )
    assert rsi.rsi_12 == 58.2
    assert rsi.status == "强势"


def test_enhanced_technical_indicators():
    """测试增强技术指标"""
    tech = EnhancedTechnicalIndicators(
        ma5=1.52,
        ma20=1.48,
        ma250=1.40,
        trend="上升",
        formation="多头排列",
        bias_ma250=8.57
    )
    assert tech.ma5 == 1.52
    assert tech.trend == "上升"
    assert tech.bias_ma250 == 8.57
    assert tech.macd is not None  # 默认工厂创建


def test_position_config_valid():
    """测试有效仓位配置"""
    config = PositionConfig(
        fund_type="宽基指数",
        target_pct=15,
        min_pct=8,
        max_pct=20
    )
    assert config.target_pct == 15
    assert config.min_pct == 8
    assert config.max_pct == 20


def test_position_config_invalid_min():
    """测试无效配置：最低线高于目标"""
    with pytest.raises(ValueError, match="最低仓位线"):
        PositionConfig(
            fund_type="测试",
            target_pct=10,
            min_pct=15,  # 高于target_pct
            max_pct=20
        )


def test_position_config_invalid_max():
    """测试无效配置：最高线低于目标"""
    with pytest.raises(ValueError, match="最高仓位线"):
        PositionConfig(
            fund_type="测试",
            target_pct=15,
            min_pct=5,
            max_pct=10  # 低于target_pct
        )


def test_position_advice():
    """测试仓位建议"""
    advice = PositionAdvice(
        fund_code="008888",
        fund_name="测试基金",
        current_pct=5.0,
        target_pct=15.0,
        min_pct=8.0,
        max_pct=20.0,
        deviation_pct=-10.0,
        distance_to_min=-3.0,
        distance_to_max=15.0,
        action="加仓",
        urgency="立即",
        reason="低于最低线"
    )
    assert advice.action == "加仓"
    assert advice.urgency == "立即"


def test_sip_advice():
    """测试定投建议"""
    advice = SIPAdvice(
        fund_code="008888",
        strategy="hybrid",
        base_amount=1000,
        suggested_amount=1500,
        multiplier=1.5,
        signal="加倍定投",
        take_profit_plan=[
            {"trigger": "PE>70%", "action": "卖出30%"}
        ]
    )
    assert advice.multiplier == 1.5
    assert len(advice.take_profit_plan) == 1


def test_five_dimension_scores():
    """测试五维评分"""
    scores = FiveDimensionScores(
        technical=75,
        fundamental=80,
        valuation=70,
        capital_flow=65,
        sentiment=60,
        total=70,
        weights={
            "technical": 0.25,
            "fundamental": 0.25,
            "valuation": 0.3,
            "capital_flow": 0.1,
            "sentiment": 0.1
        }
    )
    assert scores.total == 70
    assert scores.weights["valuation"] == 0.3


def test_default_values():
    """测试默认值"""
    val = ValuationData()
    assert val.status == "未知"

    macd = MACDIndicators()
    assert macd.signal == "未知"

    rsi = RSIIndicators()
    assert rsi.status == "中性"

    tech = EnhancedTechnicalIndicators()
    assert tech.trend == "未知"
    assert tech.signals == []
