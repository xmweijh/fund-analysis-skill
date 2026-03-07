"""
数据模型定义
使用Pydantic进行数据验证
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field, validator


class FundBasicInfo(BaseModel):
    """基金基础信息"""
    fund_code: str = Field(..., description="基金代码")
    fund_name: str = Field(..., description="基金名称")
    fund_type: Optional[str] = Field(None, description="基金类型")
    fund_scale: Optional[float] = Field(None, description="基金规模(亿元)")
    establish_date: Optional[str] = Field(None, description="成立日期")
    manager_name: Optional[str] = Field(None, description="基金经理姓名")
    company: Optional[str] = Field(None, description="基金公司")

    @validator('fund_code')
    def validate_fund_code(cls, v):
        """验证基金代码格式"""
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError("基金代码必须是6位数字")
        return v


class FundRealtimeQuote(BaseModel):
    """实时行情"""
    fund_code: str = Field(..., description="基金代码")
    nav: Optional[float] = Field(None, description="当前净值")
    change_pct: Optional[float] = Field(None, description="日涨跌幅(%)")
    day7_return: Optional[float] = Field(None, description="近7日年化收益率(%)")


class FundNavHistory(BaseModel):
    """净值历史"""
    fund_code: str = Field(..., description="基金代码")
    dates: List[str] = Field(default_factory=list, description="日期列表")
    navs: List[float] = Field(default_factory=list, description="净值列表")

    @validator('navs')
    def validate_navs(cls, v, values):
        """验证净值数据"""
        dates = values.get('dates', [])
        if len(v) != len(dates):
            raise ValueError("日期和净值数量不匹配")
        return v


class TechnicalIndicators(BaseModel):
    """技术指标"""
    ma5: Optional[float] = Field(None, description="5日均线")
    ma10: Optional[float] = Field(None, description="10日均线")
    ma20: Optional[float] = Field(None, description="20日均线")
    ma60: Optional[float] = Field(None, description="60日均线")
    trend: str = Field(default="未知", description="趋势: 上升/下降/震荡")
    formation: str = Field(default="无明确形态", description="形态: 多头排列/空头排列")
    signals: List[str] = Field(default_factory=list, description="技术信号列表")
    return_30d: Optional[float] = Field(None, description="30天收益率")
    return_60d: Optional[float] = Field(None, description="60天收益率")
    return_90d: Optional[float] = Field(None, description="90天收益率")


class HoldingStock(BaseModel):
    """持仓股票"""
    stock_name: str = Field(..., description="股票名称")
    stock_code: Optional[str] = Field(None, description="股票代码")
    holding_ratio: Optional[float] = Field(None, description="持仓比例(%)")
    holding_value: Optional[float] = Field(None, description="持仓市值(亿元)")


class HoldingAnalysis(BaseModel):
    """持仓分析"""
    top10_holdings: List[HoldingStock] = Field(default_factory=list, description="前十大重仓股")
    industry_concentration: Dict[str, float] = Field(default_factory=dict, description="行业集中度")
    holding_concentration: Optional[float] = Field(None, description="前10大持仓占比(%)")
    style: str = Field(default="未知", description="持仓风格: 价值型/成长型/平衡型")


class ManagerInfo(BaseModel):
    """基金经理信息"""
    manager_name: Optional[str] = Field(None, description="姓名")
    experience_years: Optional[int] = Field(None, description="从业年限")
    manage_years: Optional[float] = Field(None, description="管理该基金年限")
    fund_count: Optional[float] = Field(None, description="管理基金数量（API偶尔返回小数）")
    avg_return: Optional[float] = Field(None, description="平均收益率")
    max_drawdown: Optional[float] = Field(None, description="最大回撤")
    is_senior: bool = Field(default=False, description="是否资深")


class YearlyPerformance(BaseModel):
    """逐年业绩数据"""
    year: str = Field(..., description="年份或时段（如 '2024'、'成立以来'）")
    self_return: Optional[float] = Field(None, description="基金收益率(%)")
    benchmark_return: Optional[float] = Field(None, description="基准收益率(%)")
    max_drawdown: Optional[float] = Field(None, description="最大回撤(%)")
    rank: Optional[str] = Field(None, description="原始同类排名字符串，如 '697/4533'")
    rank_pct: Optional[float] = Field(None, description="同类排名百分位(越高越好, 0-100)")


class PerformanceData(BaseModel):
    """业绩数据"""
    return_1m: Optional[float] = Field(None, description="1月收益率")
    return_3m: Optional[float] = Field(None, description="3月收益率")
    return_6m: Optional[float] = Field(None, description="6月收益率")
    return_1y: Optional[float] = Field(None, description="1年收益率")
    return_3y: Optional[float] = Field(None, description="3年收益率")
    return_5y: Optional[float] = Field(None, description="5年收益率")
    annualized_return: Optional[float] = Field(None, description="年化收益率(成立以来)")
    max_drawdown: Optional[float] = Field(None, description="最大回撤(成立以来)")
    rank_percentile: Optional[float] = Field(None, description="同类排名百分位(成立以来)")
    excess_return: Optional[float] = Field(None, description="超额收益(近1年 vs 基准)")
    yearly_performance: List[YearlyPerformance] = Field(
        default_factory=list, description="逐年业绩列表（含同类排名）"
    )


class NewsItem(BaseModel):
    """新闻条目"""
    title: str = Field(..., description="标题")
    summary: Optional[str] = Field(None, description="摘要")
    sentiment: str = Field(default="中性", description="情绪: 正面/负面/中性")
    date: Optional[str] = Field(None, description="日期")


class SentimentData(BaseModel):
    """舆情数据"""
    score: float = Field(default=50.0, description="综合得分(0-100)")
    level: str = Field(default="中性", description="情绪等级: 强烈正面/正面/中性/负面/强烈负面")
    news_count: int = Field(default=0, description="新闻数量")
    news_items: List[NewsItem] = Field(default_factory=list, description="新闻列表")
    keywords: List[str] = Field(default_factory=list, description="关键词")

    @validator('score')
    def validate_score(cls, v):
        """验证得分范围"""
        if not 0 <= v <= 100:
            raise ValueError("舆情得分必须在0-100之间")
        return v


class InvestmentAdvice(BaseModel):
    """投资建议"""
    conclusion: str = Field(..., description="核心结论(一句话)")
    action: str = Field(..., description="操作建议: 买入/持有/卖出/观望")
    ideal_buy: Optional[str] = Field(None, description="理想买点区间")
    secondary_buy: Optional[str] = Field(None, description="次要买点区间")
    stop_loss: Optional[str] = Field(None, description="止损位")
    take_profit: Optional[str] = Field(None, description="止盈位")
    checklist: List[str] = Field(default_factory=list, description="操作检查清单")

    @validator('action')
    def validate_action(cls, v):
        """验证操作建议"""
        valid_actions = ["买入", "持有", "卖出", "观望"]
        if v not in valid_actions:
            raise ValueError(f"操作建议必须是: {', '.join(valid_actions)}")
        return v
