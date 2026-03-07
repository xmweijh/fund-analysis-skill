"""
技术面分析模块
"""

from typing import List, Dict, Optional
import numpy as np

from .models import FundNavHistory, TechnicalIndicators, FundRealtimeQuote
from .logger import logger


class TechnicalAnalyzer:
    """技术面分析器"""

    def analyze(
        self,
        nav_history: FundNavHistory,
        current_quote: Optional[FundRealtimeQuote] = None
    ) -> TechnicalIndicators:
        """
        执行技术分析

        Args:
            nav_history: 净值历史数据
            current_quote: 当前实时行情

        Returns:
            TechnicalIndicators: 技术指标
        """
        if not nav_history.navs or len(nav_history.navs) < 60:
            logger.warning("净值历史数据不足,无法进行完整技术分析")
            return TechnicalIndicators(trend="未知", formation="数据不足")

        try:
            navs = nav_history.navs
            current_nav = current_quote.nav if current_quote else navs[-1]

            # 计算移动平均线
            ma5 = self.calculate_ma(navs, 5)
            ma10 = self.calculate_ma(navs, 10)
            ma20 = self.calculate_ma(navs, 20)
            ma60 = self.calculate_ma(navs, 60)

            # 判断多空排列
            formation = self.check_formation(ma5, ma10, ma20, ma60)

            # 检测技术信号
            ma_values = {'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60}
            signals = self.detect_signals(current_nav, ma_values)

            # 计算各时间段收益率
            return_30d = self.calculate_return(navs, 30)
            return_60d = self.calculate_return(navs, 60)
            return_90d = self.calculate_return(navs, 90)

            # 判断趋势
            trend = self.determine_trend(navs, ma20)

            return TechnicalIndicators(
                ma5=ma5,
                ma10=ma10,
                ma20=ma20,
                ma60=ma60,
                trend=trend,
                formation=formation,
                signals=signals,
                return_30d=return_30d,
                return_60d=return_60d,
                return_90d=return_90d
            )

        except Exception as e:
            logger.error(f"技术分析失败: {e}")
            return TechnicalIndicators(trend="未知", formation="分析失败")

    def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """
        计算简单移动平均线

        Args:
            prices: 价格列表
            period: 周期

        Returns:
            移动平均值
        """
        if len(prices) < period:
            logger.warning(f"数据不足,无法计算MA{period}")
            return None

        return float(np.mean(prices[-period:]))

    def check_formation(
        self,
        ma5: Optional[float],
        ma10: Optional[float],
        ma20: Optional[float],
        ma60: Optional[float]
    ) -> str:
        """
        判断多空排列

        Args:
            ma5: 5日均线
            ma10: 10日均线
            ma20: 20日均线
            ma60: 60日均线

        Returns:
            排列形态: 多头排列/空头排列/无明确形态
        """
        if ma5 is None or ma10 is None or ma20 is None or ma60 is None:
            return "数据不足"

        if ma5 > ma10 > ma20 > ma60:
            return "多头排列"
        elif ma5 < ma10 < ma20 < ma60:
            return "空头排列"
        else:
            return "无明确形态"

    def detect_signals(
        self,
        current_price: float,
        ma_values: Dict[str, Optional[float]]
    ) -> List[str]:
        """
        检测技术信号

        Args:
            current_price: 当前价格
            ma_values: 均线值字典

        Returns:
            技术信号列表
        """
        signals = []
        ma20 = ma_values.get('ma20')

        if ma20 is None:
            return signals

        # 突破信号
        if current_price > ma20:
            signals.append("向上突破MA20")
        elif current_price < ma20:
            signals.append("向下跌破MA20")

        # 距离MA20的偏离度
        deviation = (current_price - ma20) / ma20 * 100

        if deviation > 3:
            signals.append(f"超买信号(偏离+{deviation:.2f}%)")
        elif deviation < -3:
            signals.append(f"超卖信号(偏离{deviation:.2f}%)")

        # MA5和MA10金叉死叉
        ma5 = ma_values.get('ma5')
        ma10 = ma_values.get('ma10')

        if ma5 is not None and ma10 is not None:
            if ma5 > ma10 and current_price > ma5:
                signals.append("短期趋势向上")
            elif ma5 < ma10 and current_price < ma5:
                signals.append("短期趋势向下")

        return signals

    def calculate_return(self, prices: List[float], days: int) -> Optional[float]:
        """
        计算指定天数的收益率

        Args:
            prices: 价格列表
            days: 天数

        Returns:
            收益率(%)
        """
        if len(prices) < days:
            return None

        current_price = prices[-1]
        past_price = prices[-days]

        if past_price == 0:
            return None

        return ((current_price - past_price) / past_price) * 100

    def determine_trend(self, prices: List[float], ma20: Optional[float]) -> str:
        """
        判断趋势

        Args:
            prices: 价格列表
            ma20: 20日均线

        Returns:
            趋势: 上升/下降/震荡
        """
        if not prices or len(prices) < 30:
            return "未知"

        if ma20 is None:
            # 计算最近20天价格趋势
            recent_prices = prices[-20:]
            if recent_prices[0] < recent_prices[-1]:
                return "上升"
            elif recent_prices[0] > recent_prices[-1]:
                return "下降"
            else:
                return "震荡"
        else:
            # 根据当前价格与MA20的关系判断
            current_price = prices[-1]

            if current_price > ma20 * 1.02:
                return "上升"
            elif current_price < ma20 * 0.98:
                return "下降"
            else:
                return "震荡"
