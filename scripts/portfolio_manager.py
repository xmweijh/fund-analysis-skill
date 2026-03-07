"""
用户持仓管理模块
支持用户持仓列表的增删改查，数据持久化存储到 JSON 文件
"""

import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from .logger import logger

# 持仓文件默认路径
_DEFAULT_PORTFOLIO_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "portfolio.json"
)


class PortfolioEntry:
    """单条持仓记录"""

    def __init__(
        self,
        fund_code: str,
        fund_name: Optional[str] = None,
        shares: Optional[float] = None,        # 持有份额
        cost_nav: Optional[float] = None,      # 买入净值(成本价)
        cost_amount: Optional[float] = None,   # 买入金额
        note: Optional[str] = None,            # 备注
        added_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.fund_code = fund_code
        self.fund_name = fund_name
        self.shares = shares
        self.cost_nav = cost_nav
        self.cost_amount = cost_amount
        self.note = note
        self.added_at = added_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = updated_at or self.added_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "shares": self.shares,
            "cost_nav": self.cost_nav,
            "cost_amount": self.cost_amount,
            "note": self.note,
            "added_at": self.added_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioEntry":
        return cls(
            fund_code=d["fund_code"],
            fund_name=d.get("fund_name"),
            shares=d.get("shares"),
            cost_nav=d.get("cost_nav"),
            cost_amount=d.get("cost_amount"),
            note=d.get("note"),
            added_at=d.get("added_at"),
            updated_at=d.get("updated_at"),
        )


class PortfolioManager:
    """
    用户持仓管理器
    负责持仓列表的增删改查和 JSON 持久化
    """

    def __init__(self, portfolio_path: Optional[str] = None):
        self._path = portfolio_path or _DEFAULT_PORTFOLIO_PATH
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._entries: Dict[str, PortfolioEntry] = {}
        self._load()

    # ─────────────────────────────── 持久化 ───────────────────────────────

    def _load(self):
        """从 JSON 文件加载持仓"""
        if not os.path.exists(self._path):
            logger.info("持仓文件不存在，将创建新文件")
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw: List[Dict] = json.load(f)
            self._entries = {
                item["fund_code"]: PortfolioEntry.from_dict(item) for item in raw
            }
            logger.info(f"已加载 {len(self._entries)} 条持仓记录")
        except Exception as e:
            logger.error(f"加载持仓文件失败: {e}")
            self._entries = {}

    def _save(self):
        """将持仓写入 JSON 文件"""
        try:
            data = [entry.to_dict() for entry in self._entries.values()]
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"持仓已保存（共 {len(data)} 条）")
        except Exception as e:
            logger.error(f"保存持仓文件失败: {e}")

    # ─────────────────────────────── CRUD ────────────────────────────────

    def add(
        self,
        fund_code: str,
        fund_name: Optional[str] = None,
        shares: Optional[float] = None,
        cost_nav: Optional[float] = None,
        cost_amount: Optional[float] = None,
        note: Optional[str] = None,
    ) -> PortfolioEntry:
        """
        新增一条持仓。若已存在则更新。
        返回最终的 PortfolioEntry。
        """
        if fund_code in self._entries:
            return self.update(
                fund_code,
                fund_name=fund_name,
                shares=shares,
                cost_nav=cost_nav,
                cost_amount=cost_amount,
                note=note,
            )
        entry = PortfolioEntry(
            fund_code=fund_code,
            fund_name=fund_name,
            shares=shares,
            cost_nav=cost_nav,
            cost_amount=cost_amount,
            note=note,
        )
        self._entries[fund_code] = entry
        self._save()
        logger.info(f"新增持仓: {fund_code} {fund_name or ''}")
        return entry

    def update(
        self,
        fund_code: str,
        fund_name: Optional[str] = None,
        shares: Optional[float] = None,
        cost_nav: Optional[float] = None,
        cost_amount: Optional[float] = None,
        note: Optional[str] = None,
    ) -> PortfolioEntry:
        """
        更新已有持仓（只更新非 None 的字段）。
        若不存在则先添加。
        """
        if fund_code not in self._entries:
            return self.add(
                fund_code,
                fund_name=fund_name,
                shares=shares,
                cost_nav=cost_nav,
                cost_amount=cost_amount,
                note=note,
            )
        entry = self._entries[fund_code]
        if fund_name is not None:
            entry.fund_name = fund_name
        if shares is not None:
            entry.shares = shares
        if cost_nav is not None:
            entry.cost_nav = cost_nav
        if cost_amount is not None:
            entry.cost_amount = cost_amount
        if note is not None:
            entry.note = note
        entry.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        logger.info(f"更新持仓: {fund_code}")
        return entry

    def remove(self, fund_code: str) -> bool:
        """删除一条持仓，返回是否成功"""
        if fund_code not in self._entries:
            logger.warning(f"持仓中不存在: {fund_code}")
            return False
        del self._entries[fund_code]
        self._save()
        logger.info(f"已删除持仓: {fund_code}")
        return True

    def get(self, fund_code: str) -> Optional[PortfolioEntry]:
        """查询单条持仓"""
        return self._entries.get(fund_code)

    def list_all(self) -> List[PortfolioEntry]:
        """返回全部持仓列表（按添加时间排序）"""
        return sorted(self._entries.values(), key=lambda e: e.added_at)

    def fund_codes(self) -> List[str]:
        """返回所有基金代码"""
        return list(self._entries.keys())

    def is_empty(self) -> bool:
        return len(self._entries) == 0

    # ─────────────────────────────── 展示 ────────────────────────────────

    def render_table(self) -> str:
        """
        生成 Markdown 表格，展示当前持仓列表
        """
        if self.is_empty():
            return "> 📭 当前持仓列表为空，请先使用「添加持仓」指令录入基金。"

        lines = [
            "| # | 基金代码 | 基金名称 | 持有份额 | 买入净值 | 买入金额 | 备注 | 添加时间 |",
            "|---|---------|---------|---------|---------|---------|------|---------|",
        ]
        for i, entry in enumerate(self.list_all(), 1):
            lines.append(
                "| {i} | `{code}` | {name} | {shares} | {nav} | {amount} | {note} | {at} |".format(
                    i=i,
                    code=entry.fund_code,
                    name=entry.fund_name or "—",
                    shares=f"{entry.shares:.2f}" if entry.shares else "—",
                    nav=f"{entry.cost_nav:.4f}" if entry.cost_nav else "—",
                    amount=f"{entry.cost_amount:.2f}元" if entry.cost_amount else "—",
                    note=entry.note or "—",
                    at=entry.added_at[:10],
                )
            )
        return "\n".join(lines)
