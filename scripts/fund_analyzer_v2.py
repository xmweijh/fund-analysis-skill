"""
基金分析器 V2 - 主控制器
整合所有 v2 分析模块，提供增强版基金分析流程
"""

import os
import sys
import argparse
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# 确保项目根目录在 sys.path 中
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.models import (
    FundBasicInfo,
    FundNavHistory,
    ValuationData,
    FiveDimensionScores,
    PositionAdvice,
)
from scripts.data_fetcher import DanjuanDataFetcher
from scripts.data_fetcher_v2 import ValuationDataFetcher
from scripts.analysis_v2 import (
    EnhancedTechnicalAnalyzer,
    TechnicalAnalysisResult,
    StrategyRouter,
    SIPAdvisor,
)
from scripts.position_config_manager import PositionConfigManager
from scripts.report_v2 import ReportGenerator
from scripts.portfolio_manager import PortfolioManager
from scripts.logger import logger


# 常见指数基金的指数代码映射（基金代码 -> 指数代码）
_FUND_INDEX_MAP: Dict[str, str] = {
    # 沪深300
    "110020": "000300",
    "100038": "000300",
    "161125": "000300",
    # 中证500
    "161017": "000905",
    "110033": "000905",
    # 创业板
    "161022": "399006",
    "110026": "399006",
    # 上证50
    "110003": "000016",
    # 中证1000
    "161032": "000852",
}

# 常见指数名称关键词 -> 指数代码
_INDEX_NAME_KEYWORDS: Dict[str, str] = {
    "沪深300": "000300",
    "中证500": "000905",
    "创业板": "399006",
    "上证50": "000016",
    "科创50": "000688",
    "中证1000": "000852",
    "恒生": "HSI",
    "纳斯达克": "NDX",
}


