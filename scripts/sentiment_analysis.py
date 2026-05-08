"""
舆情分析模块 - 简化版
仅展示基金公告列表，不做情绪评分
"""

import re
from typing import List, Optional

from .models import SentimentData, NewsItem
from .logger import logger


# 公告类型映射
_CATEGORY_MAP = {
    "1": "定期报告",
    "2": "招募说明书",
    "3": "季度报告",
    "4": "临时公告",
    "5": "基金运营",
    "6": "其他公告",
}


# 仅用于标记重要公告，不做评分
_IMPORTANT_PATTERNS = [
    (r"分红|派息", "分红"),
    (r"(暂停|限制)[^\s]*(大额申购|申购)", "限购"),
    (r"恢复[^\s]*(申购|赎回|交易)", "恢复申赎"),
    (r"基金经理[^\s]*离[任职]|变更基金经理", "经理变更"),
    (r"清盘|清算|终止运作", "清盘风险"),
    (r"降[低减].*费[率用]", "降费"),
]


def _classify_importance(title: str) -> Optional[str]:
    """
    标记重要公告类型，仅用于展示，不参与评分
    Returns:
        标签字符串或 None
    """
    for pattern, label in _IMPORTANT_PATTERNS:
        if re.search(pattern, title):
            return label
    return None


class SentimentAnalyzer:
    """
    舆情分析器 - 简化版
    仅展示公告列表，不做情绪评分
    """

    def analyze(
        self,
        fund_code: str,
        fund_name: str,
        mock_news: bool = False,
        data_fetcher=None,
    ) -> SentimentData:
        """
        获取基金公告列表

        Args:
            fund_code:    基金代码
            fund_name:    基金名称
            mock_news:    True=使用模拟数据，False=调用真实API
            data_fetcher: DanjuanDataFetcher 实例

        Returns:
            SentimentData（score固定为50，level固定为中性）
        """
        try:
            if mock_news:
                news_items = self._generate_mock_news(fund_name)
            else:
                raw_list = self._fetch_news(fund_code, data_fetcher)
                news_items = self._raw_to_news_items(raw_list, fund_name)

            # 简化：仅返回公告列表，不做评分
            return SentimentData(
                score=50.0,  # 固定中性值，不用于投资建议
                level="中性",  # 固定值
                news_count=len(news_items),
                news_items=news_items[:5],  # 仅展示前5条
                keywords=[]  # 不再提取关键词
            )

        except Exception as e:
            logger.error(f"公告获取失败: {e}")
            return SentimentData(
                score=50.0,
                level="中性",
                news_count=0,
                news_items=[],
                keywords=[]
            )

    def _fetch_news(self, fund_code: str, data_fetcher=None) -> list:
        """获取公告列表"""
        if data_fetcher is not None:
            return data_fetcher.fetch_news(fund_code, page_size=10)  # 减少到10条

        try:
            from .data_fetcher import DanjuanDataFetcher
            fetcher = DanjuanDataFetcher()
            return fetcher.fetch_news(fund_code, page_size=10)
        except Exception as e:
            logger.warning(f"获取公告失败: {e}")
            return []

    def _raw_to_news_items(self, raw_list: list, fund_name: str) -> List[NewsItem]:
        """
        将公告转为 NewsItem，仅标记重要类型，不做情绪分类
        """
        items = []
        for raw in raw_list:
            title = raw.get("title", "")
            if not title:
                continue
            date = raw.get("date", "")
            category_code = str(raw.get("category", ""))
            category = _CATEGORY_MAP.get(category_code, "公告")

            # 仅标记重要公告类型，不做情绪判断
            importance = _classify_importance(title)
            sentiment = importance if importance else "常规"

            summary = f"[{category}] {date}" if date else f"[{category}]"
            items.append(NewsItem(
                title=title,
                summary=summary,
                sentiment=sentiment,
                date=date,
            ))
        return items

    # ──────────────────────── 调试用模拟数据 ────────────────────────

    def _generate_mock_news(self, fund_name: str) -> List[NewsItem]:
        """生成模拟新闻（仅调试使用）"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        mock_data = [
            {"title": f"{fund_name}2024年第4季度报告",    "sentiment": "中性",  "summary": "[季度报告] " + today},
            {"title": f"{fund_name}开放大额申购限制解除",  "sentiment": "正面",  "summary": "[基金运营] " + today},
            {"title": f"市场震荡，{fund_name}净值小幅回调", "sentiment": "中性",  "summary": "[临时公告] " + today},
            {"title": f"{fund_name}获年度优秀基金奖",      "sentiment": "正面",  "summary": "[其他公告] " + today},
            {"title": f"{fund_name}暂停大额申购公告",       "sentiment": "负面",  "summary": "[基金运营] " + today},
        ]
        return [NewsItem(title=d["title"], summary=d["summary"],
                         sentiment=d["sentiment"], date=today)
                for d in mock_data]
