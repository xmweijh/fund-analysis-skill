"""
用户持仓管理模块
支持用户持仓列表的增删改查，数据持久化存储到 JSON 文件
"""

import json
import os
import math
import re
import hashlib
import tempfile
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
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
        shares: Optional[float] = None,           # 持有份额
        cost_nav: Optional[float] = None,         # 买入净值(成本价)
        cost_amount: Optional[float] = None,      # 买入金额
        note: Optional[str] = None,               # 备注
        current_nav: Optional[float] = None,      # 当前净值(分析时更新)
        current_profit: Optional[float] = None,   # 浮动盈亏(分析时更新)
        current_return_rate: Optional[float] = None,  # 收益率%(分析时更新)
        added_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.fund_code = fund_code
        self.fund_name = fund_name
        self.shares = shares
        self.cost_nav = cost_nav
        self.cost_amount = cost_amount
        self.note = note
        self.current_nav = current_nav
        self.current_profit = current_profit
        self.current_return_rate = current_return_rate
        self.added_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if added_at is None else added_at
        self.updated_at = self.added_at if updated_at is None else updated_at
        self.validate()

    def validate(self):
        if not isinstance(self.fund_code,str) or not re.fullmatch(r'[0-9]{6}',self.fund_code):
            raise ValueError('基金代码须为六位ASCII数字')
        for key in ('shares','cost_nav','cost_amount','current_nav','current_profit','current_return_rate'):
            value=getattr(self,key)
            if value is None:continue
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError(f'{key}须为有限数值或未知')
            if key in ('shares','cost_nav','cost_amount','current_nav') and value<0:
                raise ValueError(f'{key}不能为负数')
            if key in ('cost_nav','current_nav') and value==0:raise ValueError(f'{key}须为正数或未知，不能用0替代未知净值')
        for key in ('fund_name','note','added_at','updated_at'):
            if getattr(self,key) is not None and not isinstance(getattr(self,key),str):raise ValueError(f'{key}须为文本')

    def to_dict(self) -> Dict[str, Any]:
        return {
            **deepcopy(getattr(self,'_extra_fields',{})),
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "shares": self.shares,
            "cost_nav": self.cost_nav,
            "cost_amount": self.cost_amount,
            "note": self.note,
            "current_nav": self.current_nav,
            "current_profit": self.current_profit,
            "current_return_rate": self.current_return_rate,
            "added_at": self.added_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioEntry":
        entry = cls(
            fund_code=d["fund_code"],
            fund_name=d.get("fund_name"),
            shares=d.get("shares"),
            cost_nav=d.get("cost_nav"),
            cost_amount=d.get("cost_amount"),
            note=d.get("note"),
            current_nav=d.get("current_nav"),
            current_profit=d.get("current_profit"),
            current_return_rate=d.get("current_return_rate"),
            added_at=d.get("added_at"),
            updated_at=d.get("updated_at"),
        )
        entry._extra_fields={k:deepcopy(v) for k,v in d.items() if k not in entry.to_dict()}
        return entry


class PortfolioManager:
    """
    用户持仓管理器
    负责持仓列表的增删改查和 JSON 持久化
    """

    def __init__(self, portfolio_path: Optional[str] = None):
        self._path = os.path.abspath(portfolio_path or _DEFAULT_PORTFOLIO_PATH)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._entries: Dict[str, PortfolioEntry] = {}
        self._revision = None
        self._load()

    # ─────────────────────────────── 持久化 ───────────────────────────────

    def _load(self):
        """从 JSON 文件加载持仓"""
        if not os.path.exists(self._path):
            logger.info("持仓文件不存在，将创建新文件")
            return
        try:
            original=Path(self._path).read_bytes()
            raw=json.loads(original.decode('utf-8-sig'))
            if not isinstance(raw,list) or any(not isinstance(item,dict) for item in raw):raise ValueError('持仓须为对象列表')
            entries=[PortfolioEntry.from_dict(item) for item in raw]
            if len({e.fund_code for e in entries})!=len(entries):raise ValueError('持仓代码重复，不能静默覆盖')
            self._entries={e.fund_code:e for e in entries}
            self._revision=hashlib.sha256(original).hexdigest()
            logger.info(f"已加载 {len(self._entries)} 条持仓记录")
        except Exception as e:
            raise ValueError('持仓文件读取失败，已保留原文件；先核对或从备份恢复') from e

    def _save(self, entries):
        """锁定写入、核对读取版本、保留旧文件备份，成功后再更新内存。"""
        for entry in entries.values():entry.validate()
        content=(json.dumps([e.to_dict() for e in entries.values()],ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
        path=Path(self._path);lock=Path(self._path+'.lock');temporary=None
        # 排他创建失败直接报错，不删除其他进程的锁。
        with lock.open('x',encoding='utf-8'):pass
        try:
            previous=path.read_bytes() if path.exists() else None
            revision=hashlib.sha256(previous).hexdigest() if previous is not None else None
            if revision!=self._revision:raise RuntimeError('持仓文件已被其他操作修改，请重新加载后再更新')
            if previous is not None:
                backups=Path(self._path+'.backups');backups.mkdir(exist_ok=True)
                (backups/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex+'.json')).write_bytes(previous)
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as handle:
                temporary=Path(handle.name);handle.write(content);handle.flush();os.fsync(handle.fileno())
            os.replace(temporary,path)
            self._entries=entries;self._revision=hashlib.sha256(content).hexdigest()
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
            lock.unlink()

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
        if not isinstance(fund_code,str) or not re.fullmatch(r'[0-9]{6}',fund_code):raise ValueError('基金代码须为六位ASCII数字')
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
        entries=deepcopy(self._entries);entries[fund_code]=entry
        self._save(entries)
        logger.info(f"新增持仓: {fund_code} {fund_name or ''}")
        return deepcopy(entry)

    def update(
        self,
        fund_code: str,
        fund_name: Optional[str] = None,
        shares: Optional[float] = None,
        cost_nav: Optional[float] = None,
        cost_amount: Optional[float] = None,
        note: Optional[str] = None,
        current_nav: Optional[float] = None,
        current_profit: Optional[float] = None,
        current_return_rate: Optional[float] = None,
        clear_fields: Optional[List[str]] = None,
    ) -> PortfolioEntry:
        """
        更新已有持仓（只更新非 None 的字段）。
        若不存在则先添加。
        """
        if not isinstance(fund_code,str) or not re.fullmatch(r'[0-9]{6}',fund_code):raise ValueError('基金代码须为六位ASCII数字')
        entry = deepcopy(self._entries[fund_code]) if fund_code in self._entries else PortfolioEntry(fund_code)
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
        if current_nav is not None:
            entry.current_nav = current_nav
        if current_profit is not None:
            entry.current_profit = current_profit
        if current_return_rate is not None:
            entry.current_return_rate = current_return_rate
        if clear_fields is not None:
            allowed={'fund_name','shares','cost_nav','cost_amount','note','current_nav','current_profit','current_return_rate'}
            if not isinstance(clear_fields,list) or any(not isinstance(key,str) or key not in allowed for key in clear_fields):
                raise ValueError('clear_fields须列出可清空的持仓字段，不能清空代码或审计时间')
            for key in clear_fields:setattr(entry,key,None)
        entry.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entries=deepcopy(self._entries);entries[fund_code]=entry
        self._save(entries)
        logger.info(f"更新持仓: {fund_code}")
        return deepcopy(entry)

    def remove(self, fund_code: str) -> bool:
        """删除一条持仓，返回是否成功"""
        if fund_code not in self._entries:
            logger.warning(f"持仓中不存在: {fund_code}")
            return False
        entries=deepcopy(self._entries);del entries[fund_code]
        self._save(entries)
        logger.info(f"已删除持仓: {fund_code}")
        return True

    def get(self, fund_code: str) -> Optional[PortfolioEntry]:
        """查询单条持仓"""
        return deepcopy(self._entries.get(fund_code))

    def list_all(self) -> List[PortfolioEntry]:
        """返回全部持仓列表（按添加时间排序）"""
        return deepcopy(sorted(self._entries.values(), key=lambda e: e.added_at))

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
            "| # | 基金代码 | 基金名称 | 持有份额 | 买入净值 | 买入金额 | 当前净值 | 浮动盈亏 | 收益率 | 备注 | 添加时间 |",
            "|---|---------|---------|---------|---------|---------|---------|---------|------|------|---------|",
        ]
        for i, entry in enumerate(self.list_all(), 1):
            current_nav_str = f"{entry.current_nav:.4f}" if entry.current_nav is not None else "—"
            profit_str = f"{entry.current_profit:+.2f}元" if entry.current_profit is not None else "—"
            return_str = f"{entry.current_return_rate:+.2f}%" if entry.current_return_rate is not None else "—"
            lines.append(
                "| {i} | `{code}` | {name} | {shares} | {nav} | {amount} | {cur_nav} | {profit} | {ret} | {note} | {at} |".format(
                    i=i,
                    code=entry.fund_code,
                    name=entry.fund_name or "—",
                    shares=f"{entry.shares:.2f}" if entry.shares is not None else "—",
                    nav=f"{entry.cost_nav:.4f}" if entry.cost_nav is not None else "—",
                    amount=f"{entry.cost_amount:.2f}元" if entry.cost_amount is not None else "—",
                    cur_nav=current_nav_str,
                    profit=profit_str,
                    ret=return_str,
                    note=entry.note or "—",
                    at=entry.added_at[:10],
                )
            )
        return "\n".join(lines)
