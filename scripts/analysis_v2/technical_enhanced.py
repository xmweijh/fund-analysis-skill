"""
增强版技术分析模块
包含 MACD、RSI、BIAS (乖离率) 等高级技术指标计算
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from scripts.models import (
    FundNavHistory,
    EnhancedTechnicalIndicators,
    MACDIndicators,
    RSIIndicators,
)
from scripts.logger import logger


@dataclass
class TechnicalAnalysisResult:
    """技术分析结果"""
    indicators: EnhancedTechnicalIndicators
    buy_signal_score: int  # 0-100
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)


class EnhancedTechnicalAnalyzer:
    """增强版技术分析器，支持 MACD、RSI、BIAS 等指标"""

    # MACD 参数
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    # RSI 周期
    RSI_PERIODS = (6, 12, 24)

    # BIAS 关联均线
    BIAS_PERIODS = (5, 20, 250)

    # MA 周期
    MA_PERIODS = (5, 10, 20, 60, 250)

    # 最小所需数据量 (250 日均线)
    MIN_DATA = 60

    def analyze(self, nav_history: FundNavHistory) -> TechnicalAnalysisResult:
        """
        执行增强技术分析

        Args:
            nav_history: 净值历史数据

        Returns:
            TechnicalAnalysisResult: 包含全部技术指标及买入信号评分
        """
        navs = nav_history.navs

        if not navs or len(navs) < self.MIN_DATA:
            logger.warning(
                f"净值历史数据不足 ({len(navs) if navs else 0} 条)，"
                f"至少需要 {self.MIN_DATA} 条，返回默认结果"
            )
            return TechnicalAnalysisResult(
                indicators=EnhancedTechnicalIndicators(
                    trend="未知", formation="数据不足"
                ),
                buy_signal_score=50,
                signal_reasons=["数据不足，无法完整分析"],
                risk_factors=["历史净值数据过少"],
            )

        try:
            prices = np.array(navs, dtype=float)
            current_price = float(prices[-1])

            # --- 移动平均线 ---
            ma5 = self._calc_ma(prices, 5)
            ma10 = self._calc_ma(prices, 10)
            ma20 = self._calc_ma(prices, 20)
            ma60 = self._calc_ma(prices, 60)
            ma250 = self._calc_ma(prices, 250)

            # --- MACD ---
            macd = self._calc_macd(prices)

            # --- RSI ---
            rsi = self._calc_rsi(prices)

            # --- BIAS ---
            bias_ma5 = self._calc_bias(current_price, ma5)
            bias_ma20 = self._calc_bias(current_price, ma20)
            bias_ma250 = self._calc_bias(current_price, ma250)

            # --- 形态判断 ---
            formation = self._check_formation(ma5, ma10, ma20, ma60)

            # --- 趋势判断 ---
            trend = self._determine_trend(prices, ma20)

            # --- 技术信号列表 ---
            signals = self._detect_signals(
                current_price, ma5, ma10, ma20, ma60, ma250, macd, bias_ma20
            )

            indicators = EnhancedTechnicalIndicators(
                ma5=ma5,
                ma10=ma10,
                ma20=ma20,
                ma60=ma60,
                ma250=ma250,
                trend=trend,
                formation=formation,
                signals=signals,
                macd=macd,
                rsi=rsi,
                bias_ma5=bias_ma5,
                bias_ma20=bias_ma20,
                bias_ma250=bias_ma250,
            )

            # --- 综合评分 ---
            score, reasons, risks = self._calc_buy_signal_score(
                indicators, current_price
            )

            return TechnicalAnalysisResult(
                indicators=indicators,
                buy_signal_score=score,
                signal_reasons=reasons,
                risk_factors=risks,
            )

        except Exception as e:
            logger.error(f"增强技术分析失败: {e}", exc_info=True)
            return TechnicalAnalysisResult(
                indicators=EnhancedTechnicalIndicators(trend="未知", formation="分析失败"),
                buy_signal_score=50,
                signal_reasons=[],
                risk_factors=[f"分析异常: {e}"],
            )

    # ------------------------------------------------------------------ #
    #  内部计算方法                                                         #
    # ------------------------------------------------------------------ #

    def _calc_ma(self, prices: np.ndarray, period: int) -> Optional[float]:
        """简单移动平均"""
        if len(prices) < period:
            logger.warning(f"数据不足，无法计算 MA{period}")
            return None
        return float(np.mean(prices[-period:]))

    def _calc_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """
        指数移动平均 (EMA)

        使用标准递推公式:
            EMA_t = price_t * k + EMA_{t-1} * (1-k)
            k = 2 / (period + 1)
        初始值取前 period 个价格的简单均值。
        """
        if len(prices) < period:
            return np.array([])

        k = 2.0 / (period + 1)
        ema = np.empty(len(prices))
        # 初始 EMA 用前 period 个价格的均值
        ema[period - 1] = float(np.mean(prices[:period]))
        for i in range(period, len(prices)):
            ema[i] = prices[i] * k + ema[i - 1] * (1.0 - k)
        return ema[period - 1:]

    def _calc_macd(self, prices: np.ndarray) -> MACDIndicators:
        """
        计算 MACD 指标

        MACD 参数: EMA12 (快线), EMA26 (慢线), DEA 周期 9
        DIF = EMA12 - EMA26
        DEA = EMA(DIF, 9)
        Bar = (DIF - DEA) * 2
        """
        need = self.MACD_SLOW + self.MACD_SIGNAL
        if len(prices) < need:
            logger.warning(f"数据不足，无法计算 MACD (需要 {need} 条，现有 {len(prices)} 条)")
            return MACDIndicators(signal="未知")

        ema12 = self._calc_ema(prices, self.MACD_FAST)   # len = N - FAST + 1
        ema26 = self._calc_ema(prices, self.MACD_SLOW)   # len = N - SLOW + 1

        # 对齐到较短的 EMA26 序列
        min_len = min(len(ema12), len(ema26))
        dif_series = ema12[-min_len:] - ema26[-min_len:]

        if len(dif_series) < self.MACD_SIGNAL:
            return MACDIndicators(signal="未知")

        dea_series = self._calc_ema(dif_series, self.MACD_SIGNAL)

        if len(dea_series) < 2:
            return MACDIndicators(signal="未知")

        dif_last = float(dif_series[-1])
        dea_last = float(dea_series[-1])
        bar = (dif_last - dea_last) * 2.0

        # 判断金叉/死叉 (与前一个周期相比)
        dif_prev = float(dif_series[-(len(dea_series))])
        dea_prev = float(dea_series[-2])

        if dif_prev <= dea_prev and dif_last > dea_last:
            signal = "金叉"
        elif dif_prev >= dea_prev and dif_last < dea_last:
            signal = "死叉"
        elif dif_last > 0 and dea_last > 0:
            signal = "多头"
        else:
            signal = "空头"

        return MACDIndicators(dif=round(dif_last, 6), dea=round(dea_last, 6),
                              bar=round(bar, 6), signal=signal)

    def _calc_rsi(self, prices: np.ndarray) -> RSIIndicators:
        """
        计算多周期 RSI

        RSI = 100 - 100 / (1 + RS)
        RS  = avg_gain / avg_loss  (Wilder 平滑均值)
        """
        rsi_values: dict = {}
        for period in self.RSI_PERIODS:
            rsi_values[period] = self._calc_rsi_single(prices, period)

        rsi_6 = rsi_values.get(6)
        rsi_12 = rsi_values.get(12)
        rsi_24 = rsi_values.get(24)

        # 以 RSI12 为主确定状态
        ref_rsi = rsi_12 if rsi_12 is not None else rsi_6
        if ref_rsi is None:
            status = "中性"
        elif ref_rsi > 70:
            status = "超买"
        elif ref_rsi > 60:
            status = "强势"
        elif ref_rsi >= 40:
            status = "中性"
        elif ref_rsi >= 30:
            status = "弱势"
        else:
            status = "超卖"

        return RSIIndicators(
            rsi_6=round(rsi_6, 2) if rsi_6 is not None else None,
            rsi_12=round(rsi_12, 2) if rsi_12 is not None else None,
            rsi_24=round(rsi_24, 2) if rsi_24 is not None else None,
            status=status,
        )

    def _calc_rsi_single(self, prices: np.ndarray, period: int) -> Optional[float]:
        """计算单一周期 RSI"""
        # 至少需要 period+1 个价格才能有 period 个涨跌差
        if len(prices) < period + 1:
            logger.warning(f"数据不足，无法计算 RSI{period}")
            return None

        deltas = np.diff(prices.astype(float))
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # 初始均值 (简单均值)
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        # Wilder 平滑法计算后续值
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def _calc_bias(self, current_price: float, ma: Optional[float]) -> Optional[float]:
        """
        计算乖离率 (BIAS)

        BIAS = (Price - MA) / MA * 100
        """
        if ma is None or ma == 0:
            return None
        return round((current_price - ma) / ma * 100, 4)

    def _check_formation(
        self,
        ma5: Optional[float],
        ma10: Optional[float],
        ma20: Optional[float],
        ma60: Optional[float],
    ) -> str:
        """判断多空排列形态"""
        if None in (ma5, ma10, ma20, ma60):
            return "数据不足"
        if ma5 > ma10 > ma20 > ma60:   # type: ignore[operator]
            return "多头排列"
        if ma5 < ma10 < ma20 < ma60:   # type: ignore[operator]
            return "空头排列"
        return "无明确形态"

    def _determine_trend(self, prices: np.ndarray, ma20: Optional[float]) -> str:
        """
        判断价格趋势

        - 若当前价高于 MA20 超过 2% → 上升
        - 若低于 MA20 超过 2% → 下降
        - 否则结合近20日价格斜率辅助判断
        """
        if len(prices) < 20:
            return "未知"

        current = float(prices[-1])

        if ma20 is not None:
            if current > ma20 * 1.02:
                return "上升"
            if current < ma20 * 0.98:
                return "下降"

        # 辅助：最近20日价格线性拟合斜率
        recent = prices[-20:].astype(float)
        x = np.arange(len(recent))
        slope = float(np.polyfit(x, recent, 1)[0])

        if slope > 0:
            return "上升"
        if slope < 0:
            return "下降"
        return "震荡"

    def _detect_signals(
        self,
        current_price: float,
        ma5: Optional[float],
        ma10: Optional[float],
        ma20: Optional[float],
        ma60: Optional[float],
        ma250: Optional[float],
        macd: MACDIndicators,
        bias_ma20: Optional[float],
    ) -> List[str]:
        """汇总技术信号"""
        signals: List[str] = []

        # MA 突破信号
        if ma20 is not None:
            if current_price > ma20:
                signals.append("价格站上MA20")
            else:
                signals.append("价格跌破MA20")

        if ma250 is not None:
            if current_price > ma250:
                signals.append("价格站上年线(MA250)")
            else:
                signals.append("价格跌破年线(MA250)")

        # 均线金叉/死叉
        if ma5 is not None and ma10 is not None:
            if ma5 > ma10:
                signals.append("MA5>MA10 短期偏多")
            else:
                signals.append("MA5<MA10 短期偏空")

        # MACD 信号
        if macd.signal in ("金叉", "死叉", "多头", "空头"):
            signals.append(f"MACD {macd.signal}")

        # BIAS 超买超卖
        if bias_ma20 is not None:
            if bias_ma20 > 5:
                signals.append(f"偏离MA20过高({bias_ma20:+.1f}%)，注意超买风险")
            elif bias_ma20 < -5:
                signals.append(f"偏离MA20过低({bias_ma20:+.1f}%)，存在均值回归机会")

        return signals

    def _calc_buy_signal_score(
        self,
        indicators: EnhancedTechnicalIndicators,
        current_price: float,
    ):
        """
        综合技术评分 (0-100)

        评分维度:
        - 均线结构 (40 分)
        - MACD 信号 (25 分)
        - RSI 区间 (20 分)
        - BIAS 乖离 (15 分)
        """
        score = 50  # 基准分
        reasons: List[str] = []
        risks: List[str] = []

        # --- 均线结构 (最多 ±20) ---
        formation = indicators.formation
        if formation == "多头排列":
            score += 20
            reasons.append("均线多头排列，趋势强劲")
        elif formation == "空头排列":
            score -= 20
            risks.append("均线空头排列，趋势较弱")

        # 价格与 MA250 关系 (最多 ±10)
        bias_ma250 = indicators.bias_ma250
        if bias_ma250 is not None:
            if bias_ma250 < 0:
                add = min(10, abs(bias_ma250) * 0.5)
                score += int(add)
                reasons.append(f"价格低于年线 {bias_ma250:.1f}%，存在低估机会")
            elif bias_ma250 > 15:
                score -= 10
                risks.append(f"价格远高于年线 +{bias_ma250:.1f}%，注意回调风险")

        # --- MACD (最多 ±15) ---
        macd = indicators.macd
        if macd.signal == "金叉":
            score += 15
            reasons.append("MACD 金叉，动量转强")
        elif macd.signal == "多头":
            score += 8
            reasons.append("MACD 多头区间")
        elif macd.signal == "死叉":
            score -= 15
            risks.append("MACD 死叉，动量转弱")
        elif macd.signal == "空头":
            score -= 8
            risks.append("MACD 空头区间")

        if macd.bar is not None:
            if macd.bar > 0:
                score += 5
                reasons.append("MACD 柱状图为正，多头动能")
            else:
                score -= 5
                risks.append("MACD 柱状图为负，空头动能")

        # --- RSI (最多 ±10) ---
        rsi = indicators.rsi
        rsi_status = rsi.status
        if rsi_status == "超卖":
            score += 10
            reasons.append("RSI 超卖区间，存在反弹机会")
        elif rsi_status == "弱势":
            score += 5
            reasons.append("RSI 弱势区间，可关注底部")
        elif rsi_status == "超买":
            score -= 10
            risks.append("RSI 超买，短期或有回调压力")
        elif rsi_status == "强势":
            score += 3
            reasons.append("RSI 强势区间，趋势延续")

        # --- BIAS MA20 (最多 ±8) ---
        bias_ma20 = indicators.bias_ma20
        if bias_ma20 is not None:
            if bias_ma20 < -5:
                add = min(8, abs(bias_ma20) * 0.4)
                score += int(add)
                reasons.append(f"偏离MA20达 {bias_ma20:.1f}%，均值回归概率较高")
            elif bias_ma20 > 8:
                score -= 8
                risks.append(f"偏离MA20 +{bias_ma20:.1f}%，超买风险")

        # 收敛到 [0, 100]
        score = max(0, min(100, score))

        return score, reasons, risks
