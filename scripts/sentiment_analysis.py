"""
舆情分析模块
基于东方财富基金公告做真实情绪分析
"""

import re
from typing import List, Optional

from .models import SentimentData, NewsItem
from .logger import logger


# ──────────────────────── 情绪关键词词典 ────────────────────────

# ① 忽略类：纯运营/基础设施公告，不参与情绪评分
#    （系统维护、节假日暂停、例行提示性公告、招募说明书更新等）
_IGNORE_PATTERNS = [
    # 基础设施/运营类
    r"系统[^\s]*维护",
    r"数据库[^\s]*升级",
    r"官网[^\s]*(升级|维护|更新)",
    r"(通道|渠道)[^\s]*(下线|暂停|关闭)",   # "云闪付通道下线"
    r"(设立|成立)[^\s]*(销售|子公司|分公司)",  # 公司架构调整
    # 节假日常规暂停
    r"(节假日|春节|国庆|端午|中秋|元旦|清明|劳动节)[^\s]*(暂停|休市|交易安排)",
    r"非港股通交易日暂停",
    # 例行披露文件（不含实质信号）
    r"提示性公告",
    r"(更新|修订).*(招募说明书|基金产品资料概要)",
    r"(招募说明书|基金产品资料概要).*(更新|修订)",
    # 定期报告（季报/年报/半年报）——例行披露，不含情绪信号
    r"第[一二三四1234]季度报告",
    r"(年度|半年度?|中期)报告",
    r"\d{4}年第[一二三四1234]季度",
]

# ② 正面信号：实质性利好
_POSITIVE_PATTERNS = [
    r"分红|派息",
    r"恢复[^\s]*(申购|赎回|交易)",
    r"开放[^\s]*(申购|赎回)",             # "开放大额申购限制"
    r"获[奖评]|荣获|年度优秀",
    r"规模[^\s]*扩[大容]",
    r"净[值]?[^\s]*增长",
    r"评级[^\s]*[上升提调]",
    r"增[持仓]",
    r"降[低减].*费[率用]",               # 降费是利好
]

# ③ 负面信号：实质性利空（排除节假日常规暂停）
_NEGATIVE_PATTERNS = [
    r"(暂停|限制)[^\s]*(大额申购|申购)",   # 限制/暂停申购（注意：节假日暂停已被 IGNORE 过滤）
    r"终止[^\s]*(合作|基金|运营)",
    r"清盘|清算|终止运作",
    r"(违规|处罚|监管|责令|警示)",
    r"基金经理[^\s]*离[任职]",
    r"(降级|降低)[^\s]*评级",
    r"亏损[^\s]*公告",
    r"规模[^\s]*缩[小减]",
]

# 公告类型映射
_CATEGORY_MAP = {
    "1": "定期报告",
    "2": "招募说明书",
    "3": "季度报告",
    "4": "临时公告",
    "5": "基金运营",
    "6": "其他公告",
}


def _classify_title(title: str) -> Optional[str]:
    """
    对公告标题做情绪分类
    Returns:
        None    → 忽略（不参与评分）
        '正面'  → 利好
        '负面'  → 利空
        '中性'  → 例行信息
    """
    # 先判断是否应该忽略
    for pattern in _IGNORE_PATTERNS:
        if re.search(pattern, title):
            return None   # 忽略

    # 负面优先（风险信号权重高）
    for pattern in _NEGATIVE_PATTERNS:
        if re.search(pattern, title):
            return "负面"

    for pattern in _POSITIVE_PATTERNS:
        if re.search(pattern, title):
            return "正面"

    return "中性"


def _extract_keywords_from_titles(titles: List[str]) -> List[str]:
    """从有效公告标题中提取信号关键词"""
    keyword_candidates = [
        "分红", "暂停大额申购", "恢复申购", "开放申购",
        "季度报告", "年度报告", "清盘", "基金经理变更",
        "费率调整", "终止合作", "获奖", "评级提升",
        "规模扩大", "降低费率",
    ]
    found = []
    combined = " ".join(titles)
    for kw in keyword_candidates:
        if kw in combined:
            found.append(kw)
    return found[:8]


