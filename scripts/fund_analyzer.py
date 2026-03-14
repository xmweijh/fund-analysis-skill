"""
基金分析主控制器
整合所有分析模块,执行完整的分析流程
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List
from datetime import datetime

# 确保 fund-analysis/ 根目录在 sys.path 中
# 无论以 `python scripts/fund_analyzer.py` 还是 `python -m scripts.fund_analyzer` 运行均有效
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)   # fund-analysis/
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.models import (
    FundBasicInfo, FundRealtimeQuote, FundNavHistory,
    HoldingAnalysis, ManagerInfo, PerformanceData,
    SentimentData, TechnicalIndicators, InvestmentAdvice
)
from scripts.data_fetcher import DanjuanDataFetcher
from scripts.technical_analysis import TechnicalAnalyzer
from scripts.holding_analysis import HoldingAnalyzer
from scripts.manager_analysis import ManagerAnalyzer
from scripts.performance_analysis import PerformanceAnalyzer
from scripts.sentiment_analysis import SentimentAnalyzer
from scripts.investment_advisor import InvestmentAdvisor
from scripts.report_generator import ReportGenerator
from scripts.portfolio_manager import PortfolioManager, PortfolioEntry
from scripts.recommendation_engine import FundScorer, FundRanker, FundRecommendationInput
from scripts.recommendation_advisor import RecommendationReportGenerator
from scripts.logger import logger


class FundAnalyzer:
    """基金分析器主类"""

    def __init__(self):
        """初始化分析器"""
        self.data_fetcher = DanjuanDataFetcher()
        self.technical_analyzer = TechnicalAnalyzer()
        self.holding_analyzer = HoldingAnalyzer()
        self.manager_analyzer = ManagerAnalyzer()
        self.performance_analyzer = PerformanceAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.investment_advisor = InvestmentAdvisor()
        self.report_generator = ReportGenerator()
        self.portfolio = PortfolioManager()

        logger.info("FundAnalyzer初始化完成")

    # ─────────────────────────── 持仓管理接口 ───────────────────────────

    def portfolio_add(
        self,
        fund_code: str,
        fund_name: Optional[str] = None,
        shares: Optional[float] = None,
        cost_nav: Optional[float] = None,
        cost_amount: Optional[float] = None,
        note: Optional[str] = None,
    ) -> str:
        """
        添加或更新持仓
        返回操作结果的 Markdown 文本
        """
        if not self._validate_fund_code(fund_code):
            return f"❌ 无效的基金代码 `{fund_code}`，必须是6位数字。"

        existed = self.portfolio.get(fund_code) is not None
        entry = self.portfolio.add(
            fund_code=fund_code,
            fund_name=fund_name,
            shares=shares,
            cost_nav=cost_nav,
            cost_amount=cost_amount,
            note=note,
        )
        verb = "更新" if existed else "新增"
        lines = [
            f"✅ **{verb}持仓成功**",
            f"",
            f"- 基金代码：`{entry.fund_code}`",
            f"- 基金名称：{entry.fund_name or '（未填写）'}",
        ]
        if entry.shares is not None:
            lines.append(f"- 持有份额：{entry.shares:.2f}")
        if entry.cost_nav is not None:
            lines.append(f"- 买入净值：{entry.cost_nav:.4f}")
        if entry.cost_amount is not None:
            lines.append(f"- 买入金额：{entry.cost_amount:.2f} 元")
        if entry.note:
            lines.append(f"- 备注：{entry.note}")
        lines.append("")
        lines.append(self.portfolio.render_table())
        return "\n".join(lines)

    def portfolio_remove(self, fund_code: str) -> str:
        """
        删除持仓
        返回操作结果的 Markdown 文本
        """
        ok = self.portfolio.remove(fund_code)
        if not ok:
            return f"⚠️ 持仓中没有基金 `{fund_code}`，无需删除。"
        lines = [
            f"✅ **已删除持仓** `{fund_code}`",
            "",
            self.portfolio.render_table(),
        ]
        return "\n".join(lines)

    def portfolio_list(self) -> str:
        """
        展示当前完整持仓列表（Markdown 格式）
        """
        entries = self.portfolio.list_all()
        if not entries:
            return (
                "📭 **当前持仓列表为空**\n\n"
                "你可以告诉我：\n"
                "- 「添加持仓 008975 易方达蓝筹精选混合」\n"
                "- 「持仓 100000份 买入净值1.5 110011」"
            )
        lines = [
            f"## 📋 我的持仓列表（共 {len(entries)} 只）",
            "",
            self.portfolio.render_table(),
        ]
        return "\n".join(lines)

    def portfolio_analyze_all(self) -> str:
        """
        批量分析持仓中所有基金，生成组合分析报告
        报告结构：总结摘要 → 目录 → 持仓列表 → 各基金详细报告
        """
        import re

        entries = self.portfolio.list_all()
        if not entries:
            return "📭 持仓列表为空，请先添加持仓后再进行组合分析。"

        fund_codes = [e.fund_code for e in entries]
        logger.info(f"开始批量分析持仓：{fund_codes}")

        # 记录每只基金的报告正文和提取的关键元数据
        reports: List[str] = []          # 已带锚点的报告正文
        failed: List[str] = []
        meta_list: List[dict] = []       # 每只基金的摘要元数据

        # 逐只分析（避免并发太多 API 请求）
        for entry in entries:
            code = entry.fund_code
            logger.info(f"分析持仓基金: {code}")
            try:
                report = self.analyze(code)

                # ── 从报告文本提取关键字段 ──────────────────────────
                meta = self._extract_portfolio_meta(code, entry, report)
                meta_list.append(meta)

                # ── 在报告标题前注入 HTML 锚点 ─────────────────────
                anchor_id = f"fund-{code}"
                # 匹配 "# Xxx 基金分析报告" 格式的标题行
                anchored_report = re.sub(
                    r'^(# .+基金分析报告)',
                    rf'<a id="{anchor_id}"></a>\n\1',
                    report,
                    count=1,
                    flags=re.MULTILINE,
                )
                reports.append(anchored_report)
            except Exception as e:
                logger.error(f"分析 {code} 失败: {e}")
                failed.append(code)
                meta_list.append({
                    "code": code,
                    "name": entry.fund_name or code,
                    "action": "❌ 失败",
                    "change_pct": None,
                    "nav": None,
                    "nav_time": None,
                    "conclusion": str(e)[:30],
                    "return_1y": None,
                })

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # ── 1. 文档总标题 ─────────────────────────────────────────
        header_lines = [
            "# 📊 持仓组合分析报告",
            "",
            f"> 报告生成时间：{now_str}",
            f"> 分析基金数：{len(entries)} 只，成功：{len(reports)} 只"
            + (f"，失败：{len(failed)} 只" if failed else ""),
            "",
        ]
        if failed:
            header_lines.append(
                f"⚠️ 以下基金分析失败，请检查代码或网络：{', '.join(failed)}\n"
            )

        # ── 2. 持仓总结摘要表 ─────────────────────────────────────
        header_lines += self._build_portfolio_summary(meta_list)

        # ── 3. 目录（锚点跳转） ───────────────────────────────────
        header_lines += self._build_portfolio_toc(meta_list)

        # ── 4. 持仓明细表 ────────────────────────────────────────
        header_lines.append("---\n")
        header_lines.append("## 📋 持仓列表\n")
        header_lines.append(self.portfolio.render_table())
        header_lines.append("\n---\n")

        full_report = "\n".join(header_lines) + "\n\n".join(reports)

        # 保存组合报告
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"portfolio_analysis_{ts}.md"
        saved_path = self.report_generator.save_report(full_report, filename)
        print(f"报告已保存到: {saved_path}")

        return full_report

    # ─────────────────────────── 持仓组合报告辅助方法 ────────────────────────

    @staticmethod
    def _extract_portfolio_meta(code: str, entry, report: str) -> dict:
        """从单只基金的 Markdown 报告中提取摘要信息"""
        import re

        meta: dict = {
            "code": code,
            "name": entry.fund_name or code,
            "action": "—",
            "change_pct": None,
            "nav": None,
            "nav_time": None,
            "conclusion": "—",
            "return_1y": None,
        }

        # 基金名称（从报告标题提取，比持仓记录更准确）
        m = re.search(r'^# (.+?) 基金分析报告', report, re.MULTILINE)
        if m:
            meta["name"] = m.group(1)

        # 操作建议（综合操作建议表格行）
        m = re.search(r'\*\*操作建议\*\*\s*\|\s*(.+?)\s*\|', report)
        if m:
            # 去掉 emoji 前缀和 Markdown 加粗符号，只保留中文建议词
            raw = m.group(1).strip()
            raw = re.sub(r'^[🟢🟡🟠🔴🔵⚪]\s*', '', raw)   # 去 emoji
            raw = raw.replace('**', '').strip()               # 去加粗
            meta["action"] = raw

        # 核心结论
        m = re.search(r'\*\*核心结论\*\*\s*\|\s*(.+?)\s*\|', report)
        if m:
            meta["conclusion"] = m.group(1).strip()

        # 近1年收益
        m = re.search(r'\*\*近1年收益\*\*\s*\|\s*[📈📉]\s*([\+\-\d\.]+%)', report)
        if m:
            meta["return_1y"] = m.group(1).strip()

        # 日涨跌幅（实时行情章节）
        m = re.search(r'\*\*日涨跌幅\*\*[：:]\s*([\+\-\d\.]+%)', report)
        if m:
            meta["change_pct"] = m.group(1).strip()

        # 当前净值
        m = re.search(r'\*\*当前净值\*\*[：:]\s*([\d\.]+)', report)
        if m:
            meta["nav"] = m.group(1).strip()

        # 估值时间
        m = re.search(r'\*\*估值时间\*\*[：:]\s*(.+?)(?:\n|$)', report)
        if m:
            meta["nav_time"] = m.group(1).strip()

        return meta

    @staticmethod
    def _build_portfolio_summary(meta_list: List[dict]) -> List[str]:
        """生成持仓总结摘要表"""
        _ACTION_EMOJI = {
            "买入": "🟢", "加仓": "🟢", "建仓": "🟢", "定投": "🔵",
            "持有": "🟡", "观望": "🟡",
            "减仓": "🟠", "卖出": "🔴", "清仓": "🔴",
        }

        lines = [
            "## 🗂 持仓总结",
            "",
            "| # | 基金 | 代码 | 操作建议 | 日涨跌幅 | 当前净值 | 近1年收益 | 核心结论 |",
            "|---|------|------|---------|---------|---------|---------|---------|",
        ]
        for i, m in enumerate(meta_list, 1):
            emoji = _ACTION_EMOJI.get(m["action"], "")
            action_str = f"{emoji} {m['action']}" if emoji else m["action"]
            change = m["change_pct"] or "—"
            nav = m["nav"] or "—"
            ret1y = m["return_1y"] or "—"
            conclusion = m["conclusion"]
            # 截断过长的结论
            if len(conclusion) > 28:
                conclusion = conclusion[:28] + "…"
            anchor = f"#fund-{m['code']}"
            name_link = f"[{m['name']}]({anchor})"
            lines.append(
                f"| {i} | {name_link} | `{m['code']}` | {action_str} "
                f"| {change} | {nav} | {ret1y} | {conclusion} |"
            )
        lines.append("")

        # 操作分布统计
        action_counts: dict = {}
        for m in meta_list:
            action_counts[m["action"]] = action_counts.get(m["action"], 0) + 1

        stat_parts = [f"**{k}** {v}只" for k, v in sorted(action_counts.items())]
        lines.append(f"> 📌 **操作分布**：{'，'.join(stat_parts)}")
        lines.append("")

        return lines

    @staticmethod
    def _build_portfolio_toc(meta_list: List[dict]) -> List[str]:
        """生成各基金详细报告的目录（锚点跳转）"""
        lines = [
            "## 📑 目录",
            "",
        ]
        for i, m in enumerate(meta_list, 1):
            anchor = f"#fund-{m['code']}"
            action = m["action"]
            change = m["change_pct"] or ""
            change_str = f"（{change}）" if change else ""
            lines.append(f"{i}. [{m['name']} `{m['code']}`]({anchor}) — {action}{change_str}")
        lines.append("")
        return lines

    def analyze(self, fund_code: str) -> str:
        """
        执行完整的基金分析

        Args:
            fund_code: 基金代码

        Returns:
            Markdown格式分析报告
        """
        logger.info(f"开始分析基金: {fund_code}")

        # 验证基金代码
        if not self._validate_fund_code(fund_code):
            error_msg = f"无效的基金代码: {fund_code},基金代码必须是6位数字"
            logger.error(error_msg)
            return self._generate_error_report(fund_code, error_msg)

        try:
            # 执行分析流程
            analysis_result = self._execute_analysis_pipeline(fund_code)

            # 生成报告
            report = self.report_generator.generate(
                fund_code=fund_code,
                basic_info=analysis_result.get('basic_info'),
                quote=analysis_result.get('quote'),
                market_indices=analysis_result.get('market_indices') or {},
                technical=analysis_result.get('technical'),
                holding=analysis_result.get('holding'),
                manager=analysis_result.get('manager'),
                performance=analysis_result.get('performance'),
                sentiment=analysis_result.get('sentiment'),
                advice=analysis_result.get('advice'),
                stock_quotes=analysis_result.get('stock_quotes', {})
            )

            logger.info(f"基金 {fund_code} 分析完成")
            return report

        except Exception as e:
            logger.error(f"分析基金 {fund_code} 时发生错误: {e}", exc_info=True)
            error_msg = f"分析失败: {str(e)}"
            return self._generate_error_report(fund_code, error_msg)

    def _validate_fund_code(self, fund_code: str) -> bool:
        """
        验证基金代码

        Args:
            fund_code: 基金代码

        Returns:
            是否有效
        """
        if not fund_code:
            return False
        if len(fund_code) != 6:
            return False
        if not fund_code.isdigit():
            return False
        return True

    def _execute_analysis_pipeline(self, fund_code: str) -> Dict[str, Any]:
        """
        执行分析流程

        Args:
            fund_code: 基金代码

        Returns:
            分析结果字典
        """
        result = {}

        try:
            # 并发获取基础数据
            basic_data = self._fetch_all_data(fund_code)

            # 提取数据
            basic_info = basic_data.get('basic_info')
            quote = basic_data.get('quote')
            nav_history = basic_data.get('nav_history')
            holding = basic_data.get('holding')
            manager = basic_data.get('manager')
            performance = basic_data.get('performance')
            market_indices = basic_data.get('market_indices') or {}

            # 并发执行各分析模块
            analysis_tasks = {}

            if nav_history:
                analysis_tasks['technical'] = (
                    self.technical_analyzer.analyze,
                    (nav_history, quote)
                )

            if holding:
                analysis_tasks['holding'] = (
                    self.holding_analyzer.analyze,
                    (holding,)
                )

            if manager and performance:
                analysis_tasks['manager'] = (
                    self.manager_analyzer.analyze,
                    (manager, performance)
                )

            if performance:
                analysis_tasks['performance'] = (
                    self.performance_analyzer.analyze,
                    (performance,)
                )

            if basic_info:
                analysis_tasks['sentiment'] = (
                    self.sentiment_analyzer.analyze,
                    # mock_news=False 使用真实东方财富公告数据
                    # 传入 data_fetcher 复用已有连接和缓存
                    (fund_code, basic_info.fund_name, False, self.data_fetcher)
                )

            # 执行分析任务
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for key, (func, args) in analysis_tasks.items():
                    future = executor.submit(func, *args)
                    futures[future] = key

                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        result[key] = future.result()
                        logger.info(f"{key}分析完成")
                    except Exception as e:
                        logger.warning(f"{key}分析失败: {e}")
                        result[key] = None

            # 生成投资建议
            technical = result.get('technical')
            holding_analysis = result.get('holding')
            manager_analysis = result.get('manager')
            performance_analysis = result.get('performance')
            sentiment_analysis = result.get('sentiment')

            current_nav = 0.0
            if quote and quote.nav is not None:
                current_nav = quote.nav
            elif quote and quote.previous_nav is not None:
                current_nav = quote.previous_nav
            elif nav_history and nav_history.navs:
                current_nav = nav_history.navs[-1]

            if technical and performance_analysis and sentiment_analysis:
                # manager 可选；holding 可选
                _manager = manager_analysis or ManagerInfo(manager_name=None, is_senior=False)
                _holding = holding_analysis or HoldingAnalysis(
                    top10_holdings=[], style="未知", holding_concentration=0.0
                )
                try:
                    advice = self.investment_advisor.generate_advice(
                        technical=technical,
                        holding=_holding,
                        manager=_manager,
                        performance=performance_analysis,
                        sentiment=sentiment_analysis,
                        current_nav=current_nav
                    )
                    result['advice'] = advice
                    logger.info("投资建议生成完成")
                except Exception as e:
                    logger.warning(f"生成投资建议失败: {e}")
                    result['advice'] = None

            # 获取重仓股实时行情（持仓数据拿到后再查）
            stock_quotes = {}
            if holding:
                stock_codes = []
                for s in holding.top10_holdings:
                    if s is None:
                        continue
                    code = (s.get('stock_code') if isinstance(s, dict)
                            else getattr(s, 'stock_code', None))
                    if code:
                        stock_codes.append(code)
                if stock_codes:
                    try:
                        stock_quotes = self.data_fetcher.fetch_stock_quotes(stock_codes)
                    except Exception as e:
                        logger.warning(f"获取重仓股行情失败: {e}")

            # 添加原始数据到结果
            result['basic_info'] = basic_info
            result['quote'] = quote
            result['holding'] = holding
            result['manager'] = manager
            result['performance'] = performance
            result['market_indices'] = market_indices
            result['stock_quotes'] = stock_quotes

            return result

        except Exception as e:
            logger.error(f"执行分析流程失败: {e}", exc_info=True)
            raise

    def _fetch_all_data(self, fund_code: str) -> Dict[str, Any]:
        """
        并发获取所有数据

        Args:
            fund_code: 基金代码

        Returns:
            数据字典
        """
        data = {}

        with ThreadPoolExecutor(max_workers=7) as executor:
            # 提交所有数据获取任务
            futures = {
                executor.submit(self.data_fetcher.fetch_basic_info, fund_code): 'basic_info',
                executor.submit(self.data_fetcher.fetch_realtime_quote, fund_code): 'quote',
                executor.submit(self.data_fetcher.fetch_nav_history, fund_code, 365): 'nav_history',
                executor.submit(self.data_fetcher.fetch_holdings, fund_code): 'holding',
                executor.submit(self.data_fetcher.fetch_manager_info, fund_code): 'manager',
                executor.submit(self.data_fetcher.fetch_performance, fund_code): 'performance',
                executor.submit(self.data_fetcher.fetch_market_indices): 'market_indices'
            }

            # 收集结果
            for future in as_completed(futures):
                key = futures[future]
                try:
                    data[key] = future.result()
                    logger.info(f"获取{key}成功")
                except Exception as e:
                    logger.warning(f"获取{key}失败: {e}")
                    data[key] = None

        return data

    def _generate_error_report(self, fund_code: str, error_msg: str) -> str:
        """
        生成错误报告

        Args:
            fund_code: 基金代码
            error_msg: 错误信息

        Returns:
            Markdown格式错误报告
        """
        lines = []
        lines.append(f"# 基金{fund_code}分析报告\n")
        lines.append(f"> 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("---\n")
        lines.append("## ❌ 分析失败\n")
        lines.append(f"**错误信息**: {error_msg}\n")
        lines.append("\n**可能的原因**:\n")
        lines.append("- 基金代码不存在或格式错误\n")
        lines.append("- 网络连接问题\n")
        lines.append("- 数据源暂时不可用\n")
        lines.append("\n**建议**:\n")
        lines.append("- 请检查基金代码是否正确\n")
        lines.append("- 稍后重试\n")
        lines.append("- 如问题持续,请联系技术支持\n")
        lines.append("---\n")
        lines.append("## ⚠️ 免责声明\n")
        lines.append("本报告仅供参考,不构成投资建议。投资有风险,入市需谨慎。\n")

        return "\n".join(lines)

    def save_report(self, report: str, fund_code: str) -> str:
        """
        保存报告到文件

        Args:
            report: 报告内容
            fund_code: 基金代码

        Returns:
            文件路径
        """
        filename = f"fund_analysis_{fund_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        return self.report_generator.save_report(report, filename)


def main():
    """主函数"""
    import sys
    import argparse

    analyzer = FundAnalyzer()

    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python fund_analyzer.py <基金代码>                                # 分析单只基金")
        print("  python fund_analyzer.py portfolio                                 # 查看持仓列表")
        print("  python fund_analyzer.py portfolio-analyze                         # 批量分析所有持仓")
        print("  python fund_analyzer.py add <代码> [名称]                         # 添加持仓")
        print("  python fund_analyzer.py remove <代码>                             # 删除持仓")
        print("  python fund_analyzer.py recommend [--risk 低|中|高] [--period short|medium|long] [--top N]  # 推荐基金")
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        if cmd == "portfolio":
            print(analyzer.portfolio_list())

        elif cmd == "portfolio-analyze":
            report = analyzer.portfolio_analyze_all()
            print(report)
            # 注意：portfolio_analyze_all() 内部已自动保存报告，无需重复保存

        elif cmd == "add":
            if len(sys.argv) < 3:
                print("用法: python fund_analyzer.py add <基金代码> [基金名称]")
                sys.exit(1)
            fund_code = sys.argv[2]
            fund_name = sys.argv[3] if len(sys.argv) > 3 else None
            print(analyzer.portfolio_add(fund_code, fund_name=fund_name))

        elif cmd == "remove":
            if len(sys.argv) < 3:
                print("用法: python fund_analyzer.py remove <基金代码>")
                sys.exit(1)
            print(analyzer.portfolio_remove(sys.argv[2]))

        elif cmd == "recommend":
            # 推荐基金命令
            parser = argparse.ArgumentParser(description="推荐基金")
            parser.add_argument("--risk", choices=["低", "中", "高"], help="风险等级")
            parser.add_argument("--period", choices=["short", "medium", "long"], help="投资期限")
            parser.add_argument("--top", type=int, default=10, help="推荐数量")
            
            # 跳过前两个参数 (脚本名 和 'recommend')
            args = parser.parse_args(sys.argv[2:])
            
            from scripts.fund_recommender import FundRecommender
            recommender = FundRecommender()
            report = recommender.recommend(
                risk_level=args.risk,
                investment_period=args.period,
                top_n=args.top
            )
            print(report)
            
            # 保存报告
            file_path = recommender.save_recommendation_report(report, args.risk)
            if file_path:
                print(f"\n推荐报告已保存到: {file_path}")

        else:
            # 默认：分析单只基金
            fund_code = cmd
            report = analyzer.analyze(fund_code)
            print(report)
            file_path = analyzer.save_report(report, fund_code)
            print(f"\n报告已保存到: {file_path}")

    except KeyboardInterrupt:
        print("\n\n用户中断分析")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n执行失败: {e}")
        logger.error(f"主程序异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
