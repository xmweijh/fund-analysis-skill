"""
测试策略路由和三种分析策略
"""

import pytest
from scripts.models import FundBasicInfo, FiveDimensionScores
from scripts.analysis_v2.strategies import (
    StrategyWeights,
    AnalysisStrategy,
    IndexFundStrategy,
    ActiveFundStrategy,
    StrategyRouter,
)


# ================================================================== #
#  Fixtures                                                          #
# ================================================================== #


@pytest.fixture
def index_fund_info() -> FundBasicInfo:
    """创建指数基金信息"""
    return FundBasicInfo(
        fund_code="110022",
        fund_name="易方达消费行业",
        fund_type="指数基金",
        fund_scale=100.5,
        establish_date="2010-01-01",
        manager_name="张亚超",
        company="易方达基金",
    )


@pytest.fixture
def etf_fund_info() -> FundBasicInfo:
    """创建ETF基金信息"""
    return FundBasicInfo(
        fund_code="510300",
        fund_name="沪深300ETF",
        fund_type="ETF",
        fund_scale=500.0,
        establish_date="2012-01-01",
        manager_name="管理员",
        company="某基金公司",
    )


@pytest.fixture
def active_fund_info() -> FundBasicInfo:
    """创建主动基金信息"""
    return FundBasicInfo(
        fund_code="163402",
        fund_name="兴全趋势投资",
        fund_type="股票型",
        fund_scale=50.0,
        establish_date="2008-01-01",
        manager_name="谢志宇",
        company="兴全基金",
    )


@pytest.fixture
def hybrid_fund_info() -> FundBasicInfo:
    """创建混合基金信息"""
    return FundBasicInfo(
        fund_code="519674",
        fund_name="银河创新成长",
        fund_type="混合型",
        fund_scale=30.0,
        establish_date="2010-01-01",
        manager_name="李蓓",
        company="银河基金",
    )


@pytest.fixture
def unknown_type_fund_info() -> FundBasicInfo:
    """创建未知类型基金"""
    return FundBasicInfo(
        fund_code="123456",
        fund_name="未知类型基金",
        fund_type="不知道",
        fund_scale=10.0,
        establish_date="2020-01-01",
        manager_name="某经理",
        company="某基金公司",
    )


@pytest.fixture
def none_type_fund_info() -> FundBasicInfo:
    """创建类型为None的基金"""
    return FundBasicInfo(
        fund_code="654321",
        fund_name="类型为空基金",
        fund_type=None,
        fund_scale=10.0,
        establish_date="2020-01-01",
        manager_name="某经理",
        company="某基金公司",
    )


@pytest.fixture
def strategy_router() -> StrategyRouter:
    """创建策略路由器"""
    return StrategyRouter()


# ================================================================== #
#  Test StrategyWeights                                              #
# ================================================================== #


class TestStrategyWeights:
    """测试策略权重"""

    def test_valid_weights_sum_to_one(self):
        """测试有效权重之和为1"""
        weights = StrategyWeights(
            technical=0.25,
            fundamental=0.40,
            valuation=0.10,
            capital_flow=0.15,
            sentiment=0.10,
        )
        assert weights.technical == 0.25
        assert weights.fundamental == 0.40
        assert weights.valuation == 0.10
        assert weights.capital_flow == 0.15
        assert weights.sentiment == 0.10

    def test_invalid_weights_not_sum_to_one(self):
        """测试权重之和不为1时抛出异常"""
        with pytest.raises(ValueError, match="权重总和必须为1.0"):
            StrategyWeights(
                technical=0.25,
                fundamental=0.40,
                valuation=0.10,
                capital_flow=0.15,
                sentiment=0.05,  # 总和为0.95
            )

    def test_weights_to_dict(self):
        """测试权重转换为字典"""
        weights = StrategyWeights(
            technical=0.25,
            fundamental=0.40,
            valuation=0.10,
            capital_flow=0.15,
            sentiment=0.10,
        )
        weights_dict = weights.to_dict()
        assert weights_dict["technical"] == 0.25
        assert weights_dict["fundamental"] == 0.40
        assert weights_dict["valuation"] == 0.10
        assert weights_dict["capital_flow"] == 0.15
        assert weights_dict["sentiment"] == 0.10
        assert len(weights_dict) == 5

    def test_weights_with_floating_point_tolerance(self):
        """测试浮点误差容差"""
        # 由于浮点计算，可能出现微小误差
        weights = StrategyWeights(
            technical=0.25,
            fundamental=0.40,
            valuation=0.10,
            capital_flow=0.15,
            sentiment=0.10000000001,  # 略微超过但在容差范围内
        )
        assert weights.sentiment > 0.10


