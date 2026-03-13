"""
数据获取模块
从蛋卷基金API获取基金数据
"""

import sys
import os
from typing import Optional, Dict, Any, List, Tuple
from abc import ABC, abstractmethod
import time
import json
import re
from datetime import datetime

import requests

# 尝试导入 pysnowball（支持 pip install 和本地源码两种方式）
# 如果从源码运行，可设置环境变量：
#   export PYSNOWBALL_PATH=/path/to/pysnowball-master
_pysnowball_extra = os.environ.get("PYSNOWBALL_PATH", "")
if _pysnowball_extra and _pysnowball_extra not in sys.path:
    sys.path.insert(0, _pysnowball_extra)

_PYSNOWBALL_INSTALL_HINT = (
    "未找到 pysnowball 库，请安装后重试：\n"
    "  pip install pysnowball\n"
    "或克隆源码后设置：export PYSNOWBALL_PATH=/path/to/pysnowball-master"
)

try:
    import pysnowball  # noqa: F401
    from pysnowball import fund as snowball_fund
    _pysnowball_available = True
except ImportError:
    snowball_fund = None  # type: ignore
    _pysnowball_available = False


def _require_pysnowball():
    """在实际调用 pysnowball API 前检查是否可用，不可用则抛出友好提示。"""
    if not _pysnowball_available:
        raise ImportError(_PYSNOWBALL_INSTALL_HINT)

from .models import (
    FundBasicInfo, FundRealtimeQuote, FundNavHistory,
    HoldingAnalysis, ManagerInfo, PerformanceData, YearlyPerformance,
    MarketIndexQuote
)
from .logger import logger


class DataFetcher(ABC):
    """数据获取器抽象基类"""

    @abstractmethod
    def fetch_basic_info(self, fund_code: str) -> FundBasicInfo:
        """获取基金基础信息"""
        pass

    @abstractmethod
    def fetch_realtime_quote(self, fund_code: str) -> FundRealtimeQuote:
        """获取实时行情"""
        pass

    @abstractmethod
    def fetch_nav_history(self, fund_code: str, days: int = 365) -> FundNavHistory:
        """获取净值历史"""
        pass

    @abstractmethod
    def fetch_holdings(self, fund_code: str) -> HoldingAnalysis:
        """获取持仓分析"""
        pass

    @abstractmethod
    def fetch_manager_info(self, fund_code: str) -> ManagerInfo:
        """获取基金经理信息"""
        pass

    @abstractmethod
    def fetch_performance(self, fund_code: str) -> PerformanceData:
        """获取业绩数据"""
        pass

    @abstractmethod
    def fetch_news(self, fund_code: str, page_size: int = 10) -> list:
        """获取基金公告/新闻列表，返回原始 dict 列表"""
        pass

    @abstractmethod
    def fetch_market_indices(self) -> Dict[str, MarketIndexQuote]:
        """获取大盘指数行情"""
        pass


