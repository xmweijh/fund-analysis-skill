"""
基金经理分析模块
"""

from typing import Optional

from .models import ManagerInfo, PerformanceData
from .logger import logger


class ManagerAnalyzer:
    """基金经理分析器"""

    def analyze(
        self,
        manager: ManagerInfo,
        performance: Optional[PerformanceData] = None
    ) -> ManagerInfo:
        """
        执行基金经理分析

        Args:
            manager: 基金经理信息
            performance: 基金业绩数据

        Returns:
            更新的基金经理信息
        """
        try:
            # 如果有业绩数据,更新平均收益率和最大回撤
            if performance:
                if manager.avg_return == 0.0:
                    # 使用年化收益率作为平均收益率的近似
                    manager.avg_return = performance.annualized_return

                if manager.max_drawdown == 0.0:
                    # 使用最大回撤
                    manager.max_drawdown = performance.max_drawdown

            # 更新资深状态
            if manager.experience_years and manager.experience_years >= 3:
                manager.is_senior = True

            return manager

        except Exception as e:
            logger.error(f"基金经理分析失败: {e}")
            return manager