class FundAnalyzerV2:
    """
    基金分析器 V2

    整合 v2 模块，提供增强版基金分析：
    - 增强技术分析（MACD、RSI、BIAS）
    - 策略路由（指数基金/主动基金）
    - 五维评分体系
    - 仓位建议
    - 定投建议（可选）
    - HTML + JSON 报告输出
    """

    def __init__(self):
        """初始化所有 v2 模块"""
        self.data_fetcher = DanjuanDataFetcher()
        self.valuation_fetcher = ValuationDataFetcher()
        self.technical_analyzer = EnhancedTechnicalAnalyzer()
        self.strategy_router = StrategyRouter()
        self.sip_advisor = SIPAdvisor()
        self.position_manager = PositionConfigManager()
        self.report_generator = ReportGenerator()
        self.portfolio = PortfolioManager()

        logger.info("FundAnalyzerV2 初始化完成")

    # ================================================================== #
    #  主分析入口                                                         #
    # ================================================================== #

    def analyze(
        self,
        fund_code: str,
        enable_sip: bool = False,
        sip_base_amount: float = 1000.0,
        sip_strategy: str = "hybrid",
    ) -> Tuple[str, str]:
        """
        执行完整的 v2 基金分析流程

        Args:
            fund_code: 基金代码（6位数字）
            enable_sip: 是否生成定投建议
            sip_base_amount: 定投基础金额
            sip_strategy: 定投策略 ("ma250" / "valuation" / "hybrid")

        Returns:
            Tuple[str, str]: (html_path, json_path)
        """
        logger.info(f"[v2] 开始分析基金: {fund_code}")

        if not self._validate_fund_code(fund_code):
            raise ValueError(f"无效的基金代码: {fund_code}，必须是6位数字")

        # 1. 获取基础数据
        logger.info(f"[v2] Step 1: 获取基础数据 {fund_code}")
        basic_info = self._safe_fetch(
            self.data_fetcher.fetch_basic_info, fund_code, label="基础信息"
        )
        nav_history = self._safe_fetch(
            self.data_fetcher.fetch_nav_history, fund_code, 365, label="净值历史"
        )
        performance = self._safe_fetch(
            self.data_fetcher.fetch_performance, fund_code, label="业绩数据"
        )
        quote = self._safe_fetch(
            self.data_fetcher.fetch_realtime_quote, fund_code, label="实时行情"
        )
        manager = self._safe_fetch(
            self.data_fetcher.fetch_manager_info, fund_code, label="基金经理"
        )

        # 2. 获取估值数据（指数基金）
        logger.info(f"[v2] Step 2: 获取估值数据 {fund_code}")
        valuation = self._fetch_valuation(fund_code, basic_info)

        # 3. 增强技术分析
        logger.info(f"[v2] Step 3: 增强技术分析 {fund_code}")
        tech_result: Optional[TechnicalAnalysisResult] = None
        if nav_history and nav_history.navs:
            try:
                tech_result = self.technical_analyzer.analyze(nav_history)
                logger.info(
                    f"[v2] 技术分析完成，评分: {tech_result.buy_signal_score}"
                )
            except Exception as e:
                logger.warning(f"[v2] 技术分析失败: {e}")
        else:
            logger.warning(f"[v2] 净值历史数据无效，跳过技术分析")

        # 4. 路由到合适策略
        logger.info(f"[v2] Step 4: 策略路由 {fund_code}")
        strategy = None
        if basic_info:
            try:
                strategy = self.strategy_router.route(basic_info)
                logger.info(f"[v2] 使用策略: {strategy.get_strategy_name()}")
            except Exception as e:
                logger.warning(f"[v2] 策略路由失败: {e}")

        # 5. 计算五维评分
        logger.info(f"[v2] Step 5: 计算五维评分 {fund_code}")
        scores: Optional[FiveDimensionScores] = None
        if strategy:
            try:
                tech_score = float(tech_result.buy_signal_score) if tech_result else 50.0
                valuation_score = self._calc_valuation_score(valuation)
                fundamental_score = self._calc_fundamental_score(performance, manager)
                capital_flow_score = self._calc_capital_flow_score(basic_info, quote)
                sentiment_score = 50.0  # 默认中性

                scores = strategy.calculate_scores(
                    technical=tech_score,
                    valuation=valuation_score,
                    fundamental=fundamental_score,
                    capital_flow=capital_flow_score,
                    sentiment=sentiment_score,
                )
                logger.info(f"[v2] 五维评分完成，总分: {scores.total:.1f}")
            except Exception as e:
                logger.warning(f"[v2] 五维评分失败: {e}")

        # 6. 生成仓位建议
        logger.info(f"[v2] Step 6: 生成仓位建议 {fund_code}")
        position_advice = self._generate_position_advice(
            fund_code, basic_info, scores
        )

        # 7. 生成定投建议（按需）
        sip_advice_dict: Optional[Dict[str, Any]] = None
        if enable_sip:
            logger.info(f"[v2] Step 7: 生成定投建议 {fund_code}")
            sip_advice_dict = self._generate_sip_advice(
                fund_code,
                tech_result,
                valuation,
                sip_base_amount,
                sip_strategy,
            )

        # 8. 构建报告数据
        logger.info(f"[v2] Step 8: 构建报告数据 {fund_code}")
        report_data = self._build_report_data(
            fund_code=fund_code,
            basic_info=basic_info,
            quote=quote,
            tech_result=tech_result,
            valuation=valuation,
            scores=scores,
            position_advice=position_advice,
            sip_enabled=enable_sip,
            sip_advice=sip_advice_dict,
            performance=performance,
            manager=manager,
            strategy=strategy,
        )

        # 9. 生成并保存报告
        logger.info(f"[v2] Step 9: 生成 HTML/JSON 报告 {fund_code}")
        try:
            html_path, json_path = self.report_generator.generate(report_data)
            logger.info(f"[v2] 报告生成完成 HTML={html_path} JSON={json_path}")
        except Exception as e:
            logger.error(f"[v2] 报告生成失败: {e}", exc_info=True)
            raise

        return html_path, json_path

    # ================================================================== #
    #  辅助：数据获取                                                     #
    # ================================================================== #

    def _fetch_valuation(
        self,
        fund_code: str,
        basic_info: Optional[FundBasicInfo],
    ) -> Optional[ValuationData]:
        """
        获取指数估值数据。
        对于指数基金，尝试通过基金代码或基金名称推断对应的指数代码，然后获取估值。
        """
        index_code = None

        # 先尝试基金代码直接映射
        if fund_code in _FUND_INDEX_MAP:
            index_code = _FUND_INDEX_MAP[fund_code]

        # 再尝试从基金名称中推断
        if not index_code and basic_info and basic_info.fund_name:
            for keyword, code in _INDEX_NAME_KEYWORDS.items():
                if keyword in basic_info.fund_name:
                    index_code = code
                    break

        if not index_code:
            logger.debug(
                f"[v2] 未找到 {fund_code} 对应的指数代码，跳过估值获取"
            )
            return None

        try:
            valuation = self.valuation_fetcher.fetch_index_valuation(index_code)
            if valuation:
                logger.info(f"[v2] 获取估值数据成功: {index_code}")
            return valuation
        except Exception as e:
            logger.warning(f"[v2] 获取估值数据失败 {index_code}: {e}")
            return None

    # ================================================================== #
    #  辅助：评分计算                                                     #
    # ================================================================== #

    def _calc_valuation_score(self, valuation: Optional[ValuationData]) -> float:
        """
        根据估值数据计算估值面评分 (0-100)。
        主要依据 PE 百分位：百分位越低，得分越高。
        """
        if valuation is None:
            return 50.0  # 无数据时返回中性分

        pe_pct = valuation.pe_percentile
        if pe_pct is None:
            return 50.0

        # PE百分位 -> 估值评分（反向映射）
        # pe_pct=10 -> score=90, pe_pct=50 -> score=50, pe_pct=90 -> score=10
        score = 100.0 - pe_pct
        return max(0.0, min(100.0, score))

    def _calc_fundamental_score(
        self,
        performance: Any,
        manager: Any,
    ) -> float:
        """
        根据业绩数据和基金经理信息计算基本面评分 (0-100)。
        """
        score = 50.0

        if performance is None:
            return score

        # 近1年收益加分
        if hasattr(performance, "return_1y") and performance.return_1y is not None:
            r1y = performance.return_1y
            if r1y > 20:
                score += 15
            elif r1y > 10:
                score += 10
            elif r1y > 0:
                score += 5
            elif r1y < -20:
                score -= 15
            elif r1y < -10:
                score -= 10
            elif r1y < 0:
                score -= 5

        # 最大回撤惩罚
        if hasattr(performance, "max_drawdown") and performance.max_drawdown is not None:
            mdd = abs(performance.max_drawdown)
            if mdd > 50:
                score -= 15
            elif mdd > 30:
                score -= 10
            elif mdd > 20:
                score -= 5

        # 同类排名百分位加分（越高越好）
        if (
            hasattr(performance, "rank_percentile")
            and performance.rank_percentile is not None
        ):
            rp = performance.rank_percentile
            if rp > 75:
                score += 10
            elif rp > 50:
                score += 5
            elif rp < 25:
                score -= 10
            elif rp < 50:
                score -= 5

        # 基金经理加分
        if manager is not None:
            if hasattr(manager, "is_senior") and manager.is_senior:
                score += 5
            if (
                hasattr(manager, "manage_years")
                and manager.manage_years is not None
                and manager.manage_years >= 3
            ):
                score += 5

        return max(0.0, min(100.0, score))

    def _calc_capital_flow_score(
        self,
        basic_info: Optional[FundBasicInfo],
        quote: Any,
    ) -> float:
        """
        根据基金规模和涨跌幅估算资金面评分 (0-100)。
        """
        score = 50.0

        # 基金规模适中加分
        if basic_info and hasattr(basic_info, "fund_scale") and basic_info.fund_scale is not None:
            scale = basic_info.fund_scale
            if 10 <= scale <= 500:
                score += 5  # 规模适中
            elif scale < 1:
                score -= 10  # 规模过小，清盘风险

        # 日涨跌幅参考
        if quote and hasattr(quote, "change_pct") and quote.change_pct is not None:
            cp = quote.change_pct
            if cp > 3:
                score += 5  # 强势上涨
            elif cp > 1:
                score += 2
            elif cp < -3:
                score -= 5  # 大幅下跌
            elif cp < -1:
                score -= 2

        return max(0.0, min(100.0, score))

    # ================================================================== #
    #  辅助：仓位建议                                                     #
    # ================================================================== #

    def _generate_position_advice(
        self,
        fund_code: str,
        basic_info: Optional[FundBasicInfo],
        scores: Optional[FiveDimensionScores],
    ) -> Dict[str, Any]:
        """
        生成仓位建议字典。
        基于五维总分和仓位配置，给出加仓/减仓/持有建议。
        """
        # 获取基金类型
        fund_type = "宽基指数"
        if basic_info and basic_info.fund_type:
            ft = basic_info.fund_type
            if "债券" in ft or "债" in ft:
                fund_type = "债券基金"
            elif "货币" in ft:
                fund_type = "货币基金"
            elif "行业" in ft or "主题" in ft:
                fund_type = "行业指数"
            elif ft in {"股票型", "混合型", "灵活配置", "偏股混合", "平衡混合"}:
                fund_type = "主动混合"
            else:
                fund_type = "宽基指数"

        # 获取仓位配置
        try:
            config = self.position_manager.get_config(fund_code, fund_type)
        except Exception as e:
            logger.warning(f"[v2] 获取仓位配置失败: {e}")
            return {
                "fund_code": fund_code,
                "fund_type": fund_type,
                "action": "持有",
                "reason": "无法获取仓位配置，建议保持现有仓位",
                "target_pct": 10.0,
                "min_pct": 5.0,
                "max_pct": 20.0,
            }

        # 根据评分确定操作建议
        total_score = scores.total if scores else 50.0

        if total_score >= 70:
            action = "加仓"
            reason = f"综合评分 {total_score:.0f} 分，技术面+估值面均较强，建议适当加仓"
            urgency = "本月"
        elif total_score >= 55:
            action = "持有"
            reason = f"综合评分 {total_score:.0f} 分，各指标中性，建议持有或定投"
            urgency = "不急"
        elif total_score >= 40:
            action = "观望"
            reason = f"综合评分 {total_score:.0f} 分，市场偏弱，建议观望等待机会"
            urgency = "不急"
        else:
            action = "减仓"
            reason = f"综合评分 {total_score:.0f} 分，技术面/估值面偏弱，建议适当减仓"
            urgency = "本周"

        total_assets = self._estimate_total_assets()
        target_amount = total_assets * config.target_pct / 100 if total_assets else None
        min_amount = total_assets * config.min_pct / 100 if total_assets else None
        max_amount = total_assets * config.max_pct / 100 if total_assets else None

        return {
            "fund_code": fund_code,
            "fund_type": fund_type,
            "action": action,
            "urgency": urgency,
            "reason": reason,
            "target_pct": config.target_pct,
            "min_pct": config.min_pct,
            "max_pct": config.max_pct,
            "target_amount": target_amount,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "total_score": total_score,
            "config_source": "position_manager",
        }

    def _estimate_total_assets(self) -> Optional[float]:
        """
        估算用户总资产（用于计算仓位金额）。
        简单地对所有持仓的买入金额求和，若无持仓返回 None。
        """
        entries = self.portfolio.list_all()
        if not entries:
            return None

        total = 0.0
        has_amount = False
        for entry in entries:
            if entry.cost_amount is not None:
                total += entry.cost_amount
                has_amount = True

        return total if has_amount else None

    # ================================================================== #
    #  辅助：定投建议                                                     #
    # ================================================================== #

    def _generate_sip_advice(
        self,
        fund_code: str,
        tech_result: Optional[Any],
        valuation: Optional[ValuationData],
        base_amount: float,
        strategy: str,
    ) -> Dict[str, Any]:
        """生成定投建议，序列化为字典"""
        try:
            technical_indicators = tech_result.indicators if tech_result else None

            advice = self.sip_advisor.get_advice(
                strategy=strategy,
                technical=technical_indicators,
                valuation=valuation,
                base_amount=base_amount,
            )

            # Convert TakeProfitPlan objects to dicts
            take_profit_plans = []
            if hasattr(advice, 'take_profit_plans') and advice.take_profit_plans:
                for tp in advice.take_profit_plans:
                    if hasattr(tp, 'profit_level'):
                        take_profit_plans.append({
                            "profit_level": tp.profit_level,
                            "description": tp.description,
                        })
                    else:
                        take_profit_plans.append(tp)

            return {
                "fund_code": fund_code,
                "strategy": advice.strategy,
                "signal": advice.signal,
                "multiplier": advice.multiplier,
                "base_amount": advice.base_amount,
                "recommended_amount": advice.recommended_amount,
                "confidence": getattr(advice, 'confidence', 50),
                "reasons": getattr(advice, 'reasons', []),
                "risks": getattr(advice, 'risks', []),
                "take_profit_plans": take_profit_plans,
                "indicators_snapshot": getattr(advice, 'indicators_snapshot', {}),
            }
        except Exception as e:
            logger.warning(f"[v2] 生成定投建议失败: {e}")
            return {
                "fund_code": fund_code,
                "strategy": strategy,
                "signal": "正常定投",
                "multiplier": 1.0,
                "base_amount": base_amount,
                "recommended_amount": base_amount,
                "confidence": 50,
                "reasons": ["数据不足，使用默认定投策略"],
                "risks": ["信息不完整，请等待数据完善"],
                "take_profit_plans": [],
                "indicators_snapshot": {},
                "error": str(e),
            }

    # ================================================================== #
    #  辅助：构建报告数据                                                  #
    # ================================================================== #

    def _build_report_data(
        self,
        fund_code: str,
        basic_info: Optional[FundBasicInfo],
        quote: Any,
        tech_result: Optional[TechnicalAnalysisResult],
        valuation: Optional[ValuationData],
        scores: Optional[FiveDimensionScores],
        position_advice: Optional[Dict[str, Any]],
        sip_enabled: bool,
        sip_advice: Optional[Dict[str, Any]],
        performance: Any,
        manager: Any,
        strategy: Any,
    ) -> Dict[str, Any]:
        """
        将所有分析结果组装为 ReportGenerator 所需的字典格式。
        """
        # ── 基础信息 ────────────────────────────────────────────────
        fund_name = basic_info.fund_name if basic_info else fund_code
        fund_type = basic_info.fund_type if basic_info else None

        # ── 技术指标 ────────────────────────────────────────────────
        technical_dict: Dict[str, Any] = {}
        if tech_result:
            ind = tech_result.indicators
            technical_dict = {
                "ma5": ind.ma5,
                "ma10": ind.ma10,
                "ma20": ind.ma20,
                "ma60": ind.ma60,
                "ma250": ind.ma250,
                "trend": ind.trend,
                "formation": ind.formation,
                "signals": ind.signals,
                "buy_signal_score": tech_result.buy_signal_score,
                "signal_reasons": tech_result.signal_reasons,
                "risk_factors": tech_result.risk_factors,
                "bias_ma5": ind.bias_ma5,
                "bias_ma20": ind.bias_ma20,
                "bias_ma250": ind.bias_ma250,
                "macd": {
                    "dif": ind.macd.dif,
                    "dea": ind.macd.dea,
                    "bar": ind.macd.bar,
                    "signal": ind.macd.signal,
                },
                "rsi": {
                    "rsi_6": ind.rsi.rsi_6,
                    "rsi_12": ind.rsi.rsi_12,
                    "rsi_24": ind.rsi.rsi_24,
                    "status": ind.rsi.status,
                },
            }

        # ── 估值数据 ────────────────────────────────────────────────
        valuation_dict: Optional[Dict[str, Any]] = None
        if valuation:
            valuation_dict = {
                "pe_ttm": valuation.pe_ttm,
                "pb": valuation.pb,
                "pe_percentile": valuation.pe_percentile,
                "pb_percentile": valuation.pb_percentile,
                "risk_premium": valuation.risk_premium,
                "status": valuation.status,
                "update_date": valuation.update_date,
            }

        # ── 五维评分 ────────────────────────────────────────────────
        scores_dict: Optional[Dict[str, Any]] = None
        if scores:
            scores_dict = {
                "technical": scores.technical,
                "fundamental": scores.fundamental,
                "valuation": scores.valuation,
                "capital_flow": scores.capital_flow,
                "sentiment": scores.sentiment,
                "total": scores.total,
                "weights": scores.weights,
            }

        # ── 实时行情 ────────────────────────────────────────────────
        quote_dict: Optional[Dict[str, Any]] = None
        if quote:
            quote_dict = {
                "nav": getattr(quote, "nav", None),
                "change_pct": getattr(quote, "change_pct", None),
                "previous_nav": getattr(quote, "previous_nav", None),
                "previous_nav_date": getattr(quote, "previous_nav_date", None),
                "estimated_nav": getattr(quote, "estimated_nav", None),
                "estimated_change_pct": getattr(quote, "estimated_change_pct", None),
                "estimate_time": getattr(quote, "estimate_time", None),
                "is_estimated": getattr(quote, "is_estimated", False),
            }

        # ── 业绩数据 ────────────────────────────────────────────────
        performance_dict: Optional[Dict[str, Any]] = None
        if performance:
            performance_dict = {
                "return_1m": getattr(performance, "return_1m", None),
                "return_3m": getattr(performance, "return_3m", None),
                "return_6m": getattr(performance, "return_6m", None),
                "return_1y": getattr(performance, "return_1y", None),
                "return_3y": getattr(performance, "return_3y", None),
                "annualized_return": getattr(performance, "annualized_return", None),
                "max_drawdown": getattr(performance, "max_drawdown", None),
                "rank_percentile": getattr(performance, "rank_percentile", None),
            }

        # ── 基金经理 ────────────────────────────────────────────────
        manager_dict: Optional[Dict[str, Any]] = None
        if manager:
            manager_dict = {
                "manager_name": getattr(manager, "manager_name", None),
                "experience_years": getattr(manager, "experience_years", None),
                "manage_years": getattr(manager, "manage_years", None),
                "avg_return": getattr(manager, "avg_return", None),
                "is_senior": getattr(manager, "is_senior", False),
            }

        # ── 操作建议 ────────────────────────────────────────────────
        action = "观望"
        conclusion = "请结合自身情况谨慎决策"
        if position_advice:
            action = position_advice.get("action", "观望")
            total_score = position_advice.get("total_score", 50.0)
            conclusion = position_advice.get("reason", conclusion)

        # 构建完整报告字典
        data: Dict[str, Any] = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_type": fund_type,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analyzer_version": "v2",
            "strategy_name": strategy.get_strategy_name() if strategy else None,
            "quote": quote_dict,
            "technical": technical_dict if technical_dict else None,
            "valuation": valuation_dict,
            "scores": scores_dict,
            "performance": performance_dict,
            "manager": manager_dict,
            "position_advice": position_advice,
            "sip_enabled": sip_enabled,
            "sip_advice": sip_advice,
            "action": action,
            "conclusion": conclusion,
        }

        return data

    # ================================================================== #
    #  工具方法                                                           #
    # ================================================================== #

    @staticmethod
    def _validate_fund_code(fund_code: str) -> bool:
        """验证基金代码格式（6位纯数字）"""
        if not fund_code:
            return False
        return len(fund_code) == 6 and fund_code.isdigit()

    @staticmethod
    def _safe_fetch(func, *args, label: str = "", **kwargs) -> Any:
        """
        安全调用数据获取函数，异常时记录日志并返回 None。
        """
        try:
            result = func(*args, **kwargs)
            if label:
                logger.info(f"[v2] 获取{label}成功")
            return result
        except Exception as e:
            if label:
                logger.warning(f"[v2] 获取{label}失败: {e}")
            return None


