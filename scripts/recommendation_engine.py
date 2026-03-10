"""
推荐基金引擎
基于多维度评分（技术面、基本面、舆情）推荐基金
支持按风险等级和投资期限筛选
"""

from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from scripts.models import TechnicalIndicators, HoldingAnalysis, ManagerInfo, PerformanceData, SentimentData, FundRealtimeQuote, FundBasicInfo
from scripts.logger import logger


@dataclass
class FundScore:
    """基金评分数据"""
    fund_code: str
    fund_name: str
    total_score: float  # 总分 0-100
    technical_score: float  # 技术面评分 0-100
    fundamental_score: float  # 基本面评分 0-100
    sentiment_score: float  # 舆情评分 0-100
    risk_level: str  # 风险等级: 低/中/高
    reason: str  # 推荐理由
    # 原始数据,用于生成详细推荐卡片
    performance: Optional[PerformanceData] = None
    technical: Optional[TechnicalIndicators] = None
    manager: Optional[ManagerInfo] = None
    sentiment: Optional[SentimentData] = None


@dataclass
class FundRecommendationInput:
    """基金推荐输入数据"""
    fund_code: str
    fund_name: str
    technical: Optional[TechnicalIndicators]
    holding: Optional[HoldingAnalysis]
    manager: Optional[ManagerInfo]
    performance: Optional[PerformanceData]
    sentiment: Optional[SentimentData]
    quote: Optional[FundRealtimeQuote]


