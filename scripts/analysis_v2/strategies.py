"""
策略路由和三种分析策略实现
支持指数基金和主动基金两种主要策略
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from scripts.models import (
    FundBasicInfo,
    FiveDimensionScores,
    EnhancedTechnicalIndicators,
    ValuationData,
    PerformanceData,
    ManagerInfo,
)
from scripts.logger import logger


@dataclass
class StrategyWeights:
    """分析策略权重配置"""
    technical: float
    fundamental: float
    valuation: float
    capital_flow: float
    sentiment: float

    def __post_init__(self):
        """验证权重总和为1"""
        total = self.technical + self.fundamental + self.valuation + self.capital_flow + self.sentiment
        if not (0.99 <= total <= 1.01):  # 允许浮点误差
            raise ValueError(
                f"权重总和必须为1.0，当前为 {total}: "
                f"technical={self.technical}, fundamental={self.fundamental}, "
                f"valuation={self.valuation}, capital_flow={self.capital_flow}, "
                f"sentiment={self.sentiment}"
            )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "technical": self.technical,
            "fundamental": self.fundamental,
            "valuation": self.valuation,
            "capital_flow": self.capital_flow,
            "sentiment": self.sentiment,
        }


class AnalysisStrategy(ABC):
    """分析策略抽象基类"""

    @abstractmethod
    def get_weights(self) -> StrategyWeights:
        """获取权重配置"""
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """获取策略名称"""
        pass

    @abstractmethod
    def calculate_scores(
        self,
        technical: Optional[float] = None,
        valuation: Optional[float] = None,
        fundamental: Optional[float] = None,
        capital_flow: Optional[float] = None,
        sentiment: Optional[float] = None,
    ) -> FiveDimensionScores:
        """
        计算五维评分

        Args:
            technical: 技术面得分 (0-100)
            valuation: 估值面得分 (0-100)
            fundamental: 基本面得分 (0-100)
            capital_flow: 资金面得分 (0-100)
            sentiment: 情绪面得分 (0-100)

        Returns:
            FiveDimensionScores: 包含各维度评分和加权总分
        """
        pass


class IndexFundStrategy(AnalysisStrategy):
    """
    指数基金策略 - 估值法

    指数基金的重点在于估值水平，由于基金的净值变动主要跟随标的指数变动，
    估值低估时是更好的买入时机。

    权重配置：
    - technical: 0.25 (技术面作为辅助参考)
    - fundamental: 0.05 (基本面权重较低，指数基金不依赖选股)
    - valuation: 0.50 (估值面权重最高，这是指数基金的核心)
    - capital_flow: 0.15 (资金面用于判断市场情绪)
    - sentiment: 0.05 (舆情作为参考)
    """

    def get_weights(self) -> StrategyWeights:
        """获取指数基金策略权重"""
        return StrategyWeights(
            technical=0.25,
            fundamental=0.05,
            valuation=0.50,
            capital_flow=0.15,
            sentiment=0.05,
        )

    def get_strategy_name(self) -> str:
        """获取策略名称"""
        return "指数基金-估值法"

    def calculate_scores(
        self,
        technical: Optional[float] = None,
        valuation: Optional[float] = None,
        fundamental: Optional[float] = None,
        capital_flow: Optional[float] = None,
        sentiment: Optional[float] = None,
    ) -> FiveDimensionScores:
        """
        计算指数基金五维评分

        对于指数基金，PE percentile 是关键指标：
        - PE percentile > 80: 高估 (score < 40)
        - PE percentile 50-80: 合理 (score 40-70)
        - PE percentile < 50: 低估 (score > 70)
        """
        # 使用传入的值或设置默认值（50分）
        technical = technical or 50.0
        valuation = valuation or 50.0
        fundamental = fundamental or 50.0
        capital_flow = capital_flow or 50.0
        sentiment = sentiment or 50.0

        # 验证分数范围
        for score, name in [
            (technical, "technical"),
            (valuation, "valuation"),
            (fundamental, "fundamental"),
            (capital_flow, "capital_flow"),
            (sentiment, "sentiment"),
        ]:
            if not (0 <= score <= 100):
                raise ValueError(f"{name} 分数必须在 0-100 之间，当前值: {score}")

        weights = self.get_weights()

        # 计算加权总分
        total = (
            technical * weights.technical
            + valuation * weights.valuation
            + fundamental * weights.fundamental
            + capital_flow * weights.capital_flow
            + sentiment * weights.sentiment
        )

        # 确保总分在 0-100 范围内
        total = max(0.0, min(100.0, total))

        return FiveDimensionScores(
            technical=technical,
            fundamental=fundamental,
            valuation=valuation,
            capital_flow=capital_flow,
            sentiment=sentiment,
            total=total,
            weights=weights.to_dict(),
        )


class ActiveFundStrategy(AnalysisStrategy):
    """
    主动基金策略 - 经理法

    主动基金的重点在于基金经理的选股能力和历史表现，需要更多关注基本面分析。

    权重配置：
    - technical: 0.25 (技术面用于判断短期趋势)
    - fundamental: 0.40 (基本面权重最高，依赖经理选股能力)
    - valuation: 0.10 (估值面权重较低，不是主要考虑因素)
    - capital_flow: 0.15 (资金面用于判断市场情绪)
    - sentiment: 0.10 (舆情作为参考)
    """

    def get_weights(self) -> StrategyWeights:
        """获取主动基金策略权重"""
        return StrategyWeights(
            technical=0.25,
            fundamental=0.40,
            valuation=0.10,
            capital_flow=0.15,
            sentiment=0.10,
        )

    def get_strategy_name(self) -> str:
        """获取策略名称"""
        return "主动基金-经理法"

    def calculate_scores(
        self,
        technical: Optional[float] = None,
        valuation: Optional[float] = None,
        fundamental: Optional[float] = None,
        capital_flow: Optional[float] = None,
        sentiment: Optional[float] = None,
    ) -> FiveDimensionScores:
        """
        计算主动基金五维评分

        对于主动基金，基本面（经理能力）是关键指标：
        - 长期业绩排名百分位 > 70: 优秀经理 (fundamental score > 70)
        - 年化收益率 > 12%: 出色表现 (fundamental score > 65)
        - 最大回撤 < 20%: 风险控制好 (加分因子)
        """
        # 使用传入的值或设置默认值（50分）
        technical = technical or 50.0
        valuation = valuation or 50.0
        fundamental = fundamental or 50.0
        capital_flow = capital_flow or 50.0
        sentiment = sentiment or 50.0

        # 验证分数范围
        for score, name in [
            (technical, "technical"),
            (valuation, "valuation"),
            (fundamental, "fundamental"),
            (capital_flow, "capital_flow"),
            (sentiment, "sentiment"),
        ]:
            if not (0 <= score <= 100):
                raise ValueError(f"{name} 分数必须在 0-100 之间，当前值: {score}")

        weights = self.get_weights()

        # 计算加权总分
        total = (
            technical * weights.technical
            + valuation * weights.valuation
            + fundamental * weights.fundamental
            + capital_flow * weights.capital_flow
            + sentiment * weights.sentiment
        )

        # 确保总分在 0-100 范围内
        total = max(0.0, min(100.0, total))

        return FiveDimensionScores(
            technical=technical,
            fundamental=fundamental,
            valuation=valuation,
            capital_flow=capital_flow,
            sentiment=sentiment,
            total=total,
            weights=weights.to_dict(),
        )


class StrategyRouter:
    """
    策略路由器
    根据基金类型选择合适的分析策略
    """

    # 指数基金类型
    INDEX_FUND_TYPES = {
        "指数基金",
        "ETF联接",
        "指数增强",
        "ETF",
        "目标日期",
        "目标风险",
    }

    # 主动基金类型
    ACTIVE_FUND_TYPES = {
        "股票型",
        "混合型",
        "灵活配置",
        "偏股混合",
        "平衡混合",
        "偏债混合",
    }

    def route(self, fund_info: FundBasicInfo) -> AnalysisStrategy:
        """
        路由基金到对应的分析策略

        Args:
            fund_info: 基金基础信息

        Returns:
            AnalysisStrategy: 对应的分析策略实例

        Raises:
            ValueError: 如果基金类型为空
        """
        if not fund_info.fund_type:
            logger.warning(
                f"基金 {fund_info.fund_code} ({fund_info.fund_name}) "
                f"的类型为空，默认使用指数基金策略"
            )
            return IndexFundStrategy()

        fund_type = fund_info.fund_type.strip()

        # 检查指数基金类型（使用子字符串匹配）
        for index_type in self.INDEX_FUND_TYPES:
            if index_type in fund_type:
                logger.debug(f"基金 {fund_info.fund_code} 为指数基金类型: {fund_type}")
                return IndexFundStrategy()

        # 检查主动基金类型（使用子字符串匹配）
        for active_type in self.ACTIVE_FUND_TYPES:
            if active_type in fund_type:
                logger.debug(f"基金 {fund_info.fund_code} 为主动基金类型: {fund_type}")
                return ActiveFundStrategy()

        # 如果都不匹配，记录警告并返回默认策略
        logger.warning(
            f"基金 {fund_info.fund_code} 的类型 '{fund_type}' 不在已知类型中，"
            f"默认使用指数基金策略"
        )
        return IndexFundStrategy()

    def get_strategy_name(self, fund_info: FundBasicInfo) -> str:
        """获取基金对应的策略名称"""
        strategy = self.route(fund_info)
        return strategy.get_strategy_name()

    @staticmethod
    def get_all_fund_types() -> dict:
        """
        获取所有已知的基金类型分类

        Returns:
            dict: 包含 INDEX_FUND_TYPES 和 ACTIVE_FUND_TYPES 的字典
        """
        return {
            "index_fund_types": sorted(list(StrategyRouter.INDEX_FUND_TYPES)),
            "active_fund_types": sorted(list(StrategyRouter.ACTIVE_FUND_TYPES)),
        }
