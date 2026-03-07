"""
报告生成模块
"""

from typing import Optional, Dict, Any

from .models import (
    FundBasicInfo, FundRealtimeQuote, TechnicalIndicators,
    HoldingAnalysis, ManagerInfo, PerformanceData,
    SentimentData, InvestmentAdvice
)
from .logger import logger


class ReportGenerator:
    """报告生成器"""

    def generate(
        self,
        fund_code: str,
        basic_info: Optional[FundBasicInfo],
        quote: Optional[FundRealtimeQuote],
        technical: Optional[TechnicalIndicators],
        holding: Optional[HoldingAnalysis],
        manager: Optional[ManagerInfo],
        performance: Optional[PerformanceData],
        sentiment: Optional[SentimentData],
        advice: Optional[InvestmentAdvice],
        stock_quotes: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成Markdown格式报告

        Args:
            fund_code: 基金代码
            basic_info: 基金基础信息
            quote: 实时行情
            technical: 技术分析
            holding: 持仓分析
            manager: 基金经理分析
            performance: 业绩分析
            sentiment: 舆情分析
            advice: 投资建议

        Returns:
            Markdown格式报告
        """
        try:
            report_lines = []

            # 标题
            fund_name = basic_info.fund_name if basic_info else f"基金{fund_code}"
            report_lines.append(f"# {fund_name} 基金分析报告\n")

            # 报告生成时间
            from datetime import datetime
            report_lines.append(f"> 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            report_lines.append("---\n")

            # 投资建议摘要（放最顶部）
            if advice:
                report_lines.append(self._format_investment_summary(advice, sentiment, performance))

            # 基金基本信息
            if basic_info:
                report_lines.append(self._format_basic_info(basic_info))

            # 实时行情
            if quote:
                report_lines.append(self._format_realtime_quote(quote))

            # 技术面分析
            if technical:
                report_lines.append(self._format_technical_analysis(technical))

            # 持仓分析
            if holding:
                report_lines.append(self._format_holding_analysis(holding, stock_quotes or {}))

            # 基金经理分析
            if manager:
                report_lines.append(self._format_manager_info(manager))

            # 业绩分析
            if performance:
                report_lines.append(self._format_performance_analysis(performance))

            # 舆情分析
            if sentiment:
                report_lines.append(self._format_sentiment_analysis(sentiment))

            # 详细投资建议
            if advice:
                report_lines.append(self._format_detailed_advice(advice))

            # 免责声明
            report_lines.append(self._format_disclaimer())

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return f"# 报告生成失败\n\n错误信息: {str(e)}"

    def _format_investment_summary(
        self,
        advice: InvestmentAdvice,
        sentiment: Optional[SentimentData] = None,
        performance: Optional[PerformanceData] = None
    ) -> str:
        """格式化投资建议摘要卡片（报告顶部醒目展示）"""
        lines = []

        # 操作建议 → Emoji 映射
        _ACTION_EMOJI = {
            "买入":   "🟢",
            "加仓":   "🟢",
            "建仓":   "🟢",
            "定投":   "🔵",
            "持有":   "🟡",
            "观望":   "🟡",
            "减仓":   "🟠",
            "卖出":   "🔴",
            "清仓":   "🔴",
        }
        action_emoji = _ACTION_EMOJI.get(advice.action, "⚪")

        lines.append("## 📋 综合操作建议\n")
        lines.append("> 以下综合技术面、基本面和舆情进行评估，仅供参考，不构成投资建议。\n")
        lines.append("| 维度 | 评估 |")
        lines.append("|------|------|")
        lines.append(f"| **操作建议** | {action_emoji} **{advice.action}** |")
        lines.append(f"| **核心结论** | {advice.conclusion} |")

        # 近1年收益（基本面参考）
        if performance and performance.return_1y is not None:
            ret_sign = "📈" if performance.return_1y >= 0 else "📉"
            lines.append(f"| **近1年收益** | {ret_sign} {performance.return_1y:+.2f}% |")

        # 最大回撤
        if performance and performance.max_drawdown is not None:
            lines.append(f"| **历史最大回撤** | -{performance.max_drawdown:.2f}% |")

        # 舆情
        if sentiment:
            sent_emoji = {"强烈正面": "😀", "正面": "🙂", "中性": "😐",
                          "负面": "😟", "强烈负面": "😨"}.get(sentiment.level, "")
            lines.append(f"| **舆情情绪** | {sent_emoji} {sentiment.level}（{sentiment.score:.0f}/100）|")

        # 买卖点位
        if advice.ideal_buy:
            lines.append(f"| **参考买点** | {advice.ideal_buy} |")
        if advice.take_profit:
            lines.append(f"| **参考止盈** | {advice.take_profit} |")
        if advice.stop_loss:
            lines.append(f"| **参考止损** | {advice.stop_loss} |")

        lines.append("")
        lines.append("---\n")
        return "\n".join(lines)

    def _format_basic_info(self, info: FundBasicInfo) -> str:
        """格式化基金基础信息"""
        lines = []
        lines.append("## 📊 基金基本信息\n")
        lines.append(f"- **基金代码**: {info.fund_code}")
        lines.append(f"- **基金名称**: {info.fund_name}")
        if info.fund_type:
            lines.append(f"- **基金类型**: {info.fund_type}")
        if info.fund_scale:
            lines.append(f"- **基金规模**: {info.fund_scale:.2f}亿元")
        if info.establish_date:
            lines.append(f"- **成立日期**: {info.establish_date}")
        if info.manager_name:
            lines.append(f"- **基金经理**: {info.manager_name}")
        if info.company:
            lines.append(f"- **基金公司**: {info.company}")
        lines.append("")
        return "\n".join(lines)

    def _format_realtime_quote(self, quote: FundRealtimeQuote) -> str:
        """格式化实时行情"""
        lines = []
        lines.append("## 📈 实时行情\n")
        lines.append(f"- **当前净值**: {quote.nav:.4f}")
        lines.append(f"- **日涨跌幅**: {quote.change_pct:+.2f}%")
        if quote.day7_return:
            lines.append(f"- **近7日年化**: {quote.day7_return:+.2f}%")
        lines.append("")
        return "\n".join(lines)

    def _format_technical_analysis(self, technical: TechnicalIndicators) -> str:
        """格式化技术面分析"""
        lines = []
        lines.append("## 📉 技术面分析\n")

        lines.append("### 移动平均线\n")
        if technical.ma5:
            lines.append(f"- **MA5**: {technical.ma5:.4f}")
        if technical.ma10:
            lines.append(f"- **MA10**: {technical.ma10:.4f}")
        if technical.ma20:
            lines.append(f"- **MA20**: {technical.ma20:.4f}")
        if technical.ma60:
            lines.append(f"- **MA60**: {technical.ma60:.4f}")

        lines.append(f"\n### 趋势判断\n")
        lines.append(f"- **趋势**: {technical.trend}")
        lines.append(f"- **形态**: {technical.formation}")

        if technical.signals:
            lines.append(f"\n### 技术信号\n")
            for signal in technical.signals:
                lines.append(f"- {signal}")

        lines.append(f"\n### 近期收益率\n")
        if technical.return_30d:
            lines.append(f"- **30天**: {technical.return_30d:+.2f}%")
        if technical.return_60d:
            lines.append(f"- **60天**: {technical.return_60d:+.2f}%")
        if technical.return_90d:
            lines.append(f"- **90天**: {technical.return_90d:+.2f}%")

        lines.append("")
        return "\n".join(lines)

    def _format_holding_analysis(
        self,
        holding: HoldingAnalysis,
        stock_quotes: Dict[str, Any] = None
    ) -> str:
        """格式化持仓分析（含重仓股最新行情）"""
        stock_quotes = stock_quotes or {}
        lines = []
        lines.append("## 🏢 持仓分析\n")

        if holding.top10_holdings:
            has_quotes = bool(stock_quotes)
            if has_quotes:
                lines.append("### 前十大重仓股（含最新行情）\n")
                lines.append("| # | 股票 | 代码 | 持仓占比 | 最新价 | 涨跌幅 |")
                lines.append("|---|------|------|---------|-------|--------|")
            else:
                lines.append("### 前十大重仓股\n")
            for i, stock in enumerate(holding.top10_holdings, 1):
                stock_name = stock.get('stock_name', '未知') if isinstance(stock, dict) else stock.stock_name
                stock_code = stock.get('stock_code', '') if isinstance(stock, dict) else getattr(stock, 'stock_code', '')
                holding_ratio = stock.get('holding_ratio', 0) if isinstance(stock, dict) else (stock.holding_ratio or 0)

                if has_quotes and stock_code:
                    # 尝试匹配：精确 or 去前置0
                    q = stock_quotes.get(stock_code) or stock_quotes.get(stock_code.lstrip('0'))
                    if q and q.get('change_pct') is not None:
                        cp = q['change_pct']
                        price = q.get('price')
                        arrow = "🔴" if cp < 0 else ("🟢" if cp > 0 else "⬜")
                        price_str = f"{price:.2f}" if price is not None else "-"
                        lines.append(
                            f"| {i} | {stock_name} | {stock_code} | {holding_ratio:.2f}% "
                            f"| {price_str} | {arrow} {cp:+.2f}% |"
                        )
                    else:
                        lines.append(
                            f"| {i} | {stock_name} | {stock_code} | {holding_ratio:.2f}% | - | - |"
                        )
                elif has_quotes:
                    lines.append(
                        f"| {i} | {stock_name} | - | {holding_ratio:.2f}% | - | - |"
                    )
                else:
                    lines.append(f"{i}. {stock_name} - {holding_ratio:.2f}%")

        if holding.holding_concentration:
            lines.append(f"\n- **持仓集中度**: {holding.holding_concentration:.2f}%")

        lines.append(f"- **持仓风格**: {holding.style}")

        if holding.industry_concentration:
            lines.append(f"\n### 行业分布\n")
            for industry, ratio in holding.industry_concentration.items():
                if ratio > 0:
                    lines.append(f"- {industry}: {ratio:.2f}%")

        lines.append("")
        return "\n".join(lines)

    def _format_manager_info(self, manager: ManagerInfo) -> str:
        """格式化基金经理信息"""
        lines = []
        lines.append("## 👨‍💼 基金经理分析\n")

        if manager.manager_name:
            lines.append(f"- **姓名**: {manager.manager_name}")
        if manager.experience_years:
            lines.append(f"- **从业年限**: {manager.experience_years}年")
        if manager.manage_years:
            lines.append(f"- **管理该基金**: {manager.manage_years}年")
        if manager.fund_count:
            lines.append(f"- **管理基金数**: {manager.fund_count}只")
        if manager.avg_return:
            lines.append(f"- **平均收益率**: {manager.avg_return:+.2f}%")
        if manager.max_drawdown:
            lines.append(f"- **最大回撤**: {manager.max_drawdown:.2f}%")

        if manager.is_senior:
            lines.append(f"\n✅ **资深基金经理**")
        else:
            lines.append(f"\nℹ️ **中等资历基金经理**")

        lines.append("")
        return "\n".join(lines)

    def _format_performance_analysis(self, performance: PerformanceData) -> str:
        """格式化业绩分析"""
        lines = []
        lines.append("## 📊 业绩分析\n")

        # ── 各时间段收益率 ──────────────────────────────────────────────
        lines.append("### 📅 各时间段收益率\n")
        period_rows = [
            ("近1月",  performance.return_1m),
            ("近3月",  performance.return_3m),
            ("近6月",  performance.return_6m),
            ("近1年",  performance.return_1y),
            ("近3年",  performance.return_3y),
            ("近5年",  performance.return_5y),
            ("成立以来", performance.annualized_return),
        ]
        has_period = any(v is not None for _, v in period_rows)
        if has_period:
            for label, val in period_rows:
                if val is not None:
                    lines.append(f"- **{label}**: {val:+.2f}%")
        lines.append("")

        # ── 逐年业绩 + 同类排名对比表 ────────────────────────────────────
        if performance.yearly_performance:
            lines.append("### 📆 逐年业绩 & 同类排名\n")
            lines.append("| 年份/时段 | 基金收益 | 基准收益 | 超额收益 | 最大回撤 | 同类排名 | 超越比例 |")
            lines.append("|---------|---------|---------|---------|---------|---------|---------|")
            for yp in performance.yearly_performance:
                fund_ret  = f"{yp.self_return:+.2f}%" if yp.self_return is not None else "-"
                bench_ret = f"{yp.benchmark_return:+.2f}%" if yp.benchmark_return is not None else "-"
                if yp.self_return is not None and yp.benchmark_return is not None:
                    excess = yp.self_return - yp.benchmark_return
                    excess_str = f"{excess:+.2f}%"
                    # 添加超跑/跑输标记
                    if excess > 0:
                        excess_str = f"✅ {excess_str}"
                    elif excess < -2:
                        excess_str = f"❌ {excess_str}"
                else:
                    excess_str = "-"
                mdd       = f"-{yp.max_drawdown:.2f}%" if yp.max_drawdown is not None else "-"
                rank_raw  = yp.rank if yp.rank else "-"
                rank_pct  = f"**{yp.rank_pct:.1f}%**" if yp.rank_pct is not None else "-"
                lines.append(f"| {yp.year} | {fund_ret} | {bench_ret} | {excess_str} | {mdd} | {rank_raw} | {rank_pct} |")
            lines.append("")
            lines.append("> 💡 **超越比例**：超过同类基金的百分比（越高越好）。基准为沪深300。")
            lines.append("")

        # ── 综合业绩指标 ─────────────────────────────────────────────────
        lines.append("### 📌 综合业绩指标\n")
        if performance.max_drawdown is not None:
            lines.append(f"- **历史最大回撤（成立以来）**: -{performance.max_drawdown:.2f}%")
        if performance.rank_percentile is not None:
            lines.append(f"- **同类超越比例（成立以来）**: {performance.rank_percentile:.1f}%")
        if performance.excess_return is not None:
            sign = "✅" if performance.excess_return > 0 else "❌"
            lines.append(f"- **今年以来超额收益（vs基准）**: {sign} {performance.excess_return:+.2f}%")

        lines.append("")
        return "\n".join(lines)

    def _format_sentiment_analysis(self, sentiment: SentimentData) -> str:
        """格式化舆情分析"""
        lines = []
        lines.append("## 📰 舆情分析\n")

        lines.append(f"- **舆情得分**: {sentiment.score:.1f}/100")
        lines.append(f"- **情绪等级**: {sentiment.level}")
        lines.append(f"- **公告数量**: {sentiment.news_count}条（展示前{len(sentiment.news_items)}条有效信号）")

        if sentiment.keywords:
            lines.append(f"\n### 关键词\n")
            lines.append(", ".join(sentiment.keywords))

        if sentiment.news_items:
            lines.append(f"\n### 重要公告\n")
            _SENTIMENT_LABEL = {
                "正面": "✅ 利好",
                "负面": "⚠️ 利空",
                "中性": "➖ 中性",
            }
            for i, news in enumerate(sentiment.news_items[:5], 1):
                label = _SENTIMENT_LABEL.get(news.sentiment, news.sentiment)
                lines.append(f"{i}. **{label}** {news.title}")
                if news.summary:
                    lines.append(f"   - {news.summary}")
                lines.append("")
        else:
            lines.append("\n> 暂无有效舆情信号（季报/年报/运营公告已过滤）\n")

        lines.append("")
        return "\n".join(lines)

    def _format_detailed_advice(self, advice: InvestmentAdvice) -> str:
        """格式化详细投资建议"""
        lines = []
        lines.append("## 💼 详细投资建议\n")

        lines.append("### 买卖点位\n")
        if advice.ideal_buy:
            lines.append(f"- **理想买点**: {advice.ideal_buy}")
        if advice.secondary_buy:
            lines.append(f"- **次要买点**: {advice.secondary_buy}")
        if advice.take_profit:
            lines.append(f"- **止盈位**: {advice.take_profit}")
        if advice.stop_loss:
            lines.append(f"- **止损位**: {advice.stop_loss}")

        if advice.checklist:
            lines.append(f"\n### 操作检查清单\n")
            for item in advice.checklist:
                lines.append(item)

        lines.append("")
        return "\n".join(lines)

    def _format_disclaimer(self) -> str:
        """格式化免责声明"""
        lines = []
        lines.append("---\n")
        lines.append("## ⚠️ 免责声明\n")
        lines.append("""
本报告仅供参考,不构成投资建议。投资有风险,入市需谨慎。

- 基金过往业绩不代表未来表现
- 本报告基于公开数据分析,可能存在滞后性
- 请根据自身风险承受能力进行投资决策
- 建议咨询专业的投资顾问

**数据来源**: 蛋卷基金API
""")
        lines.append("")
        return "\n".join(lines)

    def save_report(self, report: str, filename: str) -> str:
        """
        保存报告到文件

        Args:
            report: 报告内容
            filename: 文件名

        Returns:
            文件路径
        """
        import os

        # 确保文件扩展名是.md
        if not filename.endswith('.md'):
            filename += '.md'

        # 保存到固定的 reports/ 目录
        reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"报告已保存到: {file_path}")
        return file_path