class FundScorer:
    """基金评分器 - 计算综合评分"""
    
    def __init__(self):
        """初始化评分器"""
        self.tech_weight = 0.40
        self.fundamental_weight = 0.40
        self.sentiment_weight = 0.20
        logger.info("FundScorer initialized")
    
    def score(self, fund_data: FundRecommendationInput) -> FundScore:
        """
        计算基金综合评分
        
        Args:
            fund_data: 基金数据
            
        Returns:
            FundScore 评分结果
        """
        try:
            # 计算各维度评分
            tech_score = self._score_technical(fund_data.technical)
            fundamental_score = self._score_fundamental(fund_data.holding, fund_data.manager, fund_data.performance)
            sentiment_score = self._score_sentiment(fund_data.sentiment)
            
            # 加权计算总分
            total_score = (
                tech_score * self.tech_weight +
                fundamental_score * self.fundamental_weight +
                sentiment_score * self.sentiment_weight
            )
            
            # 确定风险等级
            risk_level = self._determine_risk_level(fund_data.performance, fund_data.technical)
            
            # 生成推荐理由
            reason = self._generate_reason(fund_data, tech_score, fundamental_score, sentiment_score)
            
            return FundScore(
                fund_code=fund_data.fund_code,
                fund_name=fund_data.fund_name,
                total_score=round(total_score, 2),
                technical_score=round(tech_score, 2),
                fundamental_score=round(fundamental_score, 2),
                sentiment_score=round(sentiment_score, 2),
                risk_level=risk_level,
                reason=reason,
                performance=fund_data.performance,
                technical=fund_data.technical,
                manager=fund_data.manager,
                sentiment=fund_data.sentiment
            )
        except Exception as e:
            logger.error(f"评分失败 {fund_data.fund_code}: {e}")
            # 返回默认评分
            return FundScore(
                fund_code=fund_data.fund_code,
                fund_name=fund_data.fund_name,
                total_score=50.0,
                technical_score=50.0,
                fundamental_score=50.0,
                sentiment_score=50.0,
                risk_level="中",
                reason="数据不完整，评分为默认值",
                performance=fund_data.performance,
                technical=fund_data.technical,
                manager=fund_data.manager,
                sentiment=fund_data.sentiment
            )
    
    def _score_technical(self, technical: Optional[TechnicalIndicators]) -> float:
        """
        技术面评分
        权重分解:
        - 趋势 40%: 上升=100, 震荡=70, 下降=40
        - 信号 40%: 买入信号数量 × 10（上限100）
        - 偏离度 20%: 偏离度 < 10% = 100, 10-20% = 70, > 20% = 40
        """
        if not technical:
            return 50.0
        
        try:
            # 趋势评分
            trend_scores = {
                "上升": 100.0,
                "震荡": 70.0,
                "下降": 40.0,
            }
            trend_score = trend_scores.get(technical.trend, 50.0)
            
            # 信号评分
            signal_count = len(technical.signals) if technical.signals else 0
            signal_score = min(signal_count * 10, 100.0)
            
            # 偏离度评分（从信号中推导）
            deviation_score = 70.0  # 默认中等
            for signal in (technical.signals or []):
                if "超买" in signal:
                    deviation_score = 40.0
                    break
                elif "超卖" in signal:
                    deviation_score = 80.0
            
            # 加权计算
            tech_score = (
                trend_score * 0.40 +
                signal_score * 0.40 +
                deviation_score * 0.20
            )
            
            return min(max(tech_score, 0), 100)
        except Exception as e:
            logger.warning(f"技术面评分计算失败: {e}")
            return 50.0
    
    def _score_fundamental(
        self,
        holding: Optional[HoldingAnalysis],
        manager: Optional[ManagerInfo],
        performance: Optional[PerformanceData]
    ) -> float:
        """
        基本面评分
        权重分解:
        - 收益 50%: 近3年收益率（归一化）
        - 经理 30%: 资深=90, 中等=70, 新手=50
        - 持仓 20%: 集中度 < 40% = 100, 40-60% = 70, > 60% = 40
        """
        try:
            scores = []
            weights = []
            
            # 收益评分
            if performance and performance.return_3y is not None:
                # 近3年收益：简单映射
                # 假设10%为基准，每增加10%分数增加20
                return_score = min(50 + performance.return_3y * 2, 100)
                scores.append(return_score)
                weights.append(0.50)
            
            # 经理评分
            if manager:
                manager_score = 90.0 if manager.is_senior else 70.0
                scores.append(manager_score)
                weights.append(0.30)
            
            # 持仓评分
            if holding and holding.holding_concentration is not None:
                concentration = holding.holding_concentration
                if concentration < 40:
                    concentration_score = 100.0
                elif concentration < 60:
                    concentration_score = 70.0
                else:
                    concentration_score = 40.0
                scores.append(concentration_score)
                weights.append(0.20)
            
            if not scores:
                return 50.0
            
            # 加权平均
            total_weight = sum(weights)
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            return min(max(weighted_sum / total_weight, 0), 100) if total_weight > 0 else 50.0
        except Exception as e:
            logger.warning(f"基本面评分计算失败: {e}")
            return 50.0
    
    def _score_sentiment(self, sentiment: Optional[SentimentData]) -> float:
        """舆情评分 - 直接使用情绪得分"""
        if not sentiment or sentiment.score is None:
            return 50.0
        return min(max(sentiment.score, 0), 100)
    
    def _determine_risk_level(
        self,
        performance: Optional[PerformanceData],
        technical: Optional[TechnicalIndicators]
    ) -> str:
        """
        确定风险等级: 低/中/高
        
        基于: 最大回撤、近期收益波动、趋势
        """
        try:
            risk_score = 0
            
            # 最大回撤指标 (0-10)
            if performance and performance.max_drawdown is not None:
                # 将回撤转换为正数用于计算
                abs_drawdown = abs(performance.max_drawdown)
                if abs_drawdown > 25:
                    risk_score += 4  # 高风险
                elif abs_drawdown > 15:
                    risk_score += 2  # 中风险
                elif abs_drawdown > 10:
                    risk_score += 1  # 低风险
            
            # 趋势指标 (-2 到 +2)
            if technical:
                if technical.trend == "下降":
                    risk_score += 2
                elif technical.trend == "震荡":
                    risk_score += 1
                elif technical.trend == "上升":
                    risk_score -= 1
            
            # 映射到风险等级
            if risk_score <= 0:
                return "低"
            elif risk_score <= 3:
                return "中"
            else:
                return "高"
        except Exception as e:
            logger.warning(f"风险等级判断失败: {e}")
            return "中"
    
    def _generate_reason(
        self,
        fund_data: FundRecommendationInput,
        tech_score: float,
        fundamental_score: float,
        sentiment_score: float
    ) -> str:
        """生成推荐理由"""
        reasons = []
        
        # 基本面理由
        if fund_data.performance and fund_data.performance.return_3y is not None:
            ret = fund_data.performance.return_3y
            if ret > 20:
                reasons.append(f"近3年收益{ret:.2f}%表现优异")
        
        # 技术面理由
        if fund_data.technical and fund_data.technical.trend == "上升":
            reasons.append("技术面多头排列")
        
        # 经理理由
        if fund_data.manager and fund_data.manager.is_senior:
            reasons.append("经理资深")
        
        # 舆情理由
        if fund_data.sentiment:
            if fund_data.sentiment.score > 70:
                reasons.append("舆情正面")
            elif fund_data.sentiment.score < 30:
                reasons.append("舆情偏悲观")
        
        return "，".join(reasons) if reasons else "综合评分良好"


class FundRanker:
    """基金排序器 - 排序和筛选"""
    
    @staticmethod
    def rank(
        fund_scores: List[FundScore],
        risk_level: Optional[str] = None,
        investment_period: Optional[str] = None,
        top_n: int = 10
    ) -> List[FundScore]:
        """
        排序和筛选基金
        
        Args:
            fund_scores: 基金评分列表
            risk_level: 风险等级筛选 (低/中/高, None表示不筛选)
            investment_period: 投资期限 (short/medium/long, None表示不筛选)
            top_n: 返回前N个
            
        Returns:
            排序后的基金列表
        """
        try:
            # 筛选
            filtered = fund_scores
            
            if risk_level:
                filtered = [f for f in filtered if f.risk_level == risk_level]
            
            # 按总分排序（降序）
            ranked = sorted(filtered, key=lambda f: f.total_score, reverse=True)
            
            # 返回前N个
            return ranked[:top_n]
        except Exception as e:
            logger.error(f"基金排序失败: {e}")
            return fund_scores[:top_n]
