"""
业绩分析模块
"""

from typing import Optional

from .models import PerformanceData
from .logger import logger


class PerformanceAnalyzer:
    """业绩分析器"""

    def analyze(self, performance: PerformanceData) -> PerformanceData:
        """
        执行业绩分析

        Args:
            performance: 原始业绩数据

        Returns:
            更新的业绩数据
        """
        try:
            # 计算年化收益率(如果未提供)
            if performance.annualized_return is None and performance.return_1y is not None:
                # 简化处理:使用1年收益率作为年化收益率的近似
                performance.annualized_return = performance.return_1y

            return performance

        except Exception as e:
            logger.error(f"业绩分析失败: {e}")
            return performance