class DanjuanDataFetcher(DataFetcher):
    """蛋卷基金数据获取器"""

    def __init__(self):
        self._cache = {}
        self._cache_expiry = {}
        self._realtime_cache_expiry = 60   # 实时数据缓存1分钟
        self._index_cache_expiry = 120     # 指数行情缓存2分钟
        self._history_cache_expiry = 86400  # 历史数据缓存24小时
        self._index_secids = ["1.000001", "0.399001", "0.399006", "1.000300", "1.000905"]
        self._default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://fundf10.eastmoney.com/",
        }

    def _is_cache_valid(self, key: str, expiry_seconds: int) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        if key not in self._cache_expiry:
            return False
        return time.time() < self._cache_expiry[key]

    def _get_cache(self, key: str):
        """获取缓存"""
        if self._is_cache_valid(key, self._history_cache_expiry):
            return self._cache[key]
        return None

    def _set_cache(self, key: str, value, expiry_seconds: int):
        """设置缓存"""
        self._cache[key] = value
        self._cache_expiry[key] = time.time() + expiry_seconds

    def fetch_basic_info(self, fund_code: str) -> FundBasicInfo:
        """获取基金基础信息（优先蛋卷，失败时降级为天天基金估值接口）"""
        cache_key = f"basic_info_{fund_code}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        logger.info(f"获取基金基础信息: {fund_code}")

        # 1) 优先使用蛋卷（字段更完整）
        if _pysnowball_available:
            try:
                data = snowball_fund.fund_info(fund_code)
                if data and 'data' in data:
                    fund_data = data['data']
                    basic_info = FundBasicInfo(
                        fund_code=fund_code,
                        fund_name=fund_data.get('fd_name', ''),
                        fund_type=fund_data.get('fd_full_name', ''),
                        fund_scale=self._parse_fund_scale(
                            fund_data.get('fd_total_assets', fund_data.get('totshare', 0))
                        ),
                        establish_date=self._parse_date(
                            fund_data.get('fd_establish_date', fund_data.get('found_date'))
                        ),
                        manager_name=fund_data.get('fd_manager_name', fund_data.get('manager_name', '')),
                        company=fund_data.get('fd_company_name', fund_data.get('keeper_name', ''))
                    )
                    self._set_cache(cache_key, basic_info, self._history_cache_expiry)
                    return basic_info
            except Exception as e:
                logger.warning(f"蛋卷基础信息获取失败，尝试降级接口: {e}")

        # 2) 降级：天天基金实时估值接口可拿到基金名称
        try:
            estimate_data = self._fetch_tiantian_estimate_raw(fund_code)
            fund_name = estimate_data.get("name") or f"基金{fund_code}"
            basic_info = FundBasicInfo(
                fund_code=fund_code,
                fund_name=fund_name,
                fund_type=None,
                fund_scale=None,
                establish_date=None,
                manager_name=None,
                company=None,
            )
            self._set_cache(cache_key, basic_info, self._history_cache_expiry)
            return basic_info
        except Exception as e:
            logger.error(f"获取基金基础信息失败 {fund_code}: {e}")
            raise

    def fetch_realtime_quote(self, fund_code: str) -> FundRealtimeQuote:
        """获取实时行情（优先天天基金实时估值，失败后回退蛋卷）"""
        cache_key = f"realtime_{fund_code}"
        if self._is_cache_valid(cache_key, self._realtime_cache_expiry):
            return self._cache[cache_key]

        # 1) 优先天天基金实时估值（交易日盘中刷新）
        try:
            estimate_data = self._fetch_tiantian_estimate_raw(fund_code)
            quote = self._build_quote_from_tiantian(fund_code, estimate_data)
            self._set_cache(cache_key, quote, self._realtime_cache_expiry)
            return quote
        except Exception as e:
            logger.warning(f"天天基金实时估值获取失败，尝试蛋卷回退: {e}")

        # 2) 回退到蛋卷净值接口
        if _pysnowball_available:
            try:
                quote = self._fetch_realtime_quote_from_snowball(fund_code)
                self._set_cache(cache_key, quote, self._realtime_cache_expiry)
                return quote
            except Exception as e:
                logger.error(f"获取实时行情失败 {fund_code}: {e}")
                raise

        raise ValueError(f"获取实时行情失败 {fund_code}: 天天基金/蛋卷接口均不可用")

    def fetch_nav_history(self, fund_code: str, days: int = 365) -> FundNavHistory:
        """获取净值历史（优先蛋卷，失败后回退东方财富历史净值）"""
        cache_key = f"nav_history_{fund_code}_{days}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # 1) 优先蛋卷
        nav_history = self._fetch_nav_history_from_snowball(fund_code, days)
        if nav_history and nav_history.navs:
            self._set_cache(cache_key, nav_history, self._history_cache_expiry)
            return nav_history

        # 2) 回退东方财富历史净值（JSONP）
        nav_history = self._fetch_nav_history_from_eastmoney(fund_code, days)
        if nav_history and nav_history.navs:
            self._set_cache(cache_key, nav_history, self._history_cache_expiry)
            return nav_history

        raise ValueError(f"获取净值历史失败 {fund_code}: 可用数据源均返回空")

    def _fetch_tiantian_estimate_raw(self, fund_code: str) -> Dict[str, Any]:
        """调用天天基金实时估值接口并返回原始 JSON。"""
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        resp = requests.get(url, headers=self._default_headers, timeout=8)
        resp.raise_for_status()
        return self._parse_jsonp_payload(resp.text)

    def _build_quote_from_tiantian(self, fund_code: str, payload: Dict[str, Any]) -> FundRealtimeQuote:
        """将天天基金估值响应转换为统一行情模型。"""
        prev_nav = self._to_float(payload.get("dwjz"))
        estimated_nav = self._to_float(payload.get("gsz"))
        estimated_change_pct = self._to_float(payload.get("gszzl"))

        nav = estimated_nav if estimated_nav is not None else prev_nav

        return FundRealtimeQuote(
            fund_code=fund_code,
            nav=nav,
            change_pct=estimated_change_pct,
            day7_return=None,
            previous_nav=prev_nav,
            previous_nav_date=payload.get("jzrq") or None,
            estimated_nav=estimated_nav,
            estimated_change_pct=estimated_change_pct,
            estimate_time=payload.get("gztime") or None,
            is_estimated=estimated_nav is not None,
            source="tiantian_estimate",
        )

    def _fetch_realtime_quote_from_snowball(self, fund_code: str) -> FundRealtimeQuote:
        """蛋卷回退实时行情（最新已披露净值）。"""
        _require_pysnowball()
        data = snowball_fund.fund_nav_history(fund_code, page=1, size=2)

        if not data or 'data' not in data:
            raise ValueError("获取实时行情失败")

        items = data['data'].get('items', data['data'].get('list', []))
        if not items:
            raise ValueError("净值数据为空")

        latest = items[0]
        nav_val = self._to_float(latest.get('nav', latest.get('net_value')))
        change_pct = self._to_float(latest.get('percentage'))

        return FundRealtimeQuote(
            fund_code=fund_code,
            nav=nav_val,
            change_pct=change_pct,
            day7_return=None,
            previous_nav=nav_val,
            previous_nav_date=(latest.get('date') or '')[:10] or None,
            estimated_nav=None,
            estimated_change_pct=None,
            estimate_time=None,
            is_estimated=False,
            source="danjuan_nav_history",
        )

    def _fetch_nav_history_from_snowball(self, fund_code: str, days: int) -> Optional[FundNavHistory]:
        """从蛋卷获取净值历史。"""
        if not _pysnowball_available:
            return None

        try:
            logger.info(f"获取净值历史(蛋卷): {fund_code}, 天数: {days}")
            points: List[Tuple[str, float]] = []
            page = 1
            size = 50
            max_pages = (days // size) + 4

            while len(points) < days and page <= max_pages:
                data = snowball_fund.fund_nav_history(fund_code, page=page, size=size)
                if not data or 'data' not in data:
                    break

                nav_list = data['data'].get('items', data['data'].get('list', []))
                if not nav_list:
                    break

                for item in nav_list:
                    date_str = (item.get('date') or '')[:10]
                    nav_value = self._to_float(item.get('nav', item.get('net_value')))
                    if date_str and nav_value is not None:
                        points.append((date_str, nav_value))

                page += 1
                time.sleep(0.08)

            normalized = self._normalize_nav_points(points, days)
            if not normalized:
                return None

            return FundNavHistory(
                fund_code=fund_code,
                dates=[d for d, _ in normalized],
                navs=[v for _, v in normalized],
            )
        except Exception as e:
            logger.warning(f"蛋卷净值历史获取失败 {fund_code}: {e}")
            return None

    def _fetch_nav_history_from_eastmoney(self, fund_code: str, days: int) -> Optional[FundNavHistory]:
        """从东方财富 f10/lsjz(JSONP) 获取历史净值。"""
        logger.info(f"获取净值历史(东方财富): {fund_code}, 天数: {days}")
        points: List[Tuple[str, float]] = []
        page_size = 40
        max_pages = (days // page_size) + 6

        for page in range(1, max_pages + 1):
            url = (
                "https://api.fund.eastmoney.com/f10/lsjz"
                f"?callback=cb&fundCode={fund_code}&pageIndex={page}"
                f"&pageSize={page_size}&startDate=&endDate="
            )
            try:
                resp = requests.get(url, headers=self._default_headers, timeout=8)
                resp.raise_for_status()
                payload = self._parse_jsonp_payload(resp.text)
                rows = payload.get("Data", {}).get("LSJZList") or []
                if not rows:
                    break

                for row in rows:
                    date_str = (row.get("FSRQ") or "")[:10]
                    nav_value = self._to_float(row.get("DWJZ"))
                    if date_str and nav_value is not None:
                        points.append((date_str, nav_value))

                if len(points) >= days:
                    break

                time.sleep(0.08)
            except Exception as e:
                logger.warning(f"东方财富净值历史第{page}页失败 {fund_code}: {e}")
                break

        normalized = self._normalize_nav_points(points, days)
        if not normalized:
            return None

        return FundNavHistory(
            fund_code=fund_code,
            dates=[d for d, _ in normalized],
            navs=[v for _, v in normalized],
        )

    def _normalize_nav_points(self, points: List[Tuple[str, float]], days: int) -> List[Tuple[str, float]]:
        """按日期排序、去重并截取最近 N 天。"""
        if not points:
            return []

        dedup: Dict[str, float] = {}
        for date_str, nav in points:
            if date_str and nav is not None:
                dedup[date_str] = nav

        normalized = sorted(dedup.items(), key=lambda x: x[0])
        if days > 0 and len(normalized) > days:
            normalized = normalized[-days:]
        return normalized

    def _parse_jsonp_payload(self, raw_text: str) -> Dict[str, Any]:
        """解析 JSONP 响应文本。"""
        if not raw_text:
            raise ValueError("空响应")

        text = raw_text.strip()
        match = re.search(r"\{.*\}", text)
        if not match:
            raise ValueError(f"无法解析JSONP: {text[:80]}")

        return json.loads(match.group(0))

    def _to_float(self, value: Any) -> Optional[float]:
        """安全转换浮点数。"""
        if value in (None, "", "--"):
            return None
        try:
            return float(str(value).replace('%', '').strip())
        except Exception:
            return None

    def fetch_holdings(self, fund_code: str) -> HoldingAnalysis:
        """获取持仓分析"""
        _require_pysnowball()
        cache_key = f"holdings_{fund_code}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"获取持仓数据: {fund_code}")
            data = snowball_fund.fund_asset(fund_code)

            if not data or 'data' not in data:
                raise ValueError("获取持仓数据失败")

            holdings_data = data['data']

            # 解析前十大重仓股（字段名：stock_list, name, code, percent, industry_label）
            top10_holdings = []
            stock_list = holdings_data.get('stock_list', holdings_data.get('list', []))

            for stock in stock_list[:10]:
                stock_name = stock.get('name', stock.get('stock_name', ''))
                stock_code = stock.get('code', stock.get('stock_code', ''))
                holding_ratio = stock.get('percent', stock.get('holding_ratio', 0))
                industry = stock.get('industry_label', '')

                if stock_name:
                    top10_holdings.append({
                        'stock_name': stock_name,
                        'stock_code': stock_code,
                        'holding_ratio': holding_ratio,
                        'industry': industry
                    })

            # 计算持仓集中度
            holding_concentration = sum(
                h.get('holding_ratio', 0) for h in top10_holdings
            )

            # 行业集中度（从industry_label统计）
            industry_map = {}
            for stock in top10_holdings:
                ind = stock.get('industry', '其他') or '其他'
                industry_map[ind] = industry_map.get(ind, 0) + stock.get('holding_ratio', 0)
            industry_concentration = industry_map if industry_map else {"其他": 0}

            # 判断持仓风格（根据股票市场分布）
            stock_percent = holdings_data.get('stock_percent', 0)
            bond_percent = holdings_data.get('bond_percent', 0)
            if stock_percent > 60:
                style = "成长型" if any(s.get('amarket', True) for s in stock_list[:5]) else "价值型"
            elif bond_percent > 40:
                style = "债券型"
            else:
                style = "平衡型"

            holdings_analysis = HoldingAnalysis(
                top10_holdings=top10_holdings,
                industry_concentration=industry_concentration,
                holding_concentration=holding_concentration,
                style=style
            )

            self._set_cache(cache_key, holdings_analysis, self._history_cache_expiry)
            return holdings_analysis

        except Exception as e:
            logger.error(f"获取持仓数据失败 {fund_code}: {e}")
            raise

    def fetch_manager_info(self, fund_code: str) -> ManagerInfo:
        """获取基金经理信息"""
        _require_pysnowball()
        cache_key = f"manager_{fund_code}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"获取基金经理信息: {fund_code}")
            data = snowball_fund.fund_manager(fund_code)

            if not data or 'data' not in data:
                raise ValueError("获取基金经理信息失败")

            manager_data = data['data']
            manager_list = manager_data.get('items', manager_data.get('list', []))

            if not manager_list:
                raise ValueError("无基金经理信息")

            # 取第一个基金经理
            current_manager = manager_list[0]

            # 解析从业年限（work_year字段）
            work_year_raw = current_manager.get('work_year', current_manager.get('experience_years', 0))
            try:
                experience_years = int(str(work_year_raw).replace('年', '').strip()) if work_year_raw else 0
            except:
                experience_years = 0

            # 解析管理该基金时间（cp_term字段，如 "3年87天"）
            cp_term = current_manager.get('cp_term', '')
            try:
                if '年' in str(cp_term):
                    manage_years = float(str(cp_term).split('年')[0])
                else:
                    manage_years = 0.0
            except:
                manage_years = 0.0

            # 解析该基金任职总收益（cp_rate字段）
            cp_rate = current_manager.get('cp_rate', 0)
            try:
                avg_return = float(cp_rate) if cp_rate else 0.0
            except:
                avg_return = 0.0

            manager_info = ManagerInfo(
                manager_name=current_manager.get('name', ''),
                experience_years=experience_years,
                manage_years=manage_years,
                fund_count=current_manager.get('fund_total_nav', len(manager_list)),
                avg_return=avg_return,
                max_drawdown=0.0,
                is_senior=experience_years > 3
            )

            self._set_cache(cache_key, manager_info, self._history_cache_expiry)
            return manager_info

        except Exception as e:
            logger.error(f"获取基金经理信息失败 {fund_code}: {e}")
            raise

    def fetch_performance(self, fund_code: str) -> PerformanceData:
        """获取业绩数据（同时调用 fund_info + fund_achievement）"""
        _require_pysnowball()
        cache_key = f"performance_{fund_code}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"获取业绩数据: {fund_code}")

            # ── 1. fund_achievement：逐年数据 + 成立以来/今年以来 ──────────────
            ach_data = snowball_fund.fund_achievement(fund_code)
            if not ach_data or 'data' not in ach_data:
                raise ValueError("获取业绩数据失败")

            ach_list = ach_data['data'].get('annual_performance_list', [])

            def _parse_float(v):
                try:
                    return float(v) if v is not None else None
                except:
                    return None

            def _parse_pct_str(s):
                """将 '11.85%' 解析为 11.85"""
                try:
                    return float(str(s).replace('%', '').strip()) if s else None
                except:
                    return None

            def _parse_rank_pct(rank_str):
                """'697/4533' → 84.6%（超过多少人）"""
                if rank_str and '/' in str(rank_str):
                    try:
                        parts = str(rank_str).split('/')
                        return round((1 - int(parts[0]) / int(parts[1])) * 100, 1)
                    except:
                        pass
                return None

            # 构建 period_map（成立以来、今年以来）
            period_map = {}
            for item in ach_list:
                pt = item.get('period_time', '')
                period_map[pt] = {
                    'return': _parse_float(item.get('self_nav')),
                    'bench':  _parse_float(item.get('standard_index_nav')),
                    'mdd':    _parse_pct_str(item.get('self_max_draw_down')),
                    'rank':   item.get('self_nav_rank', ''),
                    'rank_pct': _parse_rank_pct(item.get('self_nav_rank')),
                }

            # 逐年数据（period_time 为4位数字年份的条目）
            yearly_perf = []
            for item in ach_list:
                pt = item.get('period_time', '')
                # 年份条目：纯数字4位（如 "2024"），以及 "今年以来"、"成立以来"
                is_year = pt.isdigit() and len(pt) == 4
                is_special = pt in ('今年以来', '成立以来')
                if is_year or is_special:
                    yearly_perf.append(YearlyPerformance(
                        year=pt,
                        self_return=_parse_float(item.get('self_nav')),
                        benchmark_return=_parse_float(item.get('standard_index_nav')),
                        max_drawdown=_parse_pct_str(item.get('self_max_draw_down')),
                        rank=item.get('self_nav_rank', '') or None,
                        rank_pct=_parse_rank_pct(item.get('self_nav_rank')),
                    ))

            p_all = period_map.get('成立以来', {})
            max_drawdown = p_all.get('mdd')
            rank_percentile = p_all.get('rank_pct')

            # ── 2. fund_info.fund_derived：近1/3/6月、近1/2/3年收益率 ──────────
            return_1m = return_3m = return_6m = return_1y = return_3y = return_5y = None
            return_ytd = None
            excess_return = None
            try:
                info_data = snowball_fund.fund_info(fund_code)
                fd = info_data.get('data', {}).get('fund_derived', {}) if info_data else {}

                def _fd_float(key):
                    v = fd.get(key)
                    return _parse_float(v) if v not in (None, '') else None

                return_1m   = _fd_float('nav_grl1m')
                return_3m   = _fd_float('nav_grl3m')
                return_6m   = _fd_float('nav_grl6m')
                return_ytd  = _fd_float('nav_grlty')   # 今年以来
                return_1y   = _fd_float('nav_grl1y')
                return_3y   = _fd_float('nav_grl3y')
                return_5y   = _fd_float('nav_grl5y')   # 近5年
                # 近1年超额收益 = 基金近1年 - 基准近1年
                bench_1y = _fd_float('srank_l1y')      # srank是排名字符串，需另取
                # 超额收益从 ach_list 取
                for item in ach_list:
                    if item.get('period_time') == '今年以来':
                        s = _parse_float(item.get('self_nav'))
                        b = _parse_float(item.get('standard_index_nav'))
                        if s is not None and b is not None:
                            excess_return = round(s - b, 4)
                        break
            except Exception as e2:
                logger.warning(f"获取fund_derived失败，部分收益率不可用: {e2}")

            performance = PerformanceData(
                return_1m=return_1m,
                return_3m=return_3m,
                return_6m=return_6m,
                return_1y=return_1y,
                return_3y=return_3y,
                return_5y=return_5y,
                annualized_return=p_all.get('return'),
                max_drawdown=max_drawdown,
                rank_percentile=rank_percentile,
                excess_return=excess_return,
                yearly_performance=yearly_perf,
            )

            self._set_cache(cache_key, performance, self._history_cache_expiry)
            return performance

        except Exception as e:
            logger.error(f"获取业绩数据失败 {fund_code}: {e}")
            raise

    def fetch_news(self, fund_code: str, page_size: int = 10) -> list:
        """
        获取基金公告列表（东方财富 f10/jjgg 接口）

        公告类型（NEWCATEGORY）:
          1=定期报告  2=招募说明书  3=季度报告  4=临时公告
          5=基金运营  6=其他公告

        Returns:
            list of dict: [{title, date, category, id}, ...]
        """
        cache_key = f"news_{fund_code}_{page_size}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            logger.info(f"获取基金公告: {fund_code}")
            url = (
                f"https://api.fund.eastmoney.com/f10/jjgg"
                f"?fundCode={fund_code}&pageIndex=1&pageSize={page_size}&type=0"
            )
            resp = requests.get(url, headers=self._default_headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            if data.get("ErrCode") != 0:
                raise ValueError(f"API错误: {data.get('ErrMsg')}")

            raw_list = data.get("Data") or []
            result = []
            for item in raw_list:
                result.append({
                    "title": item.get("TITLE", ""),
                    "date": (item.get("PUBLISHDATEDesc") or
                             (item.get("PUBLISHDATE") or "")[:10]),
                    "category": item.get("NEWCATEGORY", ""),
                    "id": item.get("ID", ""),
                })

            # 新闻缓存 1 小时
            self._set_cache(cache_key, result, 3600)
            logger.info(f"获取到 {len(result)} 条公告")
            return result

        except Exception as e:
            logger.warning(f"获取基金公告失败 {fund_code}: {e}")
            return []

    def fetch_market_indices(self) -> Dict[str, MarketIndexQuote]:
        """获取上证/深证/创业板/沪深300/中证500等大盘指数行情。"""
        cache_key = "market_indices_default"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        secids = ",".join(self._index_secids)
        url = (
            "https://push2.eastmoney.com/api/qt/ulist.np/get"
            "?fltt=2&invt=2&fields=f2,f3,f4,f12,f14"
            f"&secids={secids}"
        )

        try:
            resp = requests.get(url, headers=self._default_headers, timeout=8)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data", {}).get("diff") or []

            result: Dict[str, MarketIndexQuote] = {}
            for row in rows:
                index_name = row.get("f14") or str(row.get("f12") or "")
                index_code = str(row.get("f12") or "")
                result[index_name] = MarketIndexQuote(
                    index_code=index_code,
                    index_name=index_name,
                    latest_price=self._to_float(row.get("f2")),
                    change_pct=self._to_float(row.get("f3")),
                    change_amount=self._to_float(row.get("f4")),
                )

            self._set_cache(cache_key, result, self._index_cache_expiry)
            logger.info(f"获取到 {len(result)} 条大盘指数行情")
            return result

        except Exception as e:
            logger.warning(f"获取大盘指数行情失败: {e}")
            return {}

    def fetch_stock_quotes(self, stock_codes: list) -> Dict[str, Dict]:
        """
        批量查询股票最新行情（东方财富 push2his 日K接口，并发请求）
        支持 A 股（沪/深）和港股。

        Args:
            stock_codes: 股票代码列表，如 ['002602', '600901', '00005']

        Returns:
            dict: {stock_code: {'name': ..., 'price': ..., 'change_pct': ...}}
        """
        if not stock_codes:
            return {}

        cache_key = f"stock_quotes_{'_'.join(sorted(stock_codes))}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        from concurrent.futures import ThreadPoolExecutor, as_completed
        from datetime import date

        def _to_secid(code: str) -> str:
            code = code.strip()
            # 港股：数字 <= 5位且 < 10000
            if len(code) <= 5 and code.isdigit() and int(code) < 10000:
                return f"116.{code.zfill(5)}"
            if code.startswith('6'):
                return f"1.{code}"
            return f"0.{code}"

        def _fetch_one(code: str) -> Optional[Dict]:
            """获取单只股票最近两日K线，计算涨跌幅"""
            secid = _to_secid(code)
            today = date.today().strftime("%Y%m%d")
            url = (
                "https://push2his.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55"
                f"&klt=101&fqt=1&beg=20250101&end={today}&lmt=2"
            )
            try:
                headers = {"Referer": "https://finance.eastmoney.com/",
                           "User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=6)
                r.raise_for_status()
                data = r.json().get("data") or {}
                name = data.get("name", "")
                klines = data.get("klines") or []
                if not klines:
                    return None
                # 最新一条：date,open,close,high,low
                last = klines[-1].split(",")
                close = float(last[2]) if len(last) > 2 else None
                if len(klines) >= 2:
                    prev = klines[-2].split(",")
                    prev_close = float(prev[2]) if len(prev) > 2 else None
                else:
                    prev_close = None
                change_pct = None
                if close is not None and prev_close and prev_close != 0:
                    change_pct = round((close - prev_close) / prev_close * 100, 2)
                return {"name": name, "price": close, "change_pct": change_pct}
            except Exception as e:
                logger.debug(f"获取 {code} 行情失败: {e}")
                return None

        result: Dict[str, Dict] = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            fut_map = {pool.submit(_fetch_one, c): c for c in stock_codes}
            for fut in as_completed(fut_map):
                code = fut_map[fut]
                try:
                    q = fut.result()
                    if q:
                        result[code] = q
                except Exception:
                    pass

        self._set_cache(cache_key, result, 300)
        logger.info(f"获取到 {len(result)} 条股票行情（push2his）")
        return result

    def _parse_fund_scale(self, value: Any) -> Optional[float]:
        """解析基金规模"""
        if value is None:
            return None
        try:
            str_val = str(value).strip()
            # 处理 "18.44亿" 格式
            if '亿' in str_val:
                return float(str_val.replace('亿', '').strip())
            # 处理 "1844000000" 格式（元转亿）
            scale = float(str_val)
            if scale > 100000000:
                scale = scale / 100000000
            return scale
        except:
            return None

    def _parse_date(self, date_str: Any) -> Optional[str]:
        """解析日期"""
        if not date_str:
            return None
        try:
            # 尝试解析各种日期格式
            if isinstance(date_str, str):
                # 处理时间戳
                if date_str.isdigit():
                    date_obj = datetime.fromtimestamp(int(date_str) / 1000)
                    return date_obj.strftime('%Y-%m-%d')
                # 处理标准日期格式
                return date_str[:10]
            return None
        except:
            return None

    def _parse_return(self, data: Dict, key: str, default_days: int = 0) -> Optional[float]:
        """解析收益率"""
        if not data:
            return None
        return data.get(key, None)