# ================================================================== #
#  Test IndexFundStrategy                                            #
# ================================================================== #


class TestIndexFundStrategy:
    """测试指数基金策略"""

    def test_index_fund_strategy_name(self):
        """测试指数基金策略名称"""
        strategy = IndexFundStrategy()
        assert strategy.get_strategy_name() == "指数基金-估值法"

    def test_index_fund_weights(self):
        """测试指数基金权重配置"""
        strategy = IndexFundStrategy()
        weights = strategy.get_weights()

        assert weights.technical == 0.25
        assert weights.fundamental == 0.05
        assert weights.valuation == 0.50
        assert weights.capital_flow == 0.15
        assert weights.sentiment == 0.05

        # 验证权重之和为1
        total = (
            weights.technical
            + weights.fundamental
            + weights.valuation
            + weights.capital_flow
            + weights.sentiment
        )
        assert 0.99 <= total <= 1.01

    def test_index_fund_calculate_scores_with_all_params(self):
        """测试指数基金评分计算 - 提供所有参数"""
        strategy = IndexFundStrategy()
        scores = strategy.calculate_scores(
            technical=60.0,
            valuation=80.0,
            fundamental=50.0,
            capital_flow=70.0,
            sentiment=55.0,
        )

        assert isinstance(scores, FiveDimensionScores)
        assert scores.technical == 60.0
        assert scores.fundamental == 50.0
        assert scores.valuation == 80.0
        assert scores.capital_flow == 70.0
        assert scores.sentiment == 55.0

        # 验证加权总分
        # total = 60*0.25 + 50*0.05 + 80*0.50 + 70*0.15 + 55*0.05
        # total = 15 + 2.5 + 40 + 10.5 + 2.75 = 70.75
        assert 70.0 <= scores.total <= 71.5

    def test_index_fund_calculate_scores_with_defaults(self):
        """测试指数基金评分计算 - 使用默认值"""
        strategy = IndexFundStrategy()
        scores = strategy.calculate_scores()

        assert scores.technical == 50.0
        assert scores.fundamental == 50.0
        assert scores.valuation == 50.0
        assert scores.capital_flow == 50.0
        assert scores.sentiment == 50.0
        assert scores.total == 50.0  # 所有维度都是50时，加权总分也是50

    def test_index_fund_calculate_scores_with_partial_params(self):
        """测试指数基金评分计算 - 提供部分参数"""
        strategy = IndexFundStrategy()
        scores = strategy.calculate_scores(valuation=90.0, technical=40.0)

        assert scores.valuation == 90.0
        assert scores.technical == 40.0
        assert scores.fundamental == 50.0
        assert scores.capital_flow == 50.0
        assert scores.sentiment == 50.0

    def test_index_fund_calculate_scores_validates_range(self):
        """测试评分计算验证范围"""
        strategy = IndexFundStrategy()

        # 超过上限
        with pytest.raises(ValueError, match="分数必须在 0-100 之间"):
            strategy.calculate_scores(technical=101.0)

        # 低于下限
        with pytest.raises(ValueError, match="分数必须在 0-100 之间"):
            strategy.calculate_scores(valuation=-1.0)

    def test_index_fund_weights_in_scores(self):
        """测试返回的评分包含权重信息"""
        strategy = IndexFundStrategy()
        scores = strategy.calculate_scores(
            technical=60.0, valuation=80.0, fundamental=50.0
        )

        weights = scores.weights
        assert weights["technical"] == 0.25
        assert weights["valuation"] == 0.50
        assert weights["fundamental"] == 0.05


# ================================================================== #
#  Test ActiveFundStrategy                                           #
# ================================================================== #