# ====================================================================== #
#  CLI 入口                                                               #
# ====================================================================== #


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="基金分析器 V2 - 生成 HTML + JSON 报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/fund_analyzer_v2.py 008888
  python scripts/fund_analyzer_v2.py 008888 --sip
  python scripts/fund_analyzer_v2.py 008888 --sip --sip-amount 2000 --sip-strategy hybrid
        """,
    )
    parser.add_argument("fund_code", type=str, help="6位基金代码，如 008888")
    parser.add_argument(
        "--sip",
        action="store_true",
        default=False,
        help="是否生成定投建议（默认不生成）",
    )
    parser.add_argument(
        "--sip-amount",
        type=float,
        default=1000.0,
        metavar="AMOUNT",
        help="定投基础金额（默认 1000 元）",
    )
    parser.add_argument(
        "--sip-strategy",
        type=str,
        default="hybrid",
        choices=["ma250", "valuation", "hybrid"],
        metavar="STRATEGY",
        help="定投策略: ma250 / valuation / hybrid（默认 hybrid）",
    )

    args = parser.parse_args()

    analyzer = FundAnalyzerV2()

    try:
        print(f"正在分析基金 {args.fund_code} ...")
        html_path, json_path = analyzer.analyze(
            fund_code=args.fund_code,
            enable_sip=args.sip,
            sip_base_amount=args.sip_amount,
            sip_strategy=args.sip_strategy,
        )
        print(f"\n分析完成！")
        print(f"  HTML 报告: {html_path}")
        print(f"  JSON 数据: {json_path}")
    except ValueError as e:
        print(f"参数错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        print(f"分析失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
