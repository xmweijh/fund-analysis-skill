"""
情绪面分析器
基于市场波动率、资金流向、市场热度等指标计算情绪评分
"""
import numpy as np
from typing import Optional, List

from scripts.models import FundNavHistory
from scripts.models_risk import SentimentMetrics
from scripts.logger import logger


class SentimentAnalyzer:
    """市场情绪分析器"""

    # 评分权重配置
    WEIGHTS = {
        "volatility": 0.40,      # 波动率权重
        "fund_flow": 0.35,       # 资金流向权重
        "search_trend": 0.15,    # 搜索热度权重
        "new_fund": 0.10,        # 新基金发行权重（反向）
    }

    # 最小数据量
    MIN_DATA_DAYS = 30

    def analyze(
        self,
        nav_history: FundNavHistory,
        recent_change_pct: Optional[float] = None,
        fund_flow_data: Optional[List[float]] = None,
    ) -> SentimentMetrics:
        """
        分析市场情绪

        Args:
            nav_history: 基金净值历史
            recent_change_pct: 近期涨跌幅（用于判断资金流向）
            fund_flow_data: 资金流向数据（可选）

        Returns:
            SentimentMetrics: 情绪指标
        """
        navs = nav_history.navs if nav_history else []

        if not navs or len(navs) < self.MIN_DATA_DAYS:
            logger.warning(f"净值数据不足 ({len(navs) if navs else 0} 天)，使用默认情绪评分")
            return SentimentMetrics()

        try:
            prices = np.array(navs, dtype=float)
            returns = np.diff(prices) / prices[:-1]

            # 1. 计算波动率评分
            volatility_score = self._calculate_volatility_score(returns)

            # 2. 计算资金流向评分
            fund_flow_score = self._calculate_fund_flow_score(
                returns, recent_change_pct, fund_flow_data
            )

            # 3. 计算搜索热度评分（简化版：基于近期波动）
            search_trend_score = self._estimate_search_trend(returns)

            # 4. 新基金发行评分（简化：基于市场热度，反向指标）
            new_fund_score = self._estimate_new_fund_score(
                volatility_score, fund_flow_score
            )

            # 5. 计算综合评分
            overall_score = self._calculate_overall_score(
                volatility_score,
                fund_flow_score,
                search_trend_score,
                new_fund_score,
            )

            # 6. 确定情绪状态
            status = self._determine_sentiment_status(overall_score)

            # 7. 生成影响因素
            factors = self._generate_factors(
                volatility_score, fund_flow_score, recent_change_pct
            )

            return SentimentMetrics(
                market_volatility_score=volatility_score,
                fund_flow_score=fund_flow_score,
                search_trend_score=search_trend_score,
                new_fund_score=new_fund_score,
                overall_sentiment_score=overall_score,
                sentiment_status=status,
                factors=factors,
            )

        except Exception as e:
            logger.error(f"情绪分析失败: {e}", exc_info=True)
            return SentimentMetrics()

    def _calculate_volatility_score(self, returns: np.ndarray) -> float:
        """
        基于波动率计算评分

        逻辑：波动率越低，市场情绪越稳定，评分越高
        """
        if len(returns) < 10:
            return 50.0

        # 计算20日滚动波动率
        window = min(20, len(returns))
        recent_vol = np.std(returns[-window:]) * np.sqrt(252)

        # 历史波动率参考
        hist_vol = np.std(returns) * np.sqrt(252)

        # 综合波动率（近期权重更高）
        combined_vol = recent_vol * 0.6 + hist_vol * 0.4

        # 转换为评分：低波动=高分
        if combined_vol < 0.10:
            score = 85.0
        elif combined_vol < 0.15:
            score = 75.0
        elif combined_vol < 0.20:
            score = 65.0
        elif combined_vol < 0.25:
            score = 55.0
        elif combined_vol < 0.30:
            score = 45.0
        else:
            score = 35.0

        return score

    def _calculate_fund_flow_score(
        self,
        returns: np.ndarray,
        recent_change_pct: Optional[float],
        fund_flow_data: Optional[List[float]],
    ) -> float:
        """
        计算资金流向评分

        逻辑：正向收益+上涨 = 资金流入（乐观）
              负向收益+下跌 = 资金流出（悲观）
        """
        if fund_flow_data and len(fund_flow_data) > 0:
            # 如果有真实资金流向数据
            avg_flow = np.mean(fund_flow_data[-30:]) if len(fund_flow_data) >= 30 else np.mean(fund_flow_data)
            # 归一化到0-100
            score = 50.0 + avg_flow * 50.0
            return max(0.0, min(100.0, score))

        # 使用收益率推断资金流向
        if len(returns) < 5:
            return 50.0

        # 近期收益率趋势
        recent_return = np.mean(returns[-5:]) * 5  # 5日累计收益

        # 结合近期涨跌幅（如果有）
        if recent_change_pct is not None:
            combined = recent_return * 100 * 0.5 + recent_change_pct * 0.5
        else:
            combined = recent_return * 100

        # 转换为评分
        if combined > 5:
            score = 85.0
        elif combined > 2:
            score = 75.0
        elif combined > 0:
            score = 65.0
        elif combined > -2:
            score = 55.0
        elif combined > -5:
            score = 40.0
        else:
            score = 25.0

        return score

    def _estimate_search_trend(self, returns: np.ndarray) -> Optional[float]:
        """
        估计搜索热度评分（简化版）

        逻辑：异常波动往往伴随搜索热度增加
        """
        if len(returns) < 10:
            return None

        # 计算异常波动天数占比
        volatility = np.std(returns)
        abnormal_moves = np.sum(np.abs(returns) > 2 * volatility)
        abnormal_ratio = abnormal_moves / len(returns)

        # 异常波动多 = 关注度高，但也可能是恐慌
        if abnormal_ratio > 0.15:
            score = 70.0  # 高关注
        elif abnormal_ratio > 0.10:
            score = 60.0
        elif abnormal_ratio > 0.05:
            score = 50.0
        else:
            score = 40.0  # 低关注

        return score

    def _estimate_new_fund_score(
        self,
        volatility_score: float,
        fund_flow_score: float,
    ) -> float:
        """
        估计新基金发行评分（反向指标）

        逻辑：市场狂热时新基金大量发行（危险信号）
              市场低迷时新基金发行困难（机会信号）
        """
        # 基于市场热度推断
        market_heat = (volatility_score + fund_flow_score) / 2

        # 热度越高，新基金发行越多（反向指标，高分=危险）
        if market_heat > 75:
            return 80.0  # 发行火爆，警惕
        elif market_heat > 60:
            return 60.0
        elif market_heat > 40:
            return 40.0
        else:
            return 20.0  # 发行困难，可能是机会

    def _calculate_overall_score(
        self,
        volatility_score: float,
        fund_flow_score: float,
        search_trend_score: Optional[float],
        new_fund_score: float,
    ) -> float:
        """
        计算综合情绪评分

        权重：
        - 波动率: 40%
        - 资金流向: 35%
        - 搜索热度: 15%
        - 新基金发行: 10%（反向，所以用100-score）
        """
        search_score = search_trend_score if search_trend_score is not None else 50.0

        overall = (
            volatility_score * self.WEIGHTS["volatility"] +
            fund_flow_score * self.WEIGHTS["fund_flow"] +
            search_score * self.WEIGHTS["search_trend"] +
            (100.0 - new_fund_score) * self.WEIGHTS["new_fund"]
        )

        return max(0.0, min(100.0, overall))

    def _determine_sentiment_status(self, overall_score: float) -> str:
        """根据综合评分确定情绪状态"""
        if overall_score >= 80:
            return "极度乐观"
        elif overall_score >= 65:
            return "乐观"
        elif overall_score >= 55:
            return "中性偏多"
        elif overall_score >= 45:
            return "中性"
        elif overall_score >= 35:
            return "中性偏空"
        elif overall_score >= 20:
            return "悲观"
        else:
            return "恐慌"

    def _generate_factors(
        self,
        volatility_score: float,
        fund_flow_score: float,
        recent_change_pct: Optional[float],
    ) -> List[str]:
        """生成情绪影响因素列表"""
        factors = []

        if volatility_score > 70:
            factors.append("市场波动率较低，情绪稳定")
        elif volatility_score < 40:
            factors.append("市场波动率较高，情绪不稳定")

        if fund_flow_score > 70:
            factors.append("资金流入明显，市场情绪积极")
        elif fund_flow_score < 40:
            factors.append("资金流出，市场情绪谨慎")

        if recent_change_pct is not None:
            if recent_change_pct > 3:
                factors.append(f"近期大涨 {recent_change_pct:.2f}%，需警惕过热")
            elif recent_change_pct < -3:
                factors.append(f"近期大跌 {recent_change_pct:.2f}%，或存机会")

        return factors
