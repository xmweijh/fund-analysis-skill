"""
集成测试：FundAnalyzerV2 主分析器
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

# 确保项目根目录在 sys.path
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_tests_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.fund_analyzer_v2 import FundAnalyzerV2
from scripts.models import (
    FundBasicInfo,
    FundNavHistory,
    FundRealtimeQuote,
    PerformanceData,
    ManagerInfo,
    ValuationData,
    EnhancedTechnicalIndicators,
    MACDIndicators,
    RSIIndicators,
    FiveDimensionScores,
)
from scripts.analysis_v2 import TechnicalAnalysisResult
from scripts.analysis_v2.strategies import IndexFundStrategy, ActiveFundStrategy


# ================================================================== #
#  Fixtures                                                          #
# ================================================================== #


@pytest.fixture
def analyzer():
    """创建 FundAnalyzerV2 实例"""
    return FundAnalyzerV2()


@pytest.fixture
def mock_basic_info():
    """模拟基金基础信息（指数基金）"""
    return FundBasicInfo(
        fund_code="110020",
        fund_name="易方达沪深300ETF联接A",
        fund_type="指数基金",
        fund_scale=120.5,
        establish_date="2012-06-01",
        manager_name="林伟斌",
        company="易方达基金",
    )


@pytest.fixture
def mock_active_fund_info():
    """模拟主动基金基础信息"""
    return FundBasicInfo(
        fund_code="163402",
        fund_name="兴全趋势投资混合",
        fund_type="混合型",
        fund_scale=50.0,
        establish_date="2008-01-01",
        manager_name="谢志宇",
        company="兴全基金",
    )


@pytest.fixture
def mock_nav_history():
    """模拟净值历史（生成 300 个净值点）"""
    navs = [1.0 + i * 0.001 for i in range(300)]  # 单调递增
    dates = [f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}" for i in range(300)]
    return FundNavHistory(fund_code="110020", dates=dates, navs=navs)


@pytest.fixture
def mock_performance():
    """模拟业绩数据"""
    return PerformanceData(
        return_1m=2.5,
        return_3m=8.0,
        return_6m=15.0,
        return_1y=25.0,
        annualized_return=12.0,
        max_drawdown=20.0,
        rank_percentile=70.0,
    )


@pytest.fixture
def mock_manager():
    """模拟基金经理信息"""
    return ManagerInfo(
        manager_name="林伟斌",
        experience_years=10,
        manage_years=5.0,
        fund_count=3,
        avg_return=12.0,
        max_drawdown=18.0,
        is_senior=True,
    )


@pytest.fixture
def mock_quote():
    """模拟实时行情"""
    return FundRealtimeQuote(
        fund_code="110020",
        nav=1.25,
        change_pct=0.8,
        previous_nav=1.24,
        previous_nav_date="2026-05-09",
        is_estimated=False,
    )


@pytest.fixture
def mock_valuation():
    """模拟估值数据"""
    return ValuationData(
        pe_ttm=12.5,
        pb=1.35,
        pe_percentile=25.0,
        pb_percentile=30.0,
        risk_premium=5.5,
        status="低估",
        update_date="2026-05-10",
    )


@pytest.fixture
def mock_tech_indicators():
    """模拟增强技术指标"""
    return EnhancedTechnicalIndicators(
        ma5=1.25,
        ma10=1.23,
        ma20=1.20,
        ma60=1.15,
        ma250=1.10,
        trend="上升",
        formation="多头排列",
        signals=["价格站上MA20", "MACD 金叉"],
        macd=MACDIndicators(dif=0.01, dea=0.005, bar=0.01, signal="金叉"),
        rsi=RSIIndicators(rsi_6=55.0, rsi_12=60.0, rsi_24=65.0, status="强势"),
        bias_ma5=1.2,
        bias_ma20=4.0,
        bias_ma250=13.6,
    )


# ================================================================== #
#  测试：_validate_fund_code                                          #
# ================================================================== #


class TestValidateFundCode:
    def test_valid_6_digit(self, analyzer):
        assert analyzer._validate_fund_code("110020") is True
        assert analyzer._validate_fund_code("008888") is True

    def test_invalid_short(self, analyzer):
        assert analyzer._validate_fund_code("1234") is False

    def test_invalid_long(self, analyzer):
        assert analyzer._validate_fund_code("1234567") is False

    def test_invalid_non_digit(self, analyzer):
        assert analyzer._validate_fund_code("11002A") is False

    def test_empty(self, analyzer):
        assert analyzer._validate_fund_code("") is False


# ================================================================== #
#  测试：_calc_valuation_score                                        #
# ================================================================== #


class TestCalcValuationScore:
    def test_none_valuation_is_unknown(self, analyzer):
        assert analyzer._calc_valuation_score(None) is None

    def test_no_percentile_is_unknown(self, analyzer):
        val = ValuationData(status="未知")
        score = analyzer._calc_valuation_score(val)
        assert score is None

    def test_low_percentile_gives_high_score(self, analyzer):
        val = ValuationData(pe_percentile=10.0, status="低估")
        score = analyzer._calc_valuation_score(val)
        assert score == 90.0

    def test_high_percentile_gives_low_score(self, analyzer):
        val = ValuationData(pe_percentile=90.0, status="高估")
        score = analyzer._calc_valuation_score(val)
        assert score == 10.0

    def test_mid_percentile_gives_50(self, analyzer):
        val = ValuationData(pe_percentile=50.0, status="合理")
        score = analyzer._calc_valuation_score(val)
        assert score == 50.0

    def test_score_clamped_between_0_100(self, analyzer):
        val = ValuationData(pe_percentile=105.0, status="高估")
        score = analyzer._calc_valuation_score(val)
        assert 0.0 <= score <= 100.0


# ================================================================== #
#  测试：_calc_fundamental_score                                      #
# ================================================================== #


class TestCalcFundamentalScore:
    def test_none_performance_is_unknown(self, analyzer):
        assert analyzer._calc_fundamental_score(None, None) is None

    def test_high_return_boosts_score(self, analyzer, mock_performance, mock_manager):
        score = analyzer._calc_fundamental_score(mock_performance, mock_manager)
        assert score > 50.0

    def test_negative_return_lowers_score(self, analyzer):
        perf = PerformanceData(return_1y=-25.0, max_drawdown=40.0)
        score = analyzer._calc_fundamental_score(perf, None)
        assert score < 50.0

    def test_score_clamped_0_100(self, analyzer):
        perf = PerformanceData(
            return_1y=50.0,
            max_drawdown=5.0,
            rank_percentile=95.0,
        )
        mgr = ManagerInfo(
            manager_name="Test",
            is_senior=True,
            manage_years=5.0,
        )
        score = analyzer._calc_fundamental_score(perf, mgr)
        assert 0.0 <= score <= 100.0


# ================================================================== #
#  测试：_calc_capital_flow_score                                     #
# ================================================================== #


class TestCalcCapitalFlowScore:
    def test_none_is_unknown(self, analyzer):
        score = analyzer._calc_capital_flow_score(None, None)
        assert score is None

    def test_reasonable_scale_boosts_score(self, analyzer, mock_basic_info, mock_quote):
        score = analyzer._calc_capital_flow_score(mock_basic_info, mock_quote)
        assert score > 50.0  # scale=120.5 (合理) + change_pct=0.8 (小涨)

    def test_tiny_fund_lowers_score(self, analyzer):
        info = FundBasicInfo(
            fund_code="000001",
            fund_name="迷你基金",
            fund_type="混合型",
            fund_scale=0.5,
        )
        score = analyzer._calc_capital_flow_score(info, None)
        assert score < 50.0

    def test_large_drop_lowers_score(self, analyzer, mock_basic_info):
        quote = FundRealtimeQuote(fund_code="110020", nav=1.0, change_pct=-5.0)
        score = analyzer._calc_capital_flow_score(mock_basic_info, quote)
        assert score <= 50.0


# ================================================================== #
#  测试：_generate_position_advice                                    #
# ================================================================== #


class TestGeneratePositionAdvice:
    def test_high_score_gives_add_action(self, analyzer, mock_basic_info):
        scores = FiveDimensionScores(
            technical=80.0,
            fundamental=75.0,
            valuation=70.0,
            capital_flow=65.0,
            sentiment=60.0,
            total=75.0,
            weights={"technical": 0.25, "fundamental": 0.05, "valuation": 0.50,
                     "capital_flow": 0.15, "sentiment": 0.05},
        )
        advice = analyzer._generate_position_advice("110020", mock_basic_info, scores)
        assert advice["action"] == "加仓"
        assert advice["fund_code"] == "110020"

    def test_low_score_gives_reduce_action(self, analyzer, mock_basic_info):
        scores = FiveDimensionScores(
            technical=30.0,
            fundamental=25.0,
            valuation=35.0,
            capital_flow=20.0,
            sentiment=30.0,
            total=30.0,
            weights={"technical": 0.25, "fundamental": 0.05, "valuation": 0.50,
                     "capital_flow": 0.15, "sentiment": 0.05},
        )
        advice = analyzer._generate_position_advice("110020", mock_basic_info, scores)
        assert advice["action"] == "减仓"

    def test_none_scores_gives_watch_action(self, analyzer, mock_basic_info):
        advice = analyzer._generate_position_advice("110020", mock_basic_info, None)
        assert advice["action"] == "不可评价"
        assert advice["total_score"] is None
        assert advice["target_pct"] is None

    def test_returns_required_keys(self, analyzer, mock_basic_info):
        advice = analyzer._generate_position_advice("110020", mock_basic_info, None)
        for key in ("fund_code", "action", "reason", "target_pct", "min_pct", "max_pct"):
            assert key in advice, f"缺少必要的 key: {key}"


# ================================================================== #
#  测试：_generate_sip_advice                                         #
# ================================================================== #


class TestGenerateSIPAdvice:
    def test_returns_dict_with_required_keys(
        self, analyzer, mock_tech_indicators, mock_valuation
    ):
        tech_result = TechnicalAnalysisResult(
            indicators=mock_tech_indicators,
            buy_signal_score=65,
            signal_reasons=["MACD金叉"],
            risk_factors=[],
        )
        advice = analyzer._generate_sip_advice(
            fund_code="110020",
            tech_result=tech_result,
            valuation=mock_valuation,
            base_amount=1000.0,
            strategy="hybrid",
        )
        for key in ("fund_code", "strategy", "signal", "multiplier",
                    "base_amount", "recommended_amount", "confidence",
                    "reasons", "risks", "take_profit_plans"):
            assert key in advice, f"缺少必要的 key: {key}"

    def test_no_data_returns_default_advice(self, analyzer):
        advice = analyzer._generate_sip_advice(
            fund_code="110020",
            tech_result=None,
            valuation=None,
            base_amount=1000.0,
            strategy="hybrid",
        )
        assert advice["signal"] == "不可评价"
        assert advice["multiplier"] is None
        assert advice["recommended_amount"] is None

    def test_ma250_strategy(self, analyzer, mock_tech_indicators):
        tech_result = TechnicalAnalysisResult(
            indicators=mock_tech_indicators,
            buy_signal_score=60,
            signal_reasons=[],
            risk_factors=[],
        )
        advice = analyzer._generate_sip_advice(
            fund_code="110020",
            tech_result=tech_result,
            valuation=None,
            base_amount=500.0,
            strategy="ma250",
        )
        assert advice["strategy"] == "ma250"
        assert advice["base_amount"] == 500.0


# ================================================================== #
#  测试：_build_report_data                                           #
# ================================================================== #


class TestBuildReportData:
    def test_required_keys_present(
        self, analyzer, mock_basic_info, mock_quote, mock_valuation,
        mock_performance, mock_manager
    ):
        mock_tech_result = TechnicalAnalysisResult(
            indicators=EnhancedTechnicalIndicators(
                trend="上升",
                formation="多头排列",
                macd=MACDIndicators(signal="金叉"),
                rsi=RSIIndicators(status="强势"),
            ),
            buy_signal_score=65,
            signal_reasons=[],
            risk_factors=[],
        )
        scores = FiveDimensionScores(
            technical=65.0, fundamental=60.0, valuation=70.0,
            capital_flow=55.0, sentiment=50.0, total=64.75,
            weights={"technical": 0.25, "fundamental": 0.05, "valuation": 0.50,
                     "capital_flow": 0.15, "sentiment": 0.05},
        )
        strategy = IndexFundStrategy()

        data = analyzer._build_report_data(
            fund_code="110020",
            basic_info=mock_basic_info,
            quote=mock_quote,
            tech_result=mock_tech_result,
            valuation=mock_valuation,
            scores=scores,
            position_advice={"action": "加仓", "reason": "test", "total_score": 65.0,
                             "target_pct": 15.0, "min_pct": 8.0, "max_pct": 20.0},
            sip_enabled=False,
            sip_advice=None,
            performance=mock_performance,
            manager=mock_manager,
            strategy=strategy,
        )

        required_keys = [
            "fund_code", "fund_name", "fund_type", "generated_at",
            "analyzer_version", "strategy_name", "quote", "technical",
            "valuation", "scores", "performance", "position_advice",
            "sip_enabled", "sip_advice", "action", "conclusion",
        ]
        for key in required_keys:
            assert key in data, f"缺少必要的 key: {key}"

    def test_fund_code_present(self, analyzer):
        data = analyzer._build_report_data(
            fund_code="008888",
            basic_info=None,
            quote=None,
            tech_result=None,
            valuation=None,
            scores=None,
            position_advice=None,
            sip_enabled=False,
            sip_advice=None,
            performance=None,
            manager=None,
            strategy=None,
        )
        assert data["fund_code"] == "008888"
        assert data["analyzer_version"] == "v2"

    def test_sip_included_when_enabled(self, analyzer):
        sip = {"signal": "加倍定投", "multiplier": 2.0}
        data = analyzer._build_report_data(
            fund_code="008888",
            basic_info=None,
            quote=None,
            tech_result=None,
            valuation=None,
            scores=None,
            position_advice=None,
            sip_enabled=True,
            sip_advice=sip,
            performance=None,
            manager=None,
            strategy=None,
        )
        assert data["sip_enabled"] is True
        assert data["sip_advice"] == sip


# ================================================================== #
#  测试：analyze() - 集成测试（使用 mock 数据）                       #
# ================================================================== #


class TestAnalyzeIntegration:
    """集成测试：mock 所有网络调用，验证 analyze() 全流程"""

    def _patch_fetchers(self, analyzer, basic_info, nav_history, quote, performance, manager, valuation):
        """统一 patch 数据获取方法"""
        analyzer.data_fetcher.fetch_basic_info = Mock(return_value=basic_info)
        analyzer.data_fetcher.fetch_nav_history = Mock(return_value=nav_history)
        analyzer.data_fetcher.fetch_realtime_quote = Mock(return_value=quote)
        analyzer.data_fetcher.fetch_performance = Mock(return_value=performance)
        analyzer.data_fetcher.fetch_manager_info = Mock(return_value=manager)
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=valuation)

    def test_analyze_returns_tuple_of_paths(
        self, analyzer, mock_basic_info, mock_nav_history,
        mock_quote, mock_performance, mock_manager, mock_valuation, tmp_path
    ):
        """analyze() 应返回 (html_path, json_path)"""
        self._patch_fetchers(
            analyzer, mock_basic_info, mock_nav_history,
            mock_quote, mock_performance, mock_manager, mock_valuation
        )

        # patch report_generator 以避免写文件到真实目录
        mock_html = str(tmp_path / "report.html")
        mock_json = str(tmp_path / "report.json")
        # 写入假文件以满足可能的后续读取
        with open(mock_html, "w") as f:
            f.write("<html></html>")
        with open(mock_json, "w") as f:
            f.write("{}")

        analyzer.report_generator.generate = Mock(return_value=(mock_html, mock_json))

        html_path, json_path = analyzer.analyze("110020")

        assert isinstance(html_path, str)
        assert isinstance(json_path, str)
        assert html_path == mock_html
        assert json_path == mock_json

    def test_analyze_with_sip_enabled(
        self, analyzer, mock_basic_info, mock_nav_history,
        mock_quote, mock_performance, mock_manager, mock_valuation, tmp_path
    ):
        """启用定投时，sip_advice 应被包含在报告数据中"""
        self._patch_fetchers(
            analyzer, mock_basic_info, mock_nav_history,
            mock_quote, mock_performance, mock_manager, mock_valuation
        )

        captured_data = {}

        def fake_generate(data, output_dir=None):
            captured_data.update(data)
            html = str(tmp_path / "r.html")
            jsn = str(tmp_path / "r.json")
            open(html, "w").close()
            open(jsn, "w").close()
            return html, jsn

        analyzer.report_generator.generate = fake_generate

        analyzer.analyze("110020", enable_sip=True, sip_base_amount=2000.0, sip_strategy="hybrid")

        assert captured_data.get("sip_enabled") is True
        assert captured_data.get("sip_advice") is not None

    def test_analyze_invalid_fund_code_raises(self, analyzer):
        """无效基金代码应抛出 ValueError"""
        with pytest.raises(ValueError, match="无效的基金代码"):
            analyzer.analyze("123")

    def test_analyze_handles_missing_data_gracefully(
        self, analyzer, tmp_path
    ):
        """所有数据均返回 None 时应仍能生成报告，不抛出异常"""
        analyzer.data_fetcher.fetch_basic_info = Mock(return_value=None)
        analyzer.data_fetcher.fetch_nav_history = Mock(return_value=None)
        analyzer.data_fetcher.fetch_realtime_quote = Mock(return_value=None)
        analyzer.data_fetcher.fetch_performance = Mock(return_value=None)
        analyzer.data_fetcher.fetch_manager_info = Mock(return_value=None)
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=None)

        mock_html = str(tmp_path / "empty.html")
        mock_json = str(tmp_path / "empty.json")
        open(mock_html, "w").close()
        open(mock_json, "w").close()
        analyzer.report_generator.generate = Mock(return_value=(mock_html, mock_json))

        # 不应抛出异常
        html_path, json_path = analyzer.analyze("008888")
        assert html_path is not None
        assert json_path is not None

    def test_analyze_active_fund_uses_active_strategy(
        self, analyzer, mock_active_fund_info, mock_nav_history,
        mock_quote, mock_performance, mock_manager, mock_valuation, tmp_path
    ):
        """主动基金应路由到主动基金策略"""
        analyzer.data_fetcher.fetch_basic_info = Mock(return_value=mock_active_fund_info)
        analyzer.data_fetcher.fetch_nav_history = Mock(return_value=mock_nav_history)
        analyzer.data_fetcher.fetch_realtime_quote = Mock(return_value=mock_quote)
        analyzer.data_fetcher.fetch_performance = Mock(return_value=mock_performance)
        analyzer.data_fetcher.fetch_manager_info = Mock(return_value=mock_manager)
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=None)

        captured_data = {}

        def fake_generate(data, output_dir=None):
            captured_data.update(data)
            html = str(tmp_path / "r.html")
            jsn = str(tmp_path / "r.json")
            open(html, "w").close()
            open(jsn, "w").close()
            return html, jsn

        analyzer.report_generator.generate = fake_generate

        analyzer.analyze("163402")

        assert "主动基金" in captured_data.get("strategy_name", "")


# ================================================================== #
#  测试：_fetch_valuation 映射逻辑                                    #
# ================================================================== #


class TestFetchValuation:
    def test_known_fund_code_maps_to_index(self, analyzer, mock_valuation):
        """已知基金代码应映射到正确的指数代码"""
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=mock_valuation)

        result = analyzer._fetch_valuation(
            "110020",
            FundBasicInfo(fund_code="110020", fund_name="沪深300ETF联接"),
        )
        # 110020 -> 000300
        analyzer.valuation_fetcher.fetch_index_valuation.assert_called_once_with("000300")
        assert result is mock_valuation

    def test_unknown_fund_code_with_name_keyword(self, analyzer, mock_valuation):
        """通过名称关键词映射到指数"""
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(return_value=mock_valuation)

        info = FundBasicInfo(fund_code="999999", fund_name="某创业板指数基金")
        result = analyzer._fetch_valuation("999999", info)
        analyzer.valuation_fetcher.fetch_index_valuation.assert_called_once_with("SZ399006")
        assert result is mock_valuation

    def test_no_mapping_returns_none(self, analyzer):
        """无法推断指数时返回 None"""
        info = FundBasicInfo(fund_code="999999", fund_name="神秘主动基金A")
        result = analyzer._fetch_valuation("999999", info)
        assert result is None

    def test_fetch_error_returns_none(self, analyzer):
        """获取估值数据报错时应返回 None，不传播异常"""
        analyzer.valuation_fetcher.fetch_index_valuation = Mock(
            side_effect=Exception("网络错误")
        )
        info = FundBasicInfo(fund_code="110020", fund_name="沪深300ETF联接")
        result = analyzer._fetch_valuation("110020", info)
        assert result is None