class TestActiveFundStrategy:
    """测试主动基金策略"""

    def test_active_fund_strategy_name(self):
        """测试主动基金策略名称"""
        strategy = ActiveFundStrategy()
        assert strategy.get_strategy_name() == "主动基金-经理法"

    def test_active_fund_weights(self):
        """测试主动基金权重配置"""
        strategy = ActiveFundStrategy()
        weights = strategy.get_weights()

        assert weights.technical == 0.25
        assert weights.fundamental == 0.40
        assert weights.valuation == 0.10
        assert weights.capital_flow == 0.15
        assert weights.sentiment == 0.10

        # 验证权重之和为1
        total = (
            weights.technical
            + weights.fundamental
            + weights.valuation
            + weights.capital_flow
            + weights.sentiment
        )
        assert 0.99 <= total <= 1.01

    def test_active_fund_calculate_scores_with_all_params(self):
        """测试主动基金评分计算 - 提供所有参数"""
        strategy = ActiveFundStrategy()
        scores = strategy.calculate_scores(
            technical=60.0,
            valuation=50.0,
            fundamental=80.0,
            capital_flow=70.0,
            sentiment=65.0,
        )

        assert isinstance(scores, FiveDimensionScores)
        assert scores.technical == 60.0
        assert scores.fundamental == 80.0
        assert scores.valuation == 50.0
        assert scores.capital_flow == 70.0
        assert scores.sentiment == 65.0

        # 验证加权总分
        # total = 60*0.25 + 80*0.40 + 50*0.10 + 70*0.15 + 65*0.10
        # total = 15 + 32 + 5 + 10.5 + 6.5 = 69
        assert 68.5 <= scores.total <= 69.5

    def test_active_fund_calculate_scores_with_defaults(self):
        """测试主动基金评分计算 - 使用默认值"""
        strategy = ActiveFundStrategy()
        scores = strategy.calculate_scores()

        assert scores.technical == 50.0
        assert scores.fundamental == 50.0
        assert scores.valuation == 50.0
        assert scores.capital_flow == 50.0
        assert scores.sentiment == 50.0
        assert scores.total == 50.0

    def test_active_fund_weights_in_scores(self):
        """测试返回的评分包含权重信息"""
        strategy = ActiveFundStrategy()
        scores = strategy.calculate_scores(fundamental=75.0)

        weights = scores.weights
        assert weights["technical"] == 0.25
        assert weights["fundamental"] == 0.40
        assert weights["valuation"] == 0.10


# ================================================================== #
#  Test StrategyRouter                                               #
# ================================================================== #


class TestStrategyRouter:
    """测试策略路由器"""

    def test_route_index_fund(self, strategy_router, index_fund_info):
        """测试路由指数基金"""
        strategy = strategy_router.route(index_fund_info)
        assert isinstance(strategy, IndexFundStrategy)

    def test_route_etf(self, strategy_router, etf_fund_info):
        """测试路由ETF"""
        strategy = strategy_router.route(etf_fund_info)
        assert isinstance(strategy, IndexFundStrategy)

    def test_route_active_fund_stock(self, strategy_router, active_fund_info):
        """测试路由股票型基金"""
        strategy = strategy_router.route(active_fund_info)
        assert isinstance(strategy, ActiveFundStrategy)

    def test_route_hybrid_fund(self, strategy_router, hybrid_fund_info):
        """测试路由混合型基金"""
        strategy = strategy_router.route(hybrid_fund_info)
        assert isinstance(strategy, ActiveFundStrategy)

    def test_route_unknown_type_defaults_to_index(
        self, strategy_router, unknown_type_fund_info
    ):
        """测试未知类型默认路由到指数基金"""
        strategy = strategy_router.route(unknown_type_fund_info)
        assert isinstance(strategy, IndexFundStrategy)

    def test_route_none_type_defaults_to_index(
        self, strategy_router, none_type_fund_info
    ):
        """测试类型为None默认路由到指数基金"""
        strategy = strategy_router.route(none_type_fund_info)
        assert isinstance(strategy, IndexFundStrategy)

    def test_get_strategy_name_index_fund(self, strategy_router, index_fund_info):
        """测试获取指数基金策略名称"""
        strategy_name = strategy_router.get_strategy_name(index_fund_info)
        assert strategy_name == "指数基金-估值法"

    def test_get_strategy_name_active_fund(self, strategy_router, active_fund_info):
        """测试获取主动基金策略名称"""
        strategy_name = strategy_router.get_strategy_name(active_fund_info)
        assert strategy_name == "主动基金-经理法"

    def test_route_all_index_fund_types(self, strategy_router):
        """测试所有指数基金类型的路由"""
        index_types = ["指数基金", "ETF联接", "指数增强", "ETF", "目标日期", "目标风险"]

        for fund_type in index_types:
            fund_info = FundBasicInfo(
                fund_code="123456",
                fund_name=f"测试{fund_type}基金",
                fund_type=fund_type,
            )
            strategy = strategy_router.route(fund_info)
            assert isinstance(strategy, IndexFundStrategy), f"类型 {fund_type} 应该路由到 IndexFundStrategy"

    def test_route_all_active_fund_types(self, strategy_router):
        """测试所有主动基金类型的路由"""
        active_types = ["股票型", "混合型", "灵活配置", "偏股混合", "平衡混合", "偏债混合"]

        for fund_type in active_types:
            fund_info = FundBasicInfo(
                fund_code="123456",
                fund_name=f"测试{fund_type}基金",
                fund_type=fund_type,
            )
            strategy = strategy_router.route(fund_info)
            assert isinstance(strategy, ActiveFundStrategy), f"类型 {fund_type} 应该路由到 ActiveFundStrategy"

    def test_get_all_fund_types(self, strategy_router):
        """测试获取所有基金类型"""
        all_types = strategy_router.get_all_fund_types()

        assert "index_fund_types" in all_types
        assert "active_fund_types" in all_types

        # 验证指数基金类型
        index_types = all_types["index_fund_types"]
        assert "指数基金" in index_types
        assert "ETF" in index_types
        assert "指数增强" in index_types

        # 验证主动基金类型
        active_types = all_types["active_fund_types"]
        assert "股票型" in active_types
        assert "混合型" in active_types
        assert "灵活配置" in active_types

    def test_router_whitespace_handling(self, strategy_router):
        """测试路由器对空白字符的处理"""
        fund_info = FundBasicInfo(
            fund_code="123456",
            fund_name="测试基金",
            fund_type="  指数基金  ",  # 周围有空白
        )
        strategy = strategy_router.route(fund_info)
        assert isinstance(strategy, IndexFundStrategy)


