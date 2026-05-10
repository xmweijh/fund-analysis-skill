"""
估值数据获取模块 V2
从蛋卷指数估值API获取指数估值数据
"""

import requests
from typing import Optional, Dict, List
from datetime import datetime

from .models import ValuationData
from .logger import logger


class ValuationDataFetcher:
    """估值数据获取器"""

    DANJUAN_INDEX_URL = "https://danjuanfunds.com/djapi/index_eva/dj"

    def __init__(self, timeout: int = 10):
        """
        初始化估值数据获取器

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        })
        self._cache = {}
        self._cache_expiry = {}

    def fetch_index_valuation(self, index_code: str) -> Optional[ValuationData]:
        """
        获取指数估值数据

        Args:
            index_code: 指数代码（如 000300）

        Returns:
            ValuationData 或 None
        """
        if not index_code:
            logger.warning("指数代码为空")
            return None

        cache_key = f"valuation_{index_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            logger.info(f"获取指数估值数据: {index_code}")
            response = self.session.get(self.DANJUAN_INDEX_URL, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data or 'data' not in data:
                logger.warning(f"API响应异常: {data}")
                return None

            items = data.get('data', {}).get('items', [])
            if not items:
                logger.warning(f"API返回空数据: {data}")
                return None

            # 查找匹配的指数
            matching_item = None
            for item in items:
                item_code = item.get('code', '') or item.get('index_code', '')
                if item_code == index_code:
                    matching_item = item
                    break

            if not matching_item:
                logger.warning(f"未找到指数代码: {index_code}")
                return None

            # 解析估值数据
            valuation_data = self._parse_valuation_item(matching_item)
            if valuation_data:
                self._set_cache(cache_key, valuation_data, 3600)  # 缓存1小时
            return valuation_data

        except requests.RequestException as e:
            logger.error(f"网络请求失败 {index_code}: {e}")
            return None
        except Exception as e:
            logger.error(f"获取指数估值数据失败 {index_code}: {e}")
            return None

    def _parse_valuation_item(self, item: Dict) -> Optional[ValuationData]:
        """
        解析单个指数的估值数据

        Args:
            item: API返回的单条指数数据

        Returns:
            ValuationData 或 None
        """
        try:
            pe_ttm = self._to_float(item.get('pe'))
            pb = self._to_float(item.get('pb'))

            # 百分位数据（API返回0-1，需要转换为0-100）
            pe_percentile = self._to_float(item.get('pe_percentile'))
            if pe_percentile is not None:
                pe_percentile = pe_percentile * 100

            pb_percentile = self._to_float(item.get('pb_percentile'))
            if pb_percentile is not None:
                pb_percentile = pb_percentile * 100

            # 计算风险溢价：(1/PE * 100) - 2.5
            risk_premium = None
            if pe_ttm is not None and pe_ttm > 0:
                try:
                    risk_premium = round((1 / pe_ttm * 100) - 2.5, 2)
                except Exception as e:
                    logger.debug(f"计算风险溢价失败: {e}")

            # 映射估值状态：eva_type 的值 low -> 低估, mid -> 合理, high -> 高估
            eva_type = item.get('eva_type', '').lower()
            status_map = {
                'low': '低估',
                'mid': '合理',
                'high': '高估'
            }
            status = status_map.get(eva_type, '未知')

            # 获取更新日期
            update_date = item.get('update_date') or item.get('date')
            if update_date:
                # 尝试转换为日期字符串
                if isinstance(update_date, int):
                    try:
                        update_date = datetime.fromtimestamp(update_date / 1000).strftime('%Y-%m-%d')
                    except:
                        update_date = str(update_date)[:10]
                else:
                    update_date = str(update_date)[:10]

            return ValuationData(
                pe_ttm=pe_ttm,
                pb=pb,
                pe_percentile=pe_percentile,
                pb_percentile=pb_percentile,
                risk_premium=risk_premium,
                status=status,
                update_date=update_date
            )

        except Exception as e:
            logger.error(f"解析估值数据失败: {e}")
            return None

    def _to_float(self, value) -> Optional[float]:
        """安全转换浮点数"""
        if value in (None, "", "--"):
            return None
        try:
            return float(str(value).replace('%', '').strip())
        except Exception:
            return None

    def _get_cache(self, key: str):
        """获取缓存"""
        import time
        if key not in self._cache:
            return None
        if key not in self._cache_expiry:
            return None
        if time.time() < self._cache_expiry[key]:
            return self._cache[key]
        return None

    def _set_cache(self, key: str, value, expiry_seconds: int):
        """设置缓存"""
        import time
        self._cache[key] = value
        self._cache_expiry[key] = time.time() + expiry_seconds

    def get_common_index_mapping(self) -> Dict[str, str]:
        """
        获取常见指数映射

        Returns:
            dict: {指数名称: 指数代码}
        """
        return {
            '沪深300': '000300',
            '中证500': '000905',
            '创业板指': '399006',
            '上证50': '000016',
            '科创50': '000688',
            '中证1000': '000852',
            '恒生指数': 'HSI',
            '纳斯达克100': 'NDX',
        }

    def fetch_multiple_indices(self, index_codes: List[str]) -> Dict[str, ValuationData]:
        """
        批量获取多个指数的估值数据

        Args:
            index_codes: 指数代码列表

        Returns:
            dict: {指数代码: ValuationData}
        """
        result = {}
        for code in index_codes:
            try:
                valuation = self.fetch_index_valuation(code)
                if valuation:
                    result[code] = valuation
            except Exception as e:
                logger.warning(f"获取 {code} 估值数据失败: {e}")
        return result
