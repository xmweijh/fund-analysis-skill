"""
定投助手 (SIP Advisor) - 生成定投建议
支持三种策略: 年线定投法、估值定投法、混合策略
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from scripts.models import EnhancedTechnicalIndicators, ValuationData
from scripts.models_risk import RiskMetrics
from scripts.logger import logger


class SIPStrategy(str, Enum):
    """定投策略枚举"""
    MA250 = "ma250"        # 年线定投法
    VALUATION = "valuation"  # 估值定投法
    HYBRID = "hybrid"      # 混合策略


@dataclass
class TakeProfitPlan:
    """止盈计划"""
    profit_level: str      # e.g. "+10%", "+20%", "PE>70%"
    description: str       # 止盈描述


@dataclass
class SIPAdvice:
    """定投建议"""
    strategy: str          # "ma250", "valuation", "hybrid"
    signal: str           # "加倍定投", "开始定投", "正常定投", "减少定投", "停止定投"
    multiplier: float     # 定投倍数 (0-2.0+)
    base_amount: Optional[float]  # 基础定投金额
    recommended_amount: Optional[float]  # 推荐定投金额 = base_amount * multiplier
    confidence: int     # 信心度 (0-100)
    reasons: List[str] = field(default_factory=list)  # 建议理由
    risks: List[str] = field(default_factory=list)    # 风险提示
    take_profit_plans: List[TakeProfitPlan] = field(default_factory=list)  # 止盈计划
    indicators_snapshot: Optional[dict] = field(default_factory=dict)  # 指标快照


class SIPAdvisor:
    """定投策略顾问"""

    # 年线定投法的止盈计划
    MA250_TAKE_PROFIT_LEVELS = [
        (10, "+10% above MA250"),
        (20, "+20% above MA250"),
        (30, "+30% above MA250"),
    ]

    # 估值定投法的止盈计划
    VALUATION_TAKE_PROFIT_LEVELS = [
        (70, "PE > 70%分位"),
        (80, "PE > 80%分位"),
    ]

    # 回撤定投法的止盈计划
    DRAWDOWN_TAKE_PROFIT_LEVELS = [
        (15, "净值反弹+15%"),
        (25, "净值反弹+25%"),
        (40, "净值反弹+40%"),
    ]

    def get_advice(
        self,
        strategy: str,
        technical: Optional[EnhancedTechnicalIndicators] = None,
        valuation: Optional[ValuationData] = None,
        base_amount: Optional[float] = None,
        risk_metrics: Optional[RiskMetrics] = None,
        current_drawdown_pct: Optional[float] = None,
    ) -> SIPAdvice:
        """
        获取定投建议（扩展版，支持回撤策略）

        Args:
            strategy: 策略 ("ma250", "valuation", "hybrid", "drawdown")
            technical: 增强技术指标
            valuation: 估值数据
            base_amount: 基础定投金额
            risk_metrics: 风险指标（回撤策略需要）
            current_drawdown_pct: 当前回撤百分比（回撤策略需要）
        """
        strategy_lower = strategy.lower()

        if strategy_lower == "ma250":
            if technical is None:
                logger.warning("ma250 策略需要 EnhancedTechnicalIndicators，返回默认建议")
                return self._make_default_advice("ma250", base_amount)
            return self._get_ma250_advice(technical, base_amount)
        elif strategy_lower == "valuation":
            if valuation is None:
                logger.warning("valuation 策略需要 ValuationData，返回默认建议")
                return self._make_default_advice("valuation", base_amount)
            return self._get_valuation_advice(valuation, base_amount)
        elif strategy_lower == "hybrid":
            if technical is None or valuation is None:
                logger.warning("hybrid 策略需要 EnhancedTechnicalIndicators 和 ValuationData")
                if technical is None:
                    return self._make_default_advice("hybrid", base_amount)
                return self._get_ma250_advice(technical, base_amount)
            return self._get_hybrid_advice(technical, valuation, base_amount)
        elif strategy_lower == "drawdown":
            if current_drawdown_pct is None:
                logger.warning("drawdown 策略需要当前回撤数据")
                return self._make_default_advice("drawdown", base_amount)
            return self._get_drawdown_advice(current_drawdown_pct, risk_metrics, base_amount)
        else:
            logger.error(f"未知策略: {strategy}")
            return self._make_default_advice(strategy_lower, base_amount)

    # ================================================================== #
    #  年线定投法 (MA250)                                                #
    # ================================================================== #

    def _get_ma250_advice(
        self,
        technical: EnhancedTechnicalIndicators,
        base_amount: Optional[float] = None,
    ) -> SIPAdvice:
        """年线定投法"""
        bias_250 = technical.bias_ma250

        # 默认返回
        if bias_250 is None:
            logger.warning("bias_ma250 为空，返回默认建议")
            return self._make_default_advice("ma250", base_amount)

        # 根据 bias_250 确定倍数和信号
        if bias_250 < -10:
            multiplier = 2.0
            signal = "加倍定投"
            confidence = 95
        elif bias_250 < -5:
            multiplier = 1.5
            signal = "开始定投"
            confidence = 85
        elif bias_250 < 0:
            multiplier = 1.0
            signal = "正常定投"
            confidence = 75
        else:
            multiplier = 0.0
            signal = "停止定投"
            confidence = 80

        # 构建理由
        reasons = [
            f"年线偏离率: {bias_250:+.2f}%",
            self._interpret_ma250_bias(bias_250),
        ]

        # 风险提示
        risks = []
        if bias_250 > 10:
            risks.append(f"价格远高于年线 {bias_250:+.2f}%，存在调整风险")
        if technical.trend == "下降":
            risks.append("当前处于下降趋势，注意风险")

        # 止盈计划
        take_profit_plans = [
            TakeProfitPlan(
                profit_level=f"+{level}%",
                description=desc
            )
            for level, desc in self.MA250_TAKE_PROFIT_LEVELS
        ]

        recommended_amount = None
        if base_amount is not None:
            recommended_amount = base_amount * multiplier

        return SIPAdvice(
            strategy="ma250",
            signal=signal,
            multiplier=multiplier,
            base_amount=base_amount,
            recommended_amount=recommended_amount,
            confidence=confidence,
            reasons=reasons,
            risks=risks,
            take_profit_plans=take_profit_plans,
            indicators_snapshot={
                "bias_ma250": bias_250,
                "ma250": technical.ma250,
                "trend": technical.trend,
                "formation": technical.formation,
            },
        )

    def _interpret_ma250_bias(self, bias_250: float) -> str:
        """解释年线偏离率"""
        if bias_250 < -10:
            return "年线偏离度大，低估明显，适合加倍定投"
        elif bias_250 < -5:
            return "年线偏离度中等，存在低估机会"
        elif bias_250 < 0:
            return "年线略低于当前价，处于合理区间"
        else:
            return "年线偏离度为正，价格高于年线，建议等待机会"

    # ================================================================== #
    #  估值定投法 (Valuation)                                           #
    # ================================================================== #

    def _get_valuation_advice(
        self,
        valuation: ValuationData,
        base_amount: Optional[float] = None,
    ) -> SIPAdvice:
        """估值定投法"""
        pe_percentile = valuation.pe_percentile

        # 默认返回
        if pe_percentile is None:
            logger.warning("pe_percentile 为空，返回默认建议")
            return self._make_default_advice("valuation", base_amount)

        # 根据 PE 百分位确定倍数和信号
        if pe_percentile < 20:
            multiplier = 2.0
            signal = "加倍定投"
            confidence = 95
        elif pe_percentile < 35:
            multiplier = 1.5
            signal = "开始定投"
            confidence = 85
        elif pe_percentile < 50:
            multiplier = 1.0
            signal = "正常定投"
            confidence = 75
        elif pe_percentile < 70:
            multiplier = 0.5
            signal = "减少定投"
            confidence = 70
        else:
            multiplier = 0.0
            signal = "停止定投"
            confidence = 80

        # 构建理由
        reasons = [
            f"PE 百分位: {pe_percentile:.1f}%",
            self._interpret_pe_percentile(pe_percentile),
        ]

        if valuation.pe_ttm is not None:
            reasons.append(f"PE-TTM: {valuation.pe_ttm:.2f}")

        if valuation.status:
            reasons.append(f"估值状态: {valuation.status}")

        # 风险提示
        risks = []
        if pe_percentile > 70:
            risks.append(f"PE 百分位较高 {pe_percentile:.1f}%，存在估值风险")
        if valuation.status in ("高估", "极度高估"):
            risks.append(f"当前估值状态为 {valuation.status}，存在下跌风险")

        # 止盈计划
        take_profit_plans = [
            TakeProfitPlan(
                profit_level=f"PE > {level}%",
                description=desc
            )
            for level, desc in self.VALUATION_TAKE_PROFIT_LEVELS
        ]

        recommended_amount = None
        if base_amount is not None:
            recommended_amount = base_amount * multiplier

        return SIPAdvice(
            strategy="valuation",
            signal=signal,
            multiplier=multiplier,
            base_amount=base_amount,
            recommended_amount=recommended_amount,
            confidence=confidence,
            reasons=reasons,
            risks=risks,
            take_profit_plans=take_profit_plans,
            indicators_snapshot={
                "pe_percentile": pe_percentile,
                "pe_ttm": valuation.pe_ttm,
                "status": valuation.status,
            },
        )

    def _interpret_pe_percentile(self, pe_percentile: float) -> str:
        """解释 PE 百分位"""
        if pe_percentile < 20:
            return "估值处于历史低位，低估明显，适合加倍定投"
        elif pe_percentile < 35:
            return "估值处于相对低位，存在定投机会"
        elif pe_percentile < 50:
            return "估值处于中位，正常定投即可"
        elif pe_percentile < 70:
            return "估值处于相对高位，适当减少定投"
        else:
            return "估值处于历史高位，建议停止定投，等待调整"

    # ================================================================== #
    #  混合策略 (Hybrid)                                                #
    # ================================================================== #

    def _get_hybrid_advice(
        self,
        technical: EnhancedTechnicalIndicators,
        valuation: ValuationData,
        base_amount: Optional[float] = None,
    ) -> SIPAdvice:
        """混合策略 - 结合年线定投法 (40%) 和估值定投法 (60%)"""

        # 获取两个独立策略的建议
        ma250_advice = self._get_ma250_advice(technical, base_amount=1.0)
        valuation_advice = self._get_valuation_advice(valuation, base_amount=1.0)

        # 计算加权倍数
        ma250_mult = ma250_advice.multiplier
        valuation_mult = valuation_advice.multiplier
        hybrid_mult = valuation_mult * 0.6 + ma250_mult * 0.4

        # 根据混合倍数确定信号
        if hybrid_mult >= 1.8:
            signal = "加倍定投"
            confidence = 90
        elif hybrid_mult >= 1.2:
            signal = "开始定投"
            confidence = 85
        elif hybrid_mult >= 0.7:
            signal = "正常定投"
            confidence = 75
        elif hybrid_mult >= 0.3:
            signal = "减少定投"
            confidence = 70
        else:
            signal = "停止定投"
            confidence = 75

        # 合并理由
        reasons = [
            f"混合定投倍数: {hybrid_mult:.2f}x",
            f"估值策略倍数 (60%): {valuation_mult:.2f}x",
            f"年线策略倍数 (40%): {ma250_mult:.2f}x",
        ]
        reasons.extend(ma250_advice.reasons)
        reasons.extend(valuation_advice.reasons)

        # 合并风险
        risks = list(set(ma250_advice.risks + valuation_advice.risks))

        # 使用估值策略的止盈计划（更保守）
        take_profit_plans = valuation_advice.take_profit_plans

        recommended_amount = None
        if base_amount is not None:
            recommended_amount = base_amount * hybrid_mult

        return SIPAdvice(
            strategy="hybrid",
            signal=signal,
            multiplier=hybrid_mult,
            base_amount=base_amount,
            recommended_amount=recommended_amount,
            confidence=confidence,
            reasons=reasons,
            risks=risks,
            take_profit_plans=take_profit_plans,
            indicators_snapshot={
                "hybrid_multiplier": hybrid_mult,
                "valuation_multiplier": valuation_mult,
                "ma250_multiplier": ma250_mult,
                "pe_percentile": valuation.pe_percentile,
                "bias_ma250": technical.bias_ma250,
            },
        )

    # ================================================================== #
    #  回撤定投法 (Drawdown)                                             #
    # ================================================================== #

    def _get_drawdown_advice(
        self,
        current_drawdown_pct: float,
        risk_metrics: Optional[RiskMetrics],
        base_amount: Optional[float] = None,
    ) -> SIPAdvice:
        """
        回撤定投法

        逻辑：
        - 回撤 > 20%: 加倍定投 (2x)
        - 回撤 10-20%: 开始定投 (1.5x)
        - 回撤 5-10%: 正常定投 (1x)
        - 回撤 < 5%: 正常定投 (1x)
        """
        # 取绝对值确保回撤为正
        drawdown = abs(current_drawdown_pct)

        # 根据回撤幅度确定倍数
        if drawdown > 20:
            multiplier = 2.0
            signal = "加倍定投"
            confidence = 90
        elif drawdown > 10:
            multiplier = 1.5
            signal = "开始定投"
            confidence = 85
        elif drawdown > 5:
            multiplier = 1.0
            signal = "正常定投"
            confidence = 75
        else:
            multiplier = 1.0
            signal = "正常定投"
            confidence = 70

        # 构建理由
        reasons = [
            f"当前回撤: {drawdown:.1f}%",
            self._interpret_drawdown(drawdown),
        ]

        # 如果有风险指标，添加更多信息
        if risk_metrics:
            if risk_metrics.calmar_ratio:
                reasons.append(f"卡玛比率: {risk_metrics.calmar_ratio:.2f}")
            if risk_metrics.max_drawdown_duration:
                reasons.append(f"历史最大回撤持续: {risk_metrics.max_drawdown_duration}天")

        # 风险提示
        risks = []
        if drawdown < 5:
            risks.append("当前回撤较小，可能不是最佳定投时机")
        if risk_metrics and risk_metrics.calmar_ratio and risk_metrics.calmar_ratio < 0.5:
            risks.append("基金风险收益比不佳，需谨慎")

        # 止盈计划
        take_profit_plans = [
            TakeProfitPlan(profit_level=f"+{level}%", description=desc)
            for level, desc in self.DRAWDOWN_TAKE_PROFIT_LEVELS
        ]

        recommended_amount = None
        if base_amount is not None:
            recommended_amount = base_amount * multiplier

        return SIPAdvice(
            strategy="drawdown",
            signal=signal,
            multiplier=multiplier,
            base_amount=base_amount,
            recommended_amount=recommended_amount,
            confidence=confidence,
            reasons=reasons,
            risks=risks,
            take_profit_plans=take_profit_plans,
            indicators_snapshot={
                "current_drawdown_pct": drawdown,
                "calmar_ratio": risk_metrics.calmar_ratio if risk_metrics else None,
            },
        )

    def _interpret_drawdown(self, drawdown: float) -> str:
        """解释回撤程度"""
        if drawdown > 20:
            return "深度回撤，具备较好的定投机会"
        elif drawdown > 10:
            return "中度回撤，可以开始定投布局"
        elif drawdown > 5:
            return "轻度回撤，正常定投即可"
        else:
            return "回撤较小，等待更好时机"

    # ================================================================== #
    #  辅助方法                                                         #
    # ================================================================== #

    def _make_default_advice(
        self,
        strategy: str,
        base_amount: Optional[float] = None,
    ) -> SIPAdvice:
        """构造默认建议（数据不足时）"""
        return SIPAdvice(
            strategy=strategy,
            signal="正常定投",
            multiplier=1.0,
            base_amount=base_amount,
            recommended_amount=base_amount if base_amount else None,
            confidence=50,
            reasons=["数据不足，使用默认定投策略"],
            risks=["信息不完整，建议等待数据完善"],
            take_profit_plans=[],
            indicators_snapshot={},
        )
