"""
风险调整指标分析器
计算夏普比率、卡玛比率、Alpha/Beta、信息比率等风险指标
"""
import numpy as np
from typing import Optional, List, Tuple

from scripts.models import FundNavHistory
from scripts.models_risk import RiskMetrics
from scripts.logger import logger


class RiskAnalyzer:
    """风险指标分析器"""

    # 年化无风险利率模型假设；不是实时观测的国债收益率。
    RISK_FREE_RATE = 0.025

    # 最小数据量要求
    MIN_DATA_DAYS = 60

    def analyze(self, nav_history: FundNavHistory,
                benchmark_history: Optional[FundNavHistory] = None) -> RiskMetrics:
        """
        计算基金的风险调整指标

        Args:
            nav_history: 基金净值历史数据

        Returns:
            RiskMetrics: 风险指标对象
        """
        navs = nav_history.navs if nav_history else []

        if not navs or len(navs) < self.MIN_DATA_DAYS:
            logger.warning(f"净值数据不足 ({len(navs) if navs else 0} 天)，无法计算风险指标")
            return RiskMetrics()

        try:
            prices = np.array(navs, dtype=float)
            if not np.all(np.isfinite(prices)) or np.any(prices <= 0):
                raise ValueError("净值必须为有限正数")
            returns = self._calculate_returns(prices)
            benchmark_returns = None
            if benchmark_history is not None:
                benchmark_prices = np.array(benchmark_history.navs, dtype=float)
                if (benchmark_history.dates == nav_history.dates
                        and len(set(nav_history.dates)) == len(prices)
                        and len(benchmark_prices) == len(prices)
                        and np.all(np.isfinite(benchmark_prices))
                        and np.all(benchmark_prices > 0)):
                    benchmark_returns = self._calculate_returns(benchmark_prices)
                else:
                    logger.warning("基准净值无效或日期未对齐，不计算相对基准指标")

            if len(returns) < 10:
                logger.warning("收益率数据不足，无法计算风险指标")
                return RiskMetrics()

            # 计算各项指标
            volatility = self._calculate_volatility(returns)
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            max_drawdown, mdd_duration = self._calculate_max_drawdown(prices)
            calmar_ratio = self._calculate_calmar_ratio(returns, max_drawdown)
            alpha, beta = self._calculate_alpha_beta(returns, benchmark_returns)
            info_ratio = self._calculate_info_ratio(returns, benchmark_returns)
            downside_dev = self._calculate_downside_deviation(returns)
            recovery_time = self._calculate_recovery_time(prices, max_drawdown)

            return RiskMetrics(
                sharpe_ratio=round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
                sortino_ratio=round(sortino_ratio, 4) if sortino_ratio is not None else None,
                calmar_ratio=round(calmar_ratio, 4) if calmar_ratio is not None else None,
                alpha=round(alpha, 4) if alpha is not None else None,
                beta=round(beta, 4) if beta is not None else None,
                info_ratio=round(info_ratio, 4) if info_ratio is not None else None,
                volatility=round(volatility, 4) if volatility is not None else None,
                downside_deviation=round(downside_dev, 4) if downside_dev is not None else None,
                max_drawdown_duration=mdd_duration,
                recovery_time=recovery_time,
            )

        except Exception as e:
            logger.error(f"风险指标计算失败: {e}", exc_info=True)
            return RiskMetrics()

    def _calculate_returns(self, prices: np.ndarray) -> np.ndarray:
        """计算日收益率序列"""
        returns = np.diff(prices) / prices[:-1]
        return returns

    def _calculate_volatility(self, returns: np.ndarray) -> Optional[float]:
        """计算年化波动率"""
        if len(returns) < 10:
            return None
        daily_vol = np.std(returns, ddof=1)
        annual_vol = daily_vol * np.sqrt(252)  # 252个交易日
        return annual_vol

    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> Optional[float]:
        """
        计算夏普比率
        Sharpe = (年化收益率 - 无风险利率) / 年化波动率
        """
        if len(returns) < 10:
            return None

        annual_return = np.mean(returns) * 252
        volatility = self._calculate_volatility(returns)

        if not volatility or volatility == 0:
            return None

        sharpe = (annual_return - self.RISK_FREE_RATE) / volatility
        return sharpe

    def _calculate_sortino_ratio(self, returns: np.ndarray) -> Optional[float]:
        """
        计算索提诺比率（只考虑下行波动）
        Sortino = (年化收益率 - 无风险利率) / 下行标准差
        """
        if len(returns) < 10:
            return None

        annual_return = np.mean(returns) * 252
        downside_dev = self._calculate_downside_deviation(returns)

        if not downside_dev or downside_dev == 0:
            return None

        sortino = (annual_return - self.RISK_FREE_RATE) / downside_dev
        return sortino

    def _calculate_downside_deviation(self, returns: np.ndarray) -> Optional[float]:
        """计算下行标准差（只考虑负收益）"""
        if len(returns) < 10:
            return None

        # MAR=0，分母包含全部观察期；无负收益时偏差为0，比率不可定义。
        downside_var = np.mean(np.minimum(returns, 0.0) ** 2)
        daily_downside_dev = np.sqrt(downside_var)
        annual_downside_dev = daily_downside_dev * np.sqrt(252)
        return annual_downside_dev

    def _calculate_max_drawdown(self, prices: np.ndarray) -> Tuple[Optional[float], Optional[int]]:
        """
        计算最大回撤及持续天数

        Returns:
            (最大回撤百分比, 持续天数)
        """
        if len(prices) < 2:
            return None, None

        peak = prices[0]
        max_drawdown = 0.0
        peak_idx = 0
        max_duration = 0

        for i, price in enumerate(prices):
            if price > peak:
                peak = price
                peak_idx = i

            drawdown = (price - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
                max_duration = i - peak_idx

        return max_drawdown, max_duration

    def _calculate_calmar_ratio(self, returns: np.ndarray, max_drawdown: Optional[float]) -> Optional[float]:
        """
        计算卡玛比率
        Calmar = 年化收益率 / |最大回撤|
        """
        if max_drawdown is None or max_drawdown >= 0:
            return None

        annual_return = np.mean(returns) * 252
        calmar = annual_return / abs(max_drawdown)
        return calmar

    def _calculate_alpha_beta(self, returns: np.ndarray, market_returns: Optional[np.ndarray] = None) -> Tuple[Optional[float], Optional[float]]:
        """
        计算Alpha和Beta

        缺少同日对齐的真实基准时返回未知，不用假设市场生成指标。
        """
        if len(returns) < 10:
            return None, None

        if market_returns is None or len(market_returns) != len(returns):
            return None, None
        if not np.all(np.isfinite(returns)) or not np.all(np.isfinite(market_returns)):
            return None, None

        # 有市场数据时的精确计算
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns, ddof=1)

        if market_variance == 0:
            return None, None
        else:
            beta = covariance / market_variance

        market_mean = np.mean(market_returns) * 252
        fund_mean = np.mean(returns) * 252
        alpha = fund_mean - self.RISK_FREE_RATE - beta * (market_mean - self.RISK_FREE_RATE)

        return alpha, beta

    def _calculate_info_ratio(self, returns: np.ndarray, benchmark_returns: Optional[np.ndarray] = None) -> Optional[float]:
        """
        计算信息比率（相对基准的超额收益/跟踪误差）

        缺少同日对齐的真实基准时返回未知。
        """
        if len(returns) < 10:
            return None

        if benchmark_returns is None or len(benchmark_returns) != len(returns):
            return None
        if not np.all(np.isfinite(returns)) or not np.all(np.isfinite(benchmark_returns)):
            return None
        excess_returns = returns - benchmark_returns

        mean_excess = np.mean(excess_returns) * 252
        tracking_error = np.std(excess_returns, ddof=1) * np.sqrt(252)

        if tracking_error == 0:
            return None

        info_ratio = mean_excess / tracking_error
        return info_ratio

    def _calculate_recovery_time(self, prices: np.ndarray, max_drawdown: Optional[float]) -> Optional[int]:
        """
        计算从最大回撤恢复到新高的平均时间
        """
        if max_drawdown is None or max_drawdown >= 0 or len(prices) < 2:
            return None

        peak = prices[0]
        in_drawdown = False
        drawdown_start = 0
        recovery_times = []

        for i, price in enumerate(prices):
            if price > peak:
                if in_drawdown:
                    recovery_times.append(i - drawdown_start)
                    in_drawdown = False
                peak = price
            else:
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = i

        if recovery_times:
            return int(np.mean(recovery_times))
        return None

    def calculate_fundamental_score(self, metrics: RiskMetrics) -> float:
        """
        基于风险指标计算基本面评分 (0-100)

        评分维度：
        - 夏普比率 (30分)
        - 卡玛比率 (25分)
        - Alpha (20分)
        - 最大回撤持续时间 (15分)
        - Beta稳定性 (10分)
        """
        score = 50.0  # 基准分

        # 夏普比率评分 (30分)
        if metrics.sharpe_ratio is not None:
            if metrics.sharpe_ratio > 1.5:
                score += 30
            elif metrics.sharpe_ratio > 1.0:
                score += 20
            elif metrics.sharpe_ratio > 0.5:
                score += 10
            elif metrics.sharpe_ratio < 0:
                score -= 10

        # 卡玛比率评分 (25分)
        if metrics.calmar_ratio is not None:
            if metrics.calmar_ratio > 2.0:
                score += 25
            elif metrics.calmar_ratio > 1.0:
                score += 15
            elif metrics.calmar_ratio > 0.5:
                score += 5

        # Alpha评分 (20分)
        if metrics.alpha is not None:
            if metrics.alpha > 0.05:
                score += 20
            elif metrics.alpha > 0.02:
                score += 10
            elif metrics.alpha < -0.05:
                score -= 10

        # 回撤恢复时间评分 (15分)
        if metrics.recovery_time is not None:
            if metrics.recovery_time < 30:
                score += 15
            elif metrics.recovery_time < 60:
                score += 10
            elif metrics.recovery_time < 90:
                score += 5

        # Beta评分 (10分) - 适中为佳
        if metrics.beta is not None:
            if 0.8 <= metrics.beta <= 1.2:
                score += 10
            elif 0.5 <= metrics.beta < 0.8 or 1.2 < metrics.beta <= 1.5:
                score += 5

        return max(0.0, min(100.0, score))
