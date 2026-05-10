"""
数据模型定义
使用Pydantic进行数据验证
"""

from datetime import datetime
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
    nav: Optional[float] = Field(None, description="当前净值/估算净值")
    change_pct: Optional[float] = Field(None, description="日涨跌幅(%)")
    day7_return: Optional[float] = Field(None, description="近7日年化收益率(%)")
    previous_nav: Optional[float] = Field(None, description="上一交易日单位净值")
    previous_nav_date: Optional[str] = Field(None, description="上一交易日净值日期")
    estimated_nav: Optional[float] = Field(None, description="今日估算净值")
    estimated_change_pct: Optional[float] = Field(None, description="今日估算涨跌幅(%)")
    estimate_time: Optional[str] = Field(None, description="估值时间")
    is_estimated: bool = Field(default=False, description="是否为估算净值")
    source: Optional[str] = Field(None, description="行情数据来源")


class MarketIndexQuote(BaseModel):
    """大盘指数行情"""
    index_code: str = Field(..., description="指数代码")
    index_name: str = Field(..., description="指数名称")
    latest_price: Optional[float] = Field(None, description="最新价")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    change_amount: Optional[float] = Field(None, description="涨跌额")


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


class ValuationData(BaseModel):
    """估值数据 - 新增"""
    pe_ttm: Optional[float] = Field(None, description="PE-TTM")
    pb: Optional[float] = Field(None, description="PB")
    pe_percentile: Optional[float] = Field(None, description="PE历史百分位(0-100)")
    pb_percentile: Optional[float] = Field(None, description="PB历史百分位(0-100)")
    risk_premium: Optional[float] = Field(None, description="风险溢价(%)")
    equity_bond_ratio: Optional[float] = Field(None, description="股债性价比")
    status: str = Field(default="未知", description="估值状态: 极度低估/低估/合理/高估/极度高估")
    update_date: Optional[str] = Field(None, description="数据更新日期")


class MACDIndicators(BaseModel):
    """MACD指标 - 新增"""
    dif: Optional[float] = Field(None, description="DIF快线")
    dea: Optional[float] = Field(None, description="DEA慢线")
    bar: Optional[float] = Field(None, description="MACD柱状图")
    signal: str = Field(default="未知", description="信号: 金叉/死叉/多头/空头")


class RSIIndicators(BaseModel):
    """RSI指标 - 新增"""
    rsi_6: Optional[float] = Field(None, description="RSI(6)")
    rsi_12: Optional[float] = Field(None, description="RSI(12)")
    rsi_24: Optional[float] = Field(None, description="RSI(24)")
    status: str = Field(default="中性", description="状态: 超买/强势/中性/弱势/超卖")


class EnhancedTechnicalIndicators(BaseModel):
    """增强版技术指标 - 新增"""
    ma5: Optional[float] = Field(None, description="5日均线")
    ma10: Optional[float] = Field(None, description="10日均线")
    ma20: Optional[float] = Field(None, description="20日均线")
    ma60: Optional[float] = Field(None, description="60日均线")
    ma250: Optional[float] = Field(None, description="250日均线(年线)")
    trend: str = Field(default="未知", description="趋势: 上升/下降/震荡")
    formation: str = Field(default="无明确形态", description="形态")
    signals: List[str] = Field(default_factory=list, description="技术信号列表")
    macd: MACDIndicators = Field(default_factory=MACDIndicators)
    rsi: RSIIndicators = Field(default_factory=RSIIndicators)
    bias_ma5: Optional[float] = Field(None, description="MA5乖离率(%)")
    bias_ma20: Optional[float] = Field(None, description="MA20乖离率(%)")
    bias_ma250: Optional[float] = Field(None, description="年线乖离率(%)")
    volume_ratio: Optional[float] = Field(None, description="量比")


class PositionConfig(BaseModel):
    """用户仓位配置 - 新增"""
    fund_code: Optional[str] = Field(None, description="基金代码，None表示默认配置")
    fund_type: str = Field(..., description="基金类型分类")
    target_pct: float = Field(..., description="目标仓位(%)", ge=0, le=100)
    min_pct: float = Field(..., description="最低仓位线(%)", ge=0, le=100)
    max_pct: float = Field(..., description="最高仓位线(%)", ge=0, le=100)
    is_default: bool = Field(default=False, description="是否为该类型的默认配置")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @validator('min_pct')
    def validate_min(cls, v, values):
        if 'target_pct' in values and v > values['target_pct']:
            raise ValueError("最低仓位线不能高于目标仓位")
        return v

    @validator('max_pct')
    def validate_max(cls, v, values):
        if 'target_pct' in values and v < values['target_pct']:
            raise ValueError("最高仓位线不能低于目标仓位")
        return v


class PositionAdvice(BaseModel):
    """仓位建议 - 新增"""
    fund_code: str = Field(..., description="基金代码")
    fund_name: str = Field(..., description="基金名称")
    current_pct: float = Field(..., description="当前仓位(%)")
    current_amount: Optional[float] = Field(None, description="当前金额")
    target_pct: float = Field(..., description="目标仓位(%)")
    min_pct: float = Field(..., description="最低仓位线(%)")
    max_pct: float = Field(..., description="最高仓位线(%)")
    deviation_pct: float = Field(..., description="偏离度(%)")
    distance_to_min: float = Field(..., description="距离最低线(%)")
    distance_to_max: float = Field(..., description="距离最高线(%)")
    action: str = Field(..., description="操作建议: 加仓/减仓/持有/定投/观望")
    action_amount: Optional[float] = Field(None, description="建议操作金额")
    action_ratio: Optional[float] = Field(None, description="建议操作比例")
    urgency: str = Field(default="不急", description="紧急程度: 立即/本周/本月/不急")
    reason: str = Field(..., description="建议理由")


class SIPAdvice(BaseModel):
    """定投建议 - 新增"""
    fund_code: str = Field(..., description="基金代码")
    strategy: str = Field(..., description="策略: ma250/valuation/hybrid")
    base_amount: float = Field(..., description="用户基础定投金额")
    suggested_amount: float = Field(..., description="建议定投金额")
    multiplier: float = Field(..., description="定投倍数")
    signal: str = Field(..., description="信号: 开始定投/加倍定投/正常定投/减少定投/停止定投")
    take_profit_plan: List[Dict] = Field(default_factory=list, description="止盈计划")


class FiveDimensionScores(BaseModel):
    """五维评分 - 新增"""
    technical: float = Field(..., description="技术面得分(0-100)", ge=0, le=100)
    fundamental: float = Field(..., description="基本面得分(0-100)", ge=0, le=100)
    valuation: float = Field(..., description="估值面得分(0-100)", ge=0, le=100)
    capital_flow: float = Field(..., description="资金面得分(0-100)", ge=0, le=100)
    sentiment: float = Field(..., description="情绪面得分(0-100)", ge=0, le=100)
    total: float = Field(..., description="加权总分(0-100)", ge=0, le=100)
    weights: Dict[str, float] = Field(..., description="各维度权重")
