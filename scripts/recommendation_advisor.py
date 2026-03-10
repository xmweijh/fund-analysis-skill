"""
推荐建议生成器
为推荐的基金生成详细的推荐理由和卡片
"""

from typing import List, Optional
from scripts.recommendation_engine import FundScore
from scripts.models import PerformanceData, TechnicalIndicators, ManagerInfo, SentimentData
from scripts.logger import logger


class RecommendationCardGenerator:
    """推荐卡片生成器"""
    
    @staticmethod
    def generate_card(
        rank: int,
        fund_score: FundScore,
        performance: Optional[PerformanceData] = None,
        technical: Optional[TechnicalIndicators] = None,
        manager: Optional[ManagerInfo] = None,
        sentiment: Optional[SentimentData] = None
    ) -> str:
        """
        生成推荐卡片

        Args:
            rank: 排名 (1-10)
            fund_score: 基金评分 (包含原始数据)
            performance: 业绩数据 (可选,优先使用 fund_score 中的数据)
            technical: 技术指标 (可选,优先使用 fund_score 中的数据)
            manager: 基金经理信息 (可选,优先使用 fund_score 中的数据)
            sentiment: 舆情数据 (可选,优先使用 fund_score 中的数据)

        Returns:
            Markdown 格式的推荐卡片
        """
        try:
            lines = []

            # 从 FundScore 对象中获取原始数据,如果传入参数为 None
            performance = performance or fund_score.performance
            technical = technical or fund_score.technical
            manager = manager or fund_score.manager
            sentiment = sentiment or fund_score.sentiment

            # 标题和排名
            stars = "⭐" * int(fund_score.total_score / 20)  # 每20分一颗星
            lines.append(f"### #{rank} {fund_score.fund_name} ({fund_score.fund_code})")
            lines.append(f"**综合评分**: {stars} {fund_score.total_score}/100")
            lines.append("")

            # 维度评分
            lines.append("**维度评分**:")
            lines.append(f"- 📈 技术面: {fund_score.technical_score}/100", )
            if technical and technical.trend:
                lines[-1] += f" ({technical.trend}趋势)"
            lines.append("")

            lines.append(f"- 💰 基本面: {fund_score.fundamental_score}/100")
            if performance and performance.return_3y is not None:
                lines[-1] += f" (3年收益 {performance.return_3y:+.2f}%"
                if performance.rank_percentile is not None:
                    lines[-1] += f", 超越同类 {performance.rank_percentile:.0f}%"
                lines[-1] += ")"
            lines.append("")

            lines.append(f"- 📢 舆情: {fund_score.sentiment_score}/100")
            if sentiment:
                lines[-1] += f" ({sentiment.level})"
            lines.append("")

            # 推荐理由
            lines.append(f"**推荐理由**: {fund_score.reason}")
            lines.append("")

            # 关键指标
            key_metrics = RecommendationCardGenerator._extract_key_metrics(
                performance, technical, manager
            )
            if key_metrics:
                lines.append("**关键指标**:")
                for metric in key_metrics:
                    lines.append(f"- {metric}")
                lines.append("")

            # 风险提示
            if fund_score.risk_level == "高":
                lines.append("⚠️ **风险提示**: 此基金波动较大，建议风险承受能力强的投资者选择")

            lines.append("")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"生成推荐卡片失败: {e}")
            return f"### #{rank} {fund_score.fund_name}\n评分: {fund_score.total_score}/100\n"
    
    @staticmethod
    def _extract_key_metrics(
        performance: Optional[PerformanceData],
        technical: Optional[TechnicalIndicators],
        manager: Optional[ManagerInfo]
    ) -> List[str]:
        """提取关键指标"""
        metrics = []
        
        if performance:
            if performance.return_1y is not None:
                metrics.append(f"近1年收益: {performance.return_1y:+.2f}%")
            if performance.max_drawdown is not None:
                metrics.append(f"最大回撤: {performance.max_drawdown:.2f}%")
        
        if technical:
            if technical.signals and len(technical.signals) > 0:
                signal_text = ", ".join(technical.signals[:2])  # 最多显示2个信号
                metrics.append(f"技术信号: {signal_text}")
        
        if manager:
            if manager.manager_name:
                metrics.append(f"基金经理: {manager.manager_name}")
            if manager.manage_years:
                metrics.append(f"管理年限: {manager.manage_years}年")
        
        return metrics[:4]  # 最多4个指标


class RecommendationReportGenerator:
    """推荐报告生成器"""
    
    @staticmethod
    def generate_report(
        fund_scores: List[FundScore],
        risk_level: Optional[str] = None,
        investment_period: Optional[str] = None,
        scan_count: int = 5000
    ) -> str:
        """
        生成完整推荐报告
        
        Args:
            fund_scores: 排序后的基金评分列表
            risk_level: 推荐的风险等级
            investment_period: 推荐的投资期限
            scan_count: 扫描的基金数量
            
        Returns:
            Markdown 格式的推荐报告
        """
        try:
            lines = []
            
            # 标题
            risk_label = f"{risk_level}风险" if risk_level else "各风险等级"
            period_label = RecommendationReportGenerator._get_period_label(investment_period)
            lines.append(f"# 推荐基金列表（{risk_label}，{period_label}投资）\n")
            
            # 摘要
            from datetime import datetime
            lines.append("## 📊 推荐摘要\n")
            lines.append(f"- 扫描基金数量: {scan_count}+")
            lines.append(f"- 推荐基金数: {len(fund_scores)}")
            lines.append(f"- 推荐时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"- 平均得分: {sum(f.total_score for f in fund_scores) / len(fund_scores):.2f}/100")
            lines.append("")
            
            lines.append("---\n")
            
            # 推荐列表
            lines.append("## 🏆 推荐基金\n")
            for rank, fund_score in enumerate(fund_scores, 1):
                lines.append(RecommendationCardGenerator.generate_card(rank, fund_score))
            
            # 使用建议
            lines.append("## 📌 使用建议\n")
            lines.append("- 建议定期更新分析，市场环境可能变化")
            lines.append("- 根据个人风险承受能力调整选择")
            lines.append("- 优先考虑排名前三的基金")
            lines.append("- 结合自身投资目标和时间框架综合判断")
            lines.append("- 建议咨询专业投资顾问后再做决定\n")
            
            # 免责声明
            lines.append("---\n")
            lines.append("## ⚠️ 免责声明\n")
            lines.append("本推荐仅供参考，不构成投资建议。基金投资有风险，过往业绩不代表未来表现。")
            lines.append("请根据自身风险承受能力进行投资决策。\n")
            
            return "\n".join(lines)
        
        except Exception as e:
            logger.error(f"生成推荐报告失败: {e}")
            return "# 推荐报告生成失败\n"
    
    @staticmethod
    def _get_period_label(investment_period: Optional[str]) -> str:
        """获取投资期限标签"""
        if investment_period == "short":
            return "短期（< 1年）"
        elif investment_period == "medium":
            return "中期（1-3年）"
        elif investment_period == "long":
            return "长期（> 3年）"
        else:
            return "各期限"