# ================================================================== #
#  Test Integration Scenarios                                        #
# ================================================================== #


class TestIntegrationScenarios:
    """集成测试场景"""

    def test_index_fund_complete_analysis_workflow(self):
        """测试指数基金完整分析工作流"""
        # 创建指数基金
        fund_info = FundBasicInfo(
            fund_code="110022",
            fund_name="易方达消费行业",
            fund_type="指数基金",
        )

        # 路由到指数基金策略
        router = StrategyRouter()
        strategy = router.route(fund_info)

        assert strategy.get_strategy_name() == "指数基金-估值法"

        # 计算评分
        scores = strategy.calculate_scores(
            technical=55.0,  # 技术面中性
            valuation=75.0,  # 估值面良好
            fundamental=50.0,  # 基本面中性
            capital_flow=65.0,  # 资金面良好
            sentiment=50.0,  # 情绪面中性
        )

        # 验证权重
        assert scores.weights["valuation"] == 0.50
        # total = 55*0.25 + 50*0.05 + 75*0.50 + 65*0.15 + 50*0.05
        # total = 13.75 + 2.5 + 37.5 + 9.75 + 2.5 = 66
        assert 65.5 <= scores.total <= 66.5

    def test_active_fund_complete_analysis_workflow(self):
        """测试主动基金完整分析工作流"""
        # 创建主动基金
        fund_info = FundBasicInfo(
            fund_code="163402",
            fund_name="兴全趋势投资",
            fund_type="股票型",
        )

        # 路由到主动基金策略
        router = StrategyRouter()
        strategy = router.route(fund_info)

        assert strategy.get_strategy_name() == "主动基金-经理法"

        # 计算评分
        scores = strategy.calculate_scores(
            technical=60.0,  # 技术面良好
            valuation=55.0,  # 估值面中性
            fundamental=80.0,  # 基本面优秀
            capital_flow=70.0,  # 资金面良好
            sentiment=60.0,  # 情绪面良好
        )

        # 验证权重
        assert scores.weights["fundamental"] == 0.40
        # total = 60*0.25 + 80*0.40 + 55*0.10 + 70*0.15 + 60*0.10
        # total = 15 + 32 + 5.5 + 10.5 + 6 = 69
        assert 68.5 <= scores.total <= 69.5

    def test_strategy_comparison(self):
        """比较两种策略对相同数据的处理"""
        index_strategy = IndexFundStrategy()
        active_strategy = ActiveFundStrategy()

        # 使用相同的输入
        same_scores = {
            "technical": 60.0,
            "fundamental": 70.0,
            "valuation": 70.0,
            "capital_flow": 65.0,
            "sentiment": 60.0,
        }

        index_result = index_strategy.calculate_scores(**same_scores)
        active_result = active_strategy.calculate_scores(**same_scores)

        # 两个结果应该不同，因为权重不同
        assert index_result.total != active_result.total

        # 指数基金重视估值
        index_weights = index_strategy.get_weights()
        assert index_weights.valuation == 0.50

        # 主动基金重视基本面
        active_weights = active_strategy.get_weights()
        assert active_weights.fundamental == 0.40

        # 对于相同的估值和基本面分数，指数基金的总分应该更高
        # （因为估值权重更高，分数相同）
        # 实际上由于其他维度权重分配，需要具体计算
        # 这里主要是验证逻辑正确
