"""
风险诊断模块
计算持仓组合的集中度、同类重叠、QDII配比、亏损敞口
"""
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.logger import logger


@dataclass
class OverlapGroup:
    brand: str
    funds: List[str]   # fund_name 列表


@dataclass
class RiskReport:
    concentration_pct: float        # Top3 持仓成本占非固收总成本的百分比
    concentration_level: str        # "high" / "medium" / "low"
    overlap_groups: List[Dict]      # [{"brand": str, "funds": List[str]}] — plain dicts for easy access
    qdii_pct: float                 # QDII 成本占总持仓成本百分比
    qdii_level: str                 # "low" / "ok" / "high"
    max_loss_fund: str              # 亏损最大的基金名称
    max_loss_amount: float          # 最大亏损金额（负数或0）
    total_loss_exposure: float      # 所有亏损基金亏损总和（负数或0）
    warnings: List[str]             # 诊断预警文字列表


# 同类重叠检测：从基金名称中提取品牌关键词
_BRAND_KEYWORDS = [
    "大成", "景顺长城", "易方达", "兴全", "华夏", "南方",
    "汇添富", "华泰柏瑞", "中银", "博时", "国富", "天弘",
    "摩根", "永赢", "创金合信", "平安", "信澳", "国泰",
]


class RiskDiagnostics:
    """组合风险诊断器"""

    CONCENTRATION_HIGH = 75.0
    CONCENTRATION_MED  = 60.0
    OVERLAP_THRESHOLD = 3
    QDII_LOW  = 5.0
    QDII_HIGH = 20.0
    LOSS_SINGLE_THRESHOLD = -1000.0
    LOSS_TOTAL_THRESHOLD  = -3000.0

    def diagnose(
        self,
        holdings: List[Dict[str, Any]],
        total_portfolio_cost: Optional[float] = None,
    ) -> RiskReport:
        if not holdings:
            return RiskReport(
                concentration_pct=0.0, concentration_level="low",
                overlap_groups=[], qdii_pct=0.0, qdii_level="ok",
                max_loss_fund="", max_loss_amount=0.0,
                total_loss_exposure=0.0, warnings=[],
            )

        # Concentration
        costs = sorted(
            [(h["fund_name"], h["cost_amount"] or 0.0) for h in holdings],
            key=lambda x: x[1], reverse=True
        )
        total_non_fi_cost = sum(c for _, c in costs)
        top3_cost = sum(c for _, c in costs[:3])
        concentration_pct = (top3_cost / total_non_fi_cost * 100) if total_non_fi_cost > 0 else 0.0

        if concentration_pct > self.CONCENTRATION_HIGH:
            concentration_level = "high"
        elif concentration_pct > self.CONCENTRATION_MED:
            concentration_level = "medium"
        else:
            concentration_level = "low"

        # Overlap — store as plain dicts
        brand_map: Dict[str, List[str]] = {}
        for h in holdings:
            name = h["fund_name"]
            for brand in _BRAND_KEYWORDS:
                if brand in name:
                    brand_map.setdefault(brand, []).append(name)
                    break
        overlap_groups = [
            {"brand": b, "funds": funds}
            for b, funds in brand_map.items()
            if len(funds) >= self.OVERLAP_THRESHOLD
        ]

        # QDII
        total_cost_base = total_portfolio_cost if total_portfolio_cost else total_non_fi_cost
        qdii_cost = sum(
            (h["cost_amount"] or 0.0) for h in holdings
            if "QDII" in (h.get("fund_type") or "") or "QDII" in h.get("fund_name", "")
        )
        qdii_pct = (qdii_cost / total_cost_base * 100) if total_cost_base > 0 else 0.0

        if qdii_pct < self.QDII_LOW:
            qdii_level = "low"
        elif qdii_pct > self.QDII_HIGH:
            qdii_level = "high"
        else:
            qdii_level = "ok"

        # Loss exposure
        profits = [(h["fund_name"], h.get("stored_profit") or 0.0) for h in holdings]
        loss_entries = [(n, p) for n, p in profits if p < 0]

        if loss_entries:
            max_loss_name, max_loss_amount = min(loss_entries, key=lambda x: x[1])
            total_loss_exposure = sum(p for _, p in loss_entries)
        else:
            max_loss_name, max_loss_amount = "", 0.0
            total_loss_exposure = 0.0

        # Warnings
        warnings = []

        if concentration_level == "high":
            top3_names = [n for n, _ in costs[:3]]
            warnings.append(
                f"⚠️ 持仓集中度偏高：非固收 Top3（{'/'.join(top3_names[:2])}…）占比 {concentration_pct:.0f}%，"
                f"单只基金波动对组合影响显著，建议适当分散。"
            )
        elif concentration_level == "medium":
            warnings.append(
                f"⚡ 持仓集中度中等：Top3 占比 {concentration_pct:.0f}%，建议关注单只持仓风险。"
            )

        for og in overlap_groups:
            funds = og["funds"]
            brand = og["brand"]
            warnings.append(
                f"⚡ {brand}系基金重叠：持有 {len(funds)} 只"
                f"（{'、'.join(n[:6] for n in funds[:3])}{'…' if len(funds) > 3 else ''}），"
                f"风格趋同，可酌情合并。"
            )

        if qdii_level == "low":
            warnings.append(
                f"💡 QDII 配比不足：海外资产占总持仓 {qdii_pct:.1f}%（建议 5%~20%），"
                f"人民币资产风险集中，可适当增配全球资产。"
            )
        elif qdii_level == "high":
            warnings.append(
                f"💡 QDII 配比偏高：海外资产占总持仓 {qdii_pct:.1f}%，注意汇率风险。"
            )

        if max_loss_amount < self.LOSS_SINGLE_THRESHOLD:
            warnings.append(
                f"🔴 最大单只亏损：{max_loss_name} 亏损 ¥{abs(max_loss_amount):,.0f}，建议评估是否止损。"
            )

        if total_loss_exposure < self.LOSS_TOTAL_THRESHOLD:
            warnings.append(
                f"⚠️ 亏损总敞口：{len(loss_entries)} 只基金累计亏损 ¥{abs(total_loss_exposure):,.0f}。"
            )

        return RiskReport(
            concentration_pct=round(concentration_pct, 2),
            concentration_level=concentration_level,
            overlap_groups=overlap_groups,
            qdii_pct=round(qdii_pct, 2),
            qdii_level=qdii_level,
            max_loss_fund=max_loss_name,
            max_loss_amount=round(max_loss_amount, 2),
            total_loss_exposure=round(total_loss_exposure, 2),
            warnings=warnings,
        )