class SentimentAnalyzer:
    """
    舆情分析器
    - 优先使用东方财富公告真实数据
    - 公告数量少时以中性兜底
    """

    def analyze(
        self,
        fund_code: str,
        fund_name: str,
        mock_news: bool = False,         # 默认已切换为真实数据
        data_fetcher=None,               # 传入 DanjuanDataFetcher 实例
    ) -> SentimentData:
        """
        执行舆情分析

        Args:
            fund_code:    基金代码
            fund_name:    基金名称（用于展示）
            mock_news:    True=使用模拟数据（调试用），False=调用真实API
            data_fetcher: DanjuanDataFetcher 实例，传入后直接复用已有连接

        Returns:
            SentimentData
        """
        try:
            if mock_news:
                news_items = self._generate_mock_news(fund_name)
            else:
                raw_list = self._fetch_news(fund_code, data_fetcher)
                news_items = self._raw_to_news_items(raw_list, fund_name)

            return self._analyze_sentiment(news_items, fund_name)

        except Exception as e:
            logger.error(f"舆情分析失败: {e}")
            return SentimentData(
                score=50.0,
                level="中性",
                news_count=0,
                news_items=[],
                keywords=[]
            )

    # ──────────────────────── 数据获取 ────────────────────────

    def _fetch_news(self, fund_code: str, data_fetcher=None) -> list:
        """
        调用 data_fetcher.fetch_news 获取真实公告列表
        若未传入 data_fetcher，则内部创建一次性实例（会有重复连接，不推荐）
        """
        if data_fetcher is not None:
            return data_fetcher.fetch_news(fund_code, page_size=15)

        # 兜底：自建临时 fetcher
        try:
            from .data_fetcher import DanjuanDataFetcher
            fetcher = DanjuanDataFetcher()
            return fetcher.fetch_news(fund_code, page_size=15)
        except Exception as e:
            logger.warning(f"兜底 fetcher 获取公告失败: {e}")
            return []

    def _raw_to_news_items(self, raw_list: list, fund_name: str) -> List[NewsItem]:
        """
        将公告 dict 列表转为 NewsItem 对象列表
        - 忽略类公告：sentiment='忽略'，展示但不参与评分
        - 定期报告类：sentiment='中性（例行）'，参与展示，评分权重降低
        """
        items = []
        for raw in raw_list:
            title = raw.get("title", "")
            if not title:
                continue
            date = raw.get("date", "")
            category_code = str(raw.get("category", ""))
            category = _CATEGORY_MAP.get(category_code, "公告")
            classified = _classify_title(title)

            if classified is None:
                sentiment = "忽略"  # 不参与评分也不展示
            else:
                sentiment = classified

            summary = f"[{category}] {date}" if date else f"[{category}]"
            items.append(NewsItem(
                title=title,
                summary=summary,
                sentiment=sentiment,
                date=date,
            ))
        return items

    # ──────────────────────── 情绪计算 ────────────────────────

    def _analyze_sentiment(
        self,
        news_items: List[NewsItem],
        fund_name: str = "",
    ) -> SentimentData:
        """
        对新闻列表计算综合情绪得分
        规则：
        - 忽略类（sentiment='忽略'）：不计入评分，不展示在报告前5条
        - 例行类（sentiment='中性（例行）'）：不计入评分，但保留展示
        - 有效公告（正面/负面/中性）：参与评分
        - 无有效公告时：得分 50（中性）
        """
        if not news_items:
            return SentimentData(
                score=50.0, level="中性",
                news_count=0, news_items=[], keywords=[]
            )

        # 有效公告：正面/负面/中性（已过滤掉"忽略"）
        effective = [i for i in news_items if i.sentiment != "忽略"]
        positive_items = [i for i in effective if i.sentiment == "正面"]
        negative_items = [i for i in effective if i.sentiment == "负面"]

        if not effective:
            # 全是忽略类公告 → 中性 55（无实质利空）
            score = 55.0
        else:
            total_eff = len(effective)
            pos_ratio = len(positive_items) / total_eff
            neg_ratio = len(negative_items) / total_eff
            score = 50.0 + (pos_ratio * 40) - (neg_ratio * 40)
            # 每条实质负面额外 -5，上限 -15
            score -= min(len(negative_items) * 5, 15)

        score = round(max(0.0, min(100.0, score)), 1)

        if score >= 80:
            level = "强烈正面"
        elif score >= 60:
            level = "正面"
        elif score >= 40:
            level = "中性"
        elif score >= 20:
            level = "负面"
        else:
            level = "强烈负面"

        # 展示优先级：负面 > 正面 > 中性，最多5条，忽略类不展示
        _priority = {"负面": 0, "正面": 1, "中性": 2}
        display_items = sorted(effective, key=lambda x: _priority.get(x.sentiment, 9))[:5]

        # 关键词从有效公告中提取
        effective_titles = [i.title for i in effective]
        keywords = _extract_keywords_from_titles(effective_titles)

        return SentimentData(
            score=score,
            level=level,
            news_count=len(news_items),     # 展示总公告数
            news_items=display_items,        # 只展示有信号的
            keywords=keywords,
        )

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
