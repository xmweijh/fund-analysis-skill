"""
风险指标和情绪指标数据模型
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class RiskMetrics:
    """风险调整收益指标"""
    sharpe_ratio: Optional[float] = None          # 夏普比率
    sortino_ratio: Optional[float] = None         # 索提诺比率
    calmar_ratio: Optional[float] = None          # 卡玛比率
    alpha: Optional[float] = None                 # Alpha (超额收益)
    beta: Optional[float] = None                  # Beta (系统风险)
    info_ratio: Optional[float] = None            # 信息比率
    volatility: Optional[float] = None            # 年化波动率
    downside_deviation: Optional[float] = None    # 下行标准差
    max_drawdown_duration: Optional[int] = None   # 最大回撤持续天数
    recovery_time: Optional[int] = None           # 恢复时间(天)

    def to_dict(self) -> dict:
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "alpha": self.alpha,
            "beta": self.beta,
            "info_ratio": self.info_ratio,
            "volatility": self.volatility,
            "downside_deviation": self.downside_deviation,
            "max_drawdown_duration": self.max_drawdown_duration,
            "recovery_time": self.recovery_time,
        }


@dataclass
class SentimentMetrics:
    """市场情绪指标"""
    market_volatility_score: float = 50.0         # 市场波动率评分 (0-100)
    fund_flow_score: float = 50.0                 # 资金流向评分 (0-100)
    search_trend_score: Optional[float] = None    # 搜索热度评分 (0-100)
    new_fund_score: Optional[float] = None        # 新基金发行评分 (0-100, 反向指标)
    overall_sentiment_score: float = 50.0         # 综合情绪评分 (0-100)
    sentiment_status: str = "中性"                # 情绪状态描述
    factors: List[str] = field(default_factory=list)  # 影响因素列表

    def to_dict(self) -> dict:
        return {
            "market_volatility_score": self.market_volatility_score,
            "fund_flow_score": self.fund_flow_score,
            "search_trend_score": self.search_trend_score,
            "new_fund_score": self.new_fund_score,
            "overall_sentiment_score": self.overall_sentiment_score,
            "sentiment_status": self.sentiment_status,
            "factors": self.factors,
        }
