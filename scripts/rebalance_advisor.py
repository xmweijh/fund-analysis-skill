"""
调仓建议模块
基于五维评分、收益率、动量计算调仓优先级
"""
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.logger import logger


@dataclass
class RebalanceAction:
    fund_code: str
    fund_name: str
    action: str              # "reduce" / "add" / "hold"
    priority: str            # "high" / "medium" / "low"
    rebalance_score: float
    v2_score: float
    stored_profit: float
    stored_return_rate: float
    reason: str


@dataclass
class RebalanceReport:
    reduce: List[RebalanceAction] = field(default_factory=list)
    add: List[RebalanceAction] = field(default_factory=list)
    hold: List[RebalanceAction] = field(default_factory=list)
    total_analyzed: int = 0


class RebalanceAdvisor:
    """调仓建议生成器"""

    # 减仓判断阈值
    REDUCE_SCORE_HARD = 40.0     # v2 < 40 且亏损 → 减仓候选
    REDUCE_SCORE_SOFT = 50.0     # v2 < 50 且亏损率 < -5% → 减仓候选
    REDUCE_LOSS_RATE  = -5.0     # 亏损率阈值（%）

    # 减仓高优先级阈值
    REDUCE_HIGH_SCORE    = 40.0
    REDUCE_HIGH_LOSS_RATE = -8.0

    # 加仓判断阈值
    ADD_SCORE_HIGH      = 65.0   # v2 > 65 且 tech > 60 → 加仓候选
    ADD_SCORE_LIGHT     = 60.0   # v2 > 60 且仓位 < 5000 → 加仓候选
    ADD_TECH_THRESHOLD  = 60.0
    ADD_LIGHT_POSITION  = 5000.0

    # 加仓高优先级
    ADD_HIGH_SCORE = 70.0

    def advise(self, analyses: List[Dict[str, Any]]) -> RebalanceReport:
        """
        对非固收基金分析结果生成调仓建议。

        参数
        ----
        analyses : List[Dict]
            每个 dict 含：fund_code, fund_name, v2_score, tech_score,
            stored_profit, stored_return_rate, cost_amount
        """
        report = RebalanceReport(total_analyzed=len(analyses))

        for a in analyses:
            v2    = float(a.get("v2_score") or 50.0)
            tech  = float(a.get("tech_score") or 50.0)
            profit = float(a.get("stored_profit") or 0.0)
            rate   = float(a.get("stored_return_rate") or 0.0)
            cost   = float(a.get("cost_amount") or 0.0)
            code   = a.get("fund_code", "")
            name   = a.get("fund_name", "")

            score = self._calc_rebalance_score(a)
            action_obj = self._classify(
                code, name, v2, tech, profit, rate, cost, score
            )
            if action_obj.action == "reduce":
                report.reduce.append(action_obj)
            elif action_obj.action == "add":
                report.add.append(action_obj)
            else:
                report.hold.append(action_obj)

        # 减仓按优先级（high first）再按 rebalance_score 升序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        report.reduce.sort(key=lambda x: (priority_order[x.priority], x.rebalance_score))
        # 加仓按优先级（high first）再按 rebalance_score 降序
        report.add.sort(key=lambda x: (priority_order[x.priority], -x.rebalance_score))

        return report

    def _calc_rebalance_score(self, a: Dict[str, Any]) -> float:
        """
        rebalance_score = v2_score * 0.5
                        + return_rate_score * 0.3
                        + momentum_score * 0.2

        return_rate_score: stored_return_rate 线性归一化到 0-100
            score = clamp((rate + 15) / 30 * 100, 0, 100)
            即 -15% → 0, 0% → 50, +15% → 100

        momentum_score: tech_score 直接使用（已在 0-100 范围）
        """
        v2   = float(a.get("v2_score") or 50.0)
        tech = float(a.get("tech_score") or 50.0)
        rate = float(a.get("stored_return_rate") or 0.0)

        return_rate_score = max(0.0, min(100.0, (rate + 15.0) / 30.0 * 100.0))
        momentum_score = max(0.0, min(100.0, tech))

        return round(v2 * 0.5 + return_rate_score * 0.3 + momentum_score * 0.2, 2)

    def _classify(
        self,
        code: str, name: str,
        v2: float, tech: float,
        profit: float, rate: float,
        cost: float, score: float,
    ) -> RebalanceAction:
        """判断操作方向和优先级，生成理由"""

        # ── 减仓判断 ──────────────────────────────────────────
        is_reduce = (
            (v2 < self.REDUCE_SCORE_HARD and profit < 0) or
            (v2 < self.REDUCE_SCORE_SOFT and rate < self.REDUCE_LOSS_RATE)
        )
        if is_reduce:
            if v2 < self.REDUCE_HIGH_SCORE and rate < self.REDUCE_HIGH_LOSS_RATE:
                priority = "high"
                reason = f"评分偏低（{v2:.0f}分）且亏损率达 {rate:.1f}%，建议止损减仓。"
            else:
                priority = "medium"
                reason = f"评分{v2:.0f}分，亏损率 {rate:.1f}%，建议逐步减持观察。"
            return RebalanceAction(
                fund_code=code, fund_name=name,
                action="reduce", priority=priority,
                rebalance_score=score, v2_score=v2,
                stored_profit=profit, stored_return_rate=rate,
                reason=reason,
            )

        # ── 加仓判断 ──────────────────────────────────────────
        is_add = (
            (v2 > self.ADD_SCORE_HIGH and tech > self.ADD_TECH_THRESHOLD) or
            (v2 > self.ADD_SCORE_LIGHT and cost < self.ADD_LIGHT_POSITION)
        )
        if is_add:
            if v2 > self.ADD_HIGH_SCORE:
                priority = "high"
                reason = f"评分高（{v2:.0f}分），趋势向好，可积极加仓。"
            else:
                priority = "medium"
                reason = f"评分{v2:.0f}分，仓位偏轻（¥{cost:,.0f}），可逢低补仓。"
            return RebalanceAction(
                fund_code=code, fund_name=name,
                action="add", priority=priority,
                rebalance_score=score, v2_score=v2,
                stored_profit=profit, stored_return_rate=rate,
                reason=reason,
            )

        # ── 持有 ───────────────────────────────────────────────
        return RebalanceAction(
            fund_code=code, fund_name=name,
            action="hold", priority="low",
            rebalance_score=score, v2_score=v2,
            stored_profit=profit, stored_return_rate=rate,
            reason=f"评分{v2:.0f}分，无明显减仓或加仓信号，继续持有观察。",
        )
