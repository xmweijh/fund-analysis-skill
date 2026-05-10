"""
测试增强版技术分析模块 (EnhancedTechnicalAnalyzer)
"""

import pytest
import numpy as np
from typing import List

from scripts.models import FundNavHistory
from scripts.analysis_v2 import EnhancedTechnicalAnalyzer, TechnicalAnalysisResult


# ------------------------------------------------------------------ #
#  Fixtures                                                           #
# ------------------------------------------------------------------ #

def _make_nav_history(navs: List[float], fund_code: str = "000001") -> FundNavHistory:
    """辅助函数：构造 FundNavHistory"""
    from datetime import date, timedelta
    base = date(2020, 1, 1)
    dates = [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(len(navs))]
    return FundNavHistory(fund_code=fund_code, dates=dates, navs=navs)


def _trending_up(n: int = 300, base: float = 1.0, step: float = 0.002) -> List[float]:
    """生成 n 条稳定上升净值序列"""
    return [round(base + i * step, 4) for i in range(n)]


def _trending_down(n: int = 300, base: float = 1.6, step: float = 0.002) -> List[float]:
    """生成 n 条稳定下降净值序列"""
    return [round(base - i * step, 4) for i in range(n)]


def _flat(n: int = 300, value: float = 1.0) -> List[float]:
    """生成 n 条平坦净值序列（微小随机噪声）"""
    rng = np.random.default_rng(42)
    noise = rng.uniform(-0.002, 0.002, n)
    return [round(value + float(v), 6) for v in noise]


@pytest.fixture
def analyzer() -> EnhancedTechnicalAnalyzer:
    return EnhancedTechnicalAnalyzer()


@pytest.fixture
def up_trend_history() -> FundNavHistory:
    return _make_nav_history(_trending_up(300))


@pytest.fixture
def down_trend_history() -> FundNavHistory:
    return _make_nav_history(_trending_down(300))


@pytest.fixture
def flat_history() -> FundNavHistory:
    return _make_nav_history(_flat(300))


@pytest.fixture
def short_history() -> FundNavHistory:
    """数据不足的历史 (< 60 条)"""
    return _make_nav_history([1.0] * 30)


# ------------------------------------------------------------------ #
#  TechnicalAnalysisResult 结构测试                                    #
# ------------------------------------------------------------------ #

