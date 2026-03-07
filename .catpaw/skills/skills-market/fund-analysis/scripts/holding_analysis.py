"""
持仓分析模块
"""

from typing import List, Dict, Optional

from .models import HoldingAnalysis, HoldingStock
from .logger import logger


class HoldingAnalyzer:
    """持仓分析器"""

    def analyze(self, holdings: HoldingAnalysis) -> HoldingAnalysis:
        """
        执行持仓分析

        Args:
            holdings: 原始持仓数据

        Returns:
            更新的持仓分析
        """
        try:
            # 判断持仓风格
            style = self.determine_style(holdings.top10_holdings)

            holdings.style = style

            return holdings

        except Exception as e:
            logger.error(f"持仓分析失败: {e}")
            holdings.style = "未知"
            return holdings

    def determine_style(self, holdings: List[HoldingStock]) -> str:
        """
        判断持仓风格

        Args:
            holdings: 持仓列表

        Returns:
            持仓风格: 价值型/成长型/平衡型
        """
        if not holdings:
            return "未知"

        # 简化处理:根据行业分布判断
        # 实际应用中应该根据PE、PB、成长性等指标判断

        industry_keywords = {
            "成长": ["科技", "医药", "新能源", "消费", "互联网"],
            "价值": ["银行", "保险", "地产", "公用事业", "交通运输"]
        }

        growth_score = 0
        value_score = 0

        for holding in holdings:
            stock_name = holding.stock_name if holding else ""

            for keyword in industry_keywords["成长"]:
                if keyword in stock_name:
                    growth_score += 1
                    break

            for keyword in industry_keywords["价值"]:
                if keyword in stock_name:
                    value_score += 1
                    break

        if growth_score > value_score:
            return "成长型"
        elif value_score > growth_score:
            return "价值型"
        else:
            return "平衡型"
