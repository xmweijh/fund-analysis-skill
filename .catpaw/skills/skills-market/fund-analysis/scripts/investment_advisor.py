"""
投资建议模块
"""

from typing import Dict, List, Optional

from .models import (
    TechnicalIndicators, HoldingAnalysis, ManagerInfo,
    PerformanceData, SentimentData, InvestmentAdvice
)
from .logger import logger


class InvestmentAdvisor:
    """投资建议生成器"""

    def generate_advice(
        self,
        technical: TechnicalIndicators,
        holding: HoldingAnalysis,
        manager: ManagerInfo,
        performance: PerformanceData,
        sentiment: SentimentData,
        current_nav: float
    ) -> InvestmentAdvice:
        """
        生成投资建议

        Args:
            technical: 技术分析结果
            holding: 持仓分析结果
            manager: 基金经理分析结果
            performance: 业绩分析结果
            sentiment: 舆情分析结果
            current_nav: 当前净值

        Returns:
            投资建议
        """
        try:
            # 计算综合得分
            technical_score = self._calculate_technical_score(technical)
            fundamental_score = self._calculate_fundamental_score(holding, manager, performance)
            sentiment_score = sentiment.score

            composite_score = self._calculate_composite_score(
                technical_score, fundamental_score, sentiment_score
            )

            # 确定操作建议
            action = self._determine_action(composite_score, technical)

            # 生成核心结论
            conclusion = self._generate_conclusion(action, composite_score, technical)

            # 计算买卖点位
            volatility = self._calculate_volatility(performance)
            price_points = self._calculate_price_points(current_nav, volatility, technical)

            # 生成操作检查清单
            checklist = self._generate_checklist()

            return InvestmentAdvice(
                conclusion=conclusion,
                action=action,
                ideal_buy=price_points['ideal_buy'],
                secondary_buy=price_points['secondary_buy'],
                stop_loss=price_points['stop_loss'],
                take_profit=price_points['take_profit'],
                checklist=checklist
            )

        except Exception as e:
            logger.error(f"生成投资建议失败: {e}")
            return InvestmentAdvice(
                conclusion="分析失败,请稍后重试",
                action="观望",
                checklist=[]
            )

    def _calculate_technical_score(self, technical: TechnicalIndicators) -> float:
        """计算技术面得分"""
        score = 50.0

        # 多头排列加分
        if "多头排列" in technical.formation:
            score += 20
        elif "空头排列" in technical.formation:
            score -= 20

        # 趋势判断
        if technical.trend == "上升":
            score += 15
        elif technical.trend == "下降":
            score -= 15

        # 技术信号
        positive_signals = [s for s in technical.signals if "突破" in s or "向上" in s]
        negative_signals = [s for s in technical.signals if "破位" in s or "向下" in s]

        score += len(positive_signals) * 5
        score -= len(negative_signals) * 5

        # 收益率
        if technical.return_90d and technical.return_90d > 0:
            score += 10
        elif technical.return_90d and technical.return_90d < 0:
            score -= 10

        return max(0, min(100, score))

    def _calculate_fundamental_score(
        self,
        holding: HoldingAnalysis,
        manager: ManagerInfo,
        performance: PerformanceData
    ) -> float:
        """计算基本面得分"""
        score = 50.0

        # 基金经理经验
        if manager.is_senior:
            score += 10
        if manager.experience_years and manager.experience_years >= 5:
            score += 5

        # 业绩表现
        if performance.return_1y and performance.return_1y > 10:
            score += 15
        elif performance.return_1y and performance.return_1y > 0:
            score += 5
        elif performance.return_1y and performance.return_1y < -5:
            score -= 10

        # 最大回撤
        if performance.max_drawdown and performance.max_drawdown < 10:
            score += 10
        elif performance.max_drawdown and performance.max_drawdown > 30:
            score -= 15

        # 年化收益率
        if performance.annualized_return and performance.annualized_return > 15:
            score += 10
        elif performance.annualized_return and performance.annualized_return > 8:
            score += 5

        return max(0, min(100, score))

    def _calculate_composite_score(
        self,
        technical_score: float,
        fundamental_score: float,
        sentiment_score: float
    ) -> float:
        """计算综合得分"""
        weights = [0.4, 0.4, 0.2]
        scores = [technical_score, fundamental_score, sentiment_score]

        composite = sum(s * w for s, w in zip(scores, weights))
        return round(composite, 2)

    def _determine_action(self, composite_score: float, technical: TechnicalIndicators) -> str:
        """确定操作建议"""
        if composite_score >= 80:
            return "买入"
        elif composite_score >= 60:
            if technical.trend == "上升" or "多头排列" in technical.formation:
                return "买入"
            else:
                return "持有"
        elif composite_score >= 40:
            return "持有"
        elif composite_score >= 20:
            if technical.trend == "下降" or "空头排列" in technical.formation:
                return "卖出"
            else:
                return "观望"
        else:
            return "卖出"

    def _generate_conclusion(
        self,
        action: str,
        composite_score: float,
        technical: TechnicalIndicators
    ) -> str:
        """生成核心结论"""
        trend_desc = technical.trend
        formation_desc = technical.formation

        if action == "买入":
            if "多头排列" in formation_desc:
                return f"基金技术面呈多头排列,{trend_desc}趋势明显,建议积极配置"
            else:
                return f"基金基本面稳健,{trend_desc}趋势,建议逢低买入"
        elif action == "持有":
            return f"基金表现平稳,{trend_desc}趋势,建议继续持有观察"
        elif action == "卖出":
            if "空头排列" in formation_desc:
                return f"基金技术面呈空头排列,{trend_desc}趋势,建议减仓或退出"
            else:
                return f"基金表现不佳,{trend_desc}趋势,建议谨慎持有"
        else:
            return f"基金处于{trend_desc}趋势中,建议观望等待明确信号"

    def _calculate_volatility(self, performance: PerformanceData) -> float:
        """计算波动率"""
        # 简化处理:使用最大回撤作为波动率的近似
        if performance.max_drawdown:
            return abs(performance.max_drawdown) / 100
        return 0.1  # 默认10%波动率

    def _calculate_price_points(
        self,
        current_nav: float,
        volatility: float,
        technical: TechnicalIndicators
    ) -> Dict[str, str]:
        """计算买卖点位"""
        # 理想买点: 当前价位-0.5个波动
        ideal_buy = current_nav * (1 - volatility * 0.5)

        # 次要买点: 当前价位-0.75个波动
        secondary_buy = current_nav * (1 - volatility * 0.75)

        # 止损位: 当前价位-1个波动
        stop_loss = current_nav * (1 - volatility)

        # 止盈位: 当前价位+1.5个波动
        take_profit = current_nav * (1 + volatility * 1.5)

        return {
            'ideal_buy': f"{ideal_buy:.4f}",
            'secondary_buy': f"{secondary_buy:.4f}",
            'stop_loss': f"{stop_loss:.4f}",
            'take_profit': f"{take_profit:.4f}"
        }

    def _generate_checklist(self) -> List[str]:
        """生成操作检查清单"""
        return [
            "☐ 了解基金投资方向和风险等级",
            "☐ 确认投资期限与基金类型匹配",
            "☐ 评估个人风险承受能力",
            "☐ 确认资金可用性和流动性需求",
            "☐ 了解基金费率结构(申购费、管理费、赎回费)",
            "☐ 关注基金经理的变动情况",
            "☐ 定期关注基金净值变化和业绩表现",
            "☐ 根据市场变化适时调整仓位"
        ]