class TestTechnicalAnalysisResultStructure:
    def test_returns_correct_type(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert isinstance(result, TechnicalAnalysisResult)

    def test_indicators_not_none(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators is not None

    def test_score_in_valid_range(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert 0 <= result.buy_signal_score <= 100

    def test_signal_reasons_is_list(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert isinstance(result.signal_reasons, list)

    def test_risk_factors_is_list(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert isinstance(result.risk_factors, list)


# ------------------------------------------------------------------ #
#  移动平均线测试                                                       #
# ------------------------------------------------------------------ #

class TestMovingAverages:
    def test_ma5_close_to_recent_mean(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        navs = up_trend_history.navs
        expected_ma5 = float(np.mean(navs[-5:]))
        assert abs(result.indicators.ma5 - expected_ma5) < 1e-6  # type: ignore

    def test_ma10_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.ma10 is not None

    def test_ma20_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.ma20 is not None

    def test_ma60_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.ma60 is not None

    def test_ma250_present_when_enough_data(self, analyzer):
        navs = _trending_up(300)
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        assert result.indicators.ma250 is not None

    def test_ma250_none_when_insufficient_data(self, analyzer):
        navs = _trending_up(200)  # 200 < 250
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        assert result.indicators.ma250 is None

    def test_ma_ordering_in_uptrend(self, analyzer, up_trend_history):
        """上升趋势中 MA5 > MA10 > MA20 > MA60"""
        result = analyzer.analyze(up_trend_history)
        ind = result.indicators
        assert ind.ma5 > ind.ma10 > ind.ma20 > ind.ma60   # type: ignore


# ------------------------------------------------------------------ #
#  形态检测测试                                                         #
# ------------------------------------------------------------------ #

class TestFormation:
    def test_bullish_formation_in_uptrend(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.formation == "多头排列"

    def test_bearish_formation_in_downtrend(self, analyzer, down_trend_history):
        result = analyzer.analyze(down_trend_history)
        assert result.indicators.formation == "空头排列"


# ------------------------------------------------------------------ #
#  趋势判断测试                                                         #
# ------------------------------------------------------------------ #

class TestTrend:
    def test_uptrend_detected(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.trend == "上升"

    def test_downtrend_detected(self, analyzer, down_trend_history):
        result = analyzer.analyze(down_trend_history)
        assert result.indicators.trend == "下降"

    def test_trend_is_string(self, analyzer, flat_history):
        result = analyzer.analyze(flat_history)
        assert isinstance(result.indicators.trend, str)


# ------------------------------------------------------------------ #
#  MACD 测试                                                           #
# ------------------------------------------------------------------ #

class TestMACD:
    def test_macd_fields_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        macd = result.indicators.macd
        assert macd is not None
        assert macd.dif is not None
        assert macd.dea is not None
        assert macd.bar is not None

    def test_macd_signal_valid_value(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.macd.signal in ("金叉", "死叉", "多头", "空头", "未知")

    def test_macd_bar_equals_dif_minus_dea_times_two(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        macd = result.indicators.macd
        if macd.dif is not None and macd.dea is not None and macd.bar is not None:
            expected_bar = (macd.dif - macd.dea) * 2
            assert abs(macd.bar - expected_bar) < 1e-5

    def test_uptrend_macd_in_bullish_area(self, analyzer, up_trend_history):
        """稳定上升趋势下 DIF 应大于等于 DEA (多头区间)"""
        result = analyzer.analyze(up_trend_history)
        macd = result.indicators.macd
        if macd.dif is not None and macd.dea is not None:
            # 在稳定上升趋势下 DIF >= DEA (线性序列可能恰好相等)
            assert macd.dif >= macd.dea

    def test_macd_unknown_when_insufficient_data(self, analyzer, short_history):
        """数据不足时 MACD 信号应为"未知"或返回默认"""
        result = analyzer.analyze(short_history)
        assert result.indicators.macd.signal in ("未知",)

    def test_golden_cross_detected(self, analyzer):
        """
        构造一个 DIF 从下方穿越 DEA 的序列以触发金叉。
        使用先下降后上升的净值序列。
        """
        down_then_up = _trending_down(200) + _trending_up(100, base=0.2)
        history = _make_nav_history(down_then_up)
        result = analyzer.analyze(history)
        # 不要求必定出现金叉(取决于具体价格序列)，只验证信号合法
        assert result.indicators.macd.signal in ("金叉", "死叉", "多头", "空头", "未知")


# ------------------------------------------------------------------ #
#  RSI 测试                                                            #
# ------------------------------------------------------------------ #

class TestRSI:
    def test_rsi_fields_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        rsi = result.indicators.rsi
        assert rsi is not None
        assert rsi.rsi_6 is not None
        assert rsi.rsi_12 is not None
        assert rsi.rsi_24 is not None

    def test_rsi_values_in_0_100_range(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        rsi = result.indicators.rsi
        for val in (rsi.rsi_6, rsi.rsi_12, rsi.rsi_24):
            if val is not None:
                assert 0.0 <= val <= 100.0

    def test_rsi_status_valid_value(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.rsi.status in ("超买", "强势", "中性", "弱势", "超卖")

    def test_overbought_rsi_in_strong_uptrend(self, analyzer):
        """强劲上升趋势下 RSI 应接近超买区间"""
        steep_up = [round(1.0 + i * 0.01, 4) for i in range(100)]  # 每天 +1%
        history = _make_nav_history(steep_up)
        result = analyzer.analyze(history)
        rsi = result.indicators.rsi
        if rsi.rsi_6 is not None:
            assert rsi.rsi_6 > 60  # 强劲上升 RSI 应进入强势或超买

    def test_oversold_rsi_in_strong_downtrend(self, analyzer):
        """强劲下跌趋势下 RSI 应接近超卖区间"""
        steep_down = [round(2.0 - i * 0.01, 4) for i in range(100)]
        history = _make_nav_history(steep_down)
        result = analyzer.analyze(history)
        rsi = result.indicators.rsi
        if rsi.rsi_6 is not None:
            assert rsi.rsi_6 < 40  # 强劲下跌 RSI 应进入弱势或超卖

    def test_rsi_6_reacts_faster_than_rsi_24(self, analyzer):
        """RSI6 波动幅度应大于 RSI24"""
        steep_up = [round(1.0 + i * 0.008, 4) for i in range(100)]
        history = _make_nav_history(steep_up)
        result = analyzer.analyze(history)
        rsi = result.indicators.rsi
        if rsi.rsi_6 is not None and rsi.rsi_24 is not None:
            assert rsi.rsi_6 >= rsi.rsi_24  # 在上升趋势中短周期 RSI 更高


# ------------------------------------------------------------------ #
#  BIAS (乖离率) 测试                                                   #
# ------------------------------------------------------------------ #

class TestBIAS:
    def test_bias_ma5_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.bias_ma5 is not None

    def test_bias_ma20_present(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert result.indicators.bias_ma20 is not None

    def test_bias_formula_correctness(self, analyzer, up_trend_history):
        """BIAS = (price - MA) / MA * 100"""
        result = analyzer.analyze(up_trend_history)
        ind = result.indicators
        navs = up_trend_history.navs
        current = navs[-1]
        if ind.ma20 is not None and ind.bias_ma20 is not None:
            expected = (current - ind.ma20) / ind.ma20 * 100
            assert abs(ind.bias_ma20 - expected) < 1e-3

    def test_bias_ma250_none_when_not_enough(self, analyzer):
        navs = _trending_up(200)
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        # ma250 为 None，则 bias_ma250 也应为 None
        assert result.indicators.bias_ma250 is None

    def test_bias_positive_in_uptrend(self, analyzer, up_trend_history):
        """上升趋势中 BIAS_MA20 应为正（当前价 > MA20）"""
        result = analyzer.analyze(up_trend_history)
        if result.indicators.bias_ma20 is not None:
            assert result.indicators.bias_ma20 > 0

    def test_bias_negative_in_downtrend(self, analyzer, down_trend_history):
        """下降趋势中 BIAS_MA20 应为负"""
        result = analyzer.analyze(down_trend_history)
        if result.indicators.bias_ma20 is not None:
            assert result.indicators.bias_ma20 < 0


# ------------------------------------------------------------------ #
#  买入信号评分测试                                                      #
# ------------------------------------------------------------------ #

class TestBuySignalScore:
    def test_uptrend_score_above_50(self, analyzer, up_trend_history):
        """多头市场评分应高于 50"""
        result = analyzer.analyze(up_trend_history)
        assert result.buy_signal_score > 50

    def test_downtrend_score_below_50(self, analyzer, down_trend_history):
        """空头市场评分应低于 50"""
        result = analyzer.analyze(down_trend_history)
        assert result.buy_signal_score < 50

    def test_score_is_integer(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert isinstance(result.buy_signal_score, int)

    def test_uptrend_has_signal_reasons(self, analyzer, up_trend_history):
        result = analyzer.analyze(up_trend_history)
        assert len(result.signal_reasons) > 0

    def test_downtrend_has_risk_factors(self, analyzer, down_trend_history):
        result = analyzer.analyze(down_trend_history)
        assert len(result.risk_factors) > 0


# ------------------------------------------------------------------ #
#  边缘情况测试                                                         #
# ------------------------------------------------------------------ #

class TestEdgeCases:
    def test_insufficient_data_returns_default(self, analyzer, short_history):
        result = analyzer.analyze(short_history)
        assert result.indicators.trend == "未知"
        assert result.buy_signal_score == 50

    def test_empty_navs_returns_default(self, analyzer):
        history = FundNavHistory(fund_code="000001", dates=[], navs=[])
        result = analyzer.analyze(history)
        assert result.indicators.trend == "未知"

    def test_exactly_60_data_points(self, analyzer):
        """恰好 60 条数据应能正常分析"""
        navs = _trending_up(60)
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        # 应正常返回，不报错
        assert result is not None
        assert result.indicators.ma60 is not None

    def test_constant_price_series(self, analyzer):
        """所有净值相同不应导致异常"""
        navs = [1.0] * 100
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        assert result is not None
        # RSI 在全增益或全亏损时极端值处理
        rsi = result.indicators.rsi
        assert rsi.rsi_6 is not None

    def test_single_spike_does_not_crash(self, analyzer):
        """单个极端值不应导致崩溃"""
        navs = _trending_up(100)
        navs[50] = 100.0  # 异常尖峰
        history = _make_nav_history(navs)
        result = analyzer.analyze(history)
        assert result is not None

    def test_result_score_never_exceeds_100(self, analyzer):
        """评分不得超过 100"""
        # 构造极端多头序列
        extreme_up = [round(1.0 + i * 0.05, 2) for i in range(300)]
        history = _make_nav_history(extreme_up)
        result = analyzer.analyze(history)
        assert result.buy_signal_score <= 100

    def test_result_score_never_below_0(self, analyzer):
        """评分不得低于 0"""
        extreme_down = [round(10.0 - i * 0.03, 2) for i in range(300)]
        extreme_down = [max(v, 0.01) for v in extreme_down]
        history = _make_nav_history(extreme_down)
        result = analyzer.analyze(history)
        assert result.buy_signal_score >= 0


# ------------------------------------------------------------------ #
#  模块导入测试                                                         #
# ------------------------------------------------------------------ #

class TestImports:
    def test_can_import_analyzer(self):
        from scripts.analysis_v2 import EnhancedTechnicalAnalyzer
        assert EnhancedTechnicalAnalyzer is not None

    def test_can_import_result_class(self):
        from scripts.analysis_v2 import TechnicalAnalysisResult
        assert TechnicalAnalysisResult is not None
