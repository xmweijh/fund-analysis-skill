"""
深度持仓分析器 — 主控制器
分析非固收基金，输出风险诊断 + 调仓建议 + HTML报告 + 终端摘要
"""
import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_scripts_dir)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from scripts.portfolio_manager import PortfolioManager, PortfolioEntry
from scripts.portfolio_analyzer import PortfolioAnalyzer, FundHoldingAnalysis
from scripts.risk_diagnostics import RiskDiagnostics, RiskReport
from scripts.rebalance_advisor import RebalanceAdvisor, RebalanceReport
from scripts.logger import logger

# 跳过关键词（名称含以下任一则视为固收，排除分析）
_SKIP_KEYWORDS = ["债券", "货币", "持有期", "增强回报", "稳悦", "恒睿", "利添"]


class DeepPortfolioAnalyzer:
    """深度持仓分析器"""

    def __init__(self):
        self.portfolio_mgr = PortfolioManager()
        self.base_analyzer = PortfolioAnalyzer()

    # ── 公开接口 ──────────────────────────────────────────────────────────

    def run(self, output_dir: Optional[str] = None) -> Tuple[str, str]:
        """
        执行完整深度分析。

        Returns
        -------
        (html_path, terminal_summary)
        """
        # 1. 加载并过滤非固收持仓
        all_entries = self.portfolio_mgr.list_all()
        non_fi_entries = self._filter_non_fixed_income(all_entries)
        logger.info(f"深度分析：共 {len(all_entries)} 只持仓，过滤后 {len(non_fi_entries)} 只非固收基金")

        if not non_fi_entries:
            return "", "没有非固收基金需要分析。"

        # 2. 复用 PortfolioAnalyzer 的 analyze_all，但只传非固收基金
        #    通过临时替换 portfolio_mgr 的 list_all 实现
        analyses = self._run_v2_for_entries(non_fi_entries)

        # 3. 风险诊断（使用非固收持仓 dict 列表）
        holdings_dicts = self._analyses_to_dicts(analyses)
        total_cost = sum(e.cost_amount or 0.0 for e in all_entries)
        risk_report = RiskDiagnostics().diagnose(holdings_dicts, total_portfolio_cost=total_cost)

        # 4. 调仓建议
        rebalance_report = RebalanceAdvisor().advise(holdings_dicts)

        # 5. 生成 HTML 报告
        html_path = self._generate_html(
            analyses, risk_report, rebalance_report, output_dir
        )

        # 6. 生成终端摘要
        summary = self._format_terminal_summary(risk_report, rebalance_report)

        return html_path, summary

    # ── 过滤逻辑 ─────────────────────────────────────────────────────────

    def _filter_non_fixed_income(self, entries: List) -> List:
        """过滤掉固收类基金，返回非固收基金列表"""
        result = []
        for e in entries:
            name = e.fund_name or ""
            if any(kw in name for kw in _SKIP_KEYWORDS):
                logger.debug(f"跳过固收基金: {e.fund_code} {name}")
                continue
            result.append(e)
        return result

    # ── V2 分析（复用 PortfolioAnalyzer）────────────────────────────────

    def _run_v2_for_entries(self, entries: List) -> List:
        """对指定 entries 运行 V2 五维评分"""
        # 临时替换 portfolio 的 list_all，使 analyze_all 只处理目标基金
        original_list_all = self.base_analyzer.portfolio.list_all
        self.base_analyzer.portfolio.list_all = lambda: entries
        try:
            analyses, _ = self.base_analyzer.analyze_all()
        finally:
            self.base_analyzer.portfolio.list_all = original_list_all
        return analyses

    def _analyses_to_dicts(self, analyses: List) -> List[Dict[str, Any]]:
        """将 FundHoldingAnalysis 列表转换为 dict 列表（供 RiskDiagnostics / RebalanceAdvisor 使用）"""
        return [
            {
                "fund_code": a.fund_code,
                "fund_name": a.fund_name,
                "fund_type": a.fund_type,
                "cost_amount": a.cost_amount,
                "stored_profit": a.stored_profit,
                "stored_return_rate": a.stored_return_rate,
                "v2_score": a.v2_score,
                "tech_score": a.tech_score,
            }
            for a in analyses
        ]

    # ── 报告生成 ─────────────────────────────────────────────────────────

    def _generate_html(
        self,
        analyses: List,
        risk: RiskReport,
        rebalance: RebalanceReport,
        output_dir: Optional[str],
    ) -> str:
        """生成 HTML 报告（复用 PortfolioAnalyzer._generate_html，追加 §3/§4）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_str = datetime.now().strftime("%Y%m%d")

        if output_dir is None:
            output_dir = os.path.join(_pkg_root, "reports", date_str)
        os.makedirs(output_dir, exist_ok=True)

        total_cost = sum(a.cost_amount or 0.0 for a in analyses)
        stored_profits = [a.stored_profit for a in analyses if a.stored_profit is not None]
        stored_total_profit = round(sum(stored_profits), 2) if stored_profits else None
        avg_score = round(
            sum(a.v2_score or 0.0 for a in analyses) / len(analyses), 1
        ) if analyses else 0.0

        report_data = {
            "report_type": "deep_portfolio_analysis",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_cost": round(total_cost, 2),
                "fund_count": len(analyses),
                "avg_score": avg_score,
                "total_return": stored_total_profit,
            },
            "holdings": [
                {
                    "fund_code": a.fund_code,
                    "fund_name": a.fund_name,
                    "fund_type": a.fund_type,
                    "cost_amount": round(a.cost_amount, 2) if a.cost_amount else None,
                    "stored_profit": a.stored_profit,
                    "stored_return_rate": a.stored_return_rate,
                    "weight_pct": round((a.cost_amount or 0) / total_cost * 100, 1) if total_cost > 0 else 0,
                    "total_score": a.v2_score or 0.0,
                    "tech_score": a.tech_score,
                    "action": a.action,
                    "report_file": self.base_analyzer._find_fund_report_file(a.fund_code),
                }
                for a in analyses
            ],
            "risk_report": {
                "concentration_pct": risk.concentration_pct,
                "concentration_level": risk.concentration_level,
                "overlap_groups": risk.overlap_groups,
                "qdii_pct": risk.qdii_pct,
                "qdii_level": risk.qdii_level,
                "max_loss_fund": risk.max_loss_fund,
                "max_loss_amount": risk.max_loss_amount,
                "total_loss_exposure": risk.total_loss_exposure,
                "warnings": risk.warnings,
            },
            "rebalance_report": {
                "reduce": [self._action_to_dict(a) for a in rebalance.reduce],
                "add": [self._action_to_dict(a) for a in rebalance.add],
                "hold": [self._action_to_dict(a) for a in rebalance.hold],
                "total_analyzed": rebalance.total_analyzed,
            },
        }

        # 保存 JSON
        json_path = os.path.join(output_dir, f"deep_portfolio_{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成 HTML（复用 base_analyzer 的模板，追加 §3/§4）
        html_content = self.base_analyzer._generate_html(report_data, timestamp)
        html_content = _inject_risk_rebalance_sections(html_content, risk, rebalance)

        html_path = os.path.join(output_dir, f"deep_portfolio_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"深度分析报告生成: {html_path}")
        return html_path

    def _action_to_dict(self, a) -> Dict[str, Any]:
        return {
            "fund_code": a.fund_code,
            "fund_name": a.fund_name,
            "action": a.action,
            "priority": a.priority,
            "rebalance_score": a.rebalance_score,
            "v2_score": a.v2_score,
            "stored_profit": a.stored_profit,
            "stored_return_rate": a.stored_return_rate,
            "reason": a.reason,
        }

    # ── 终端摘要 ──────────────────────────────────────────────────────────

    def _format_terminal_summary(
        self, risk: RiskReport, rebalance: RebalanceReport
    ) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [
            "══════════════════════════════════════════",
            f"📊 深度持仓分析摘要（{today}）",
            "══════════════════════════════════════════",
            "",
            "[风险诊断]",
        ]
        if risk.warnings:
            for w in risk.warnings:
                lines.append(f"  {w}")
        else:
            lines.append("  ✅ 未发现明显风险预警")

        lines += ["", "[调仓建议]"]
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "⚪"}
        add_emoji = {"high": "🟢", "medium": "🟢", "low": "⚪"}

        for a in rebalance.reduce:
            emoji = priority_emoji.get(a.priority, "🟡")
            lines.append(
                f"  {emoji} {'高' if a.priority == 'high' else '中'}优先级减仓："
                f"{a.fund_name}（{a.stored_return_rate:+.1f}%，评分{a.v2_score:.0f}）"
            )
        for a in rebalance.add:
            emoji = add_emoji.get(a.priority, "🟢")
            lines.append(
                f"  {emoji} {'高' if a.priority == 'high' else '中'}优先级加仓："
                f"{a.fund_name}（{a.stored_return_rate:+.1f}%，评分{a.v2_score:.0f}）"
            )
        if not rebalance.reduce and not rebalance.add:
            lines.append("  ✅ 当前持仓无明显调仓需求")

        lines += [
            "",
            f"共分析 {rebalance.total_analyzed} 只 · "
            f"减仓 {len(rebalance.reduce)} 只 · "
            f"加仓 {len(rebalance.add)} 只 · "
            f"观察 {len(rebalance.hold)} 只",
            "══════════════════════════════════════════",
        ]
        return "\n".join(lines)


# ── HTML 注入函数（模块级，便于测试）─────────────────────────────────────

def _inject_risk_rebalance_sections(
    html: str, risk: RiskReport, rebalance: RebalanceReport
) -> str:
    """在 </body> 前注入 §3 风险诊断和 §4 调仓建议两个章节"""

    level_color = {"high": "#ef5350", "medium": "#ffb74d", "low": "#4caf50"}
    level_label = {"high": "高", "medium": "中", "low": "低"}
    qdii_color = {"low": "#ffb74d", "ok": "#4caf50", "high": "#ef5350"}

    # § 3 风险诊断 — 五个指标卡片
    conc_color = level_color.get(risk.concentration_level, "#888")
    conc_label = level_label.get(risk.concentration_level, "?")
    overlap_color = "#ffb74d" if risk.overlap_groups else "#4caf50"
    overlap_label = "有" if risk.overlap_groups else "无"
    overlap_brands = "、".join(g["brand"] for g in risk.overlap_groups[:2]) or "无重叠"
    q_color = qdii_color.get(risk.qdii_level, "#888")
    q_label = "低" if risk.qdii_level == "low" else ("高" if risk.qdii_level == "high" else "OK")
    loss_color = "#ef5350" if risk.max_loss_amount < -1000 else "#4caf50"
    loss_val = "¥{:,.0f}".format(abs(risk.max_loss_amount)) if risk.max_loss_amount else "无"
    loss_name = (risk.max_loss_fund[:8] if risk.max_loss_fund else "-")
    expo_color = "#ffb74d" if risk.total_loss_exposure < -3000 else "#4caf50"
    expo_val = "¥{:,.0f}".format(abs(risk.total_loss_exposure)) if risk.total_loss_exposure else "无"
    expo_label = "有亏损" if risk.total_loss_exposure < 0 else "无亏损"

    # Build warning rows
    if risk.warnings:
        warning_rows = "".join(
            '<div style="border-left:3px solid #ffb74d;padding:10px 14px;margin-bottom:8px;'
            'border-radius:0 6px 6px 0;font-size:13px">' + w + "</div>"
            for w in risk.warnings
        )
    else:
        warning_rows = '<div style="color:#4caf50;font-size:13px">✅ 未发现明显风险预警</div>'

    risk_html = (
        '\n    <div class="card" style="margin-top:24px">'
        "\n      <h2>🔍 §3 风险诊断</h2>"
        '\n      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px">'
        # 集中度
        f'\n        <div style="border:2px solid {conc_color};border-radius:8px;padding:12px;text-align:center">'
        '\n          <div style="font-size:11px;color:#888">集中度</div>'
        f'\n          <div style="font-size:22px;font-weight:700;color:{conc_color}">{conc_label}</div>'
        f'\n          <div style="font-size:11px;color:{conc_color}">Top3 占 {risk.concentration_pct:.0f}%</div>'
        "\n        </div>"
        # 同类重叠
        f'\n        <div style="border:2px solid {overlap_color};border-radius:8px;padding:12px;text-align:center">'
        '\n          <div style="font-size:11px;color:#888">同类重叠</div>'
        f'\n          <div style="font-size:22px;font-weight:700;color:{overlap_color}">{overlap_label}</div>'
        f'\n          <div style="font-size:11px;color:{overlap_color}">{overlap_brands}</div>'
        "\n        </div>"
        # QDII
        f'\n        <div style="border:2px solid {q_color};border-radius:8px;padding:12px;text-align:center">'
        '\n          <div style="font-size:11px;color:#888">QDII 配比</div>'
        f'\n          <div style="font-size:22px;font-weight:700;color:{q_color}">{q_label}</div>'
        f'\n          <div style="font-size:11px;color:{q_color}">{risk.qdii_pct:.1f}%</div>'
        "\n        </div>"
        # 最大单亏
        f'\n        <div style="border:2px solid {loss_color};border-radius:8px;padding:12px;text-align:center">'
        '\n          <div style="font-size:11px;color:#888">最大单亏</div>'
        f'\n          <div style="font-size:18px;font-weight:700;color:{loss_color}">{loss_val}</div>'
        f'\n          <div style="font-size:11px;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{loss_name}</div>'
        "\n        </div>"
        # 亏损总敞口
        f'\n        <div style="border:2px solid {expo_color};border-radius:8px;padding:12px;text-align:center">'
        '\n          <div style="font-size:11px;color:#888">亏损总敞口</div>'
        f'\n          <div style="font-size:18px;font-weight:700;color:{expo_color}">{expo_val}</div>'
        f'\n          <div style="font-size:11px;color:#888">{expo_label}</div>'
        "\n        </div>"
        "\n      </div>"
        f"\n      {warning_rows}"
        "\n    </div>"
    )

    # § 4 调仓建议
    priority_badge_styles = {
        "high": 'style="background:#4a1010;color:#ef5350;padding:2px 8px;border-radius:4px;font-size:11px"',
        "medium": 'style="background:#3a2a10;color:#ffb74d;padding:2px 8px;border-radius:4px;font-size:11px"',
    }

    def action_rows(actions):
        rows = []
        for a in actions:
            profit_str = f"{a.stored_profit:+,.0f}" if a.stored_profit is not None else "-"
            rate_str = f"{a.stored_return_rate:+.1f}%" if a.stored_return_rate is not None else "-"
            profit_color = "#4caf50" if (a.stored_profit or 0) > 0 else "#ef5350"
            badge_style = priority_badge_styles.get(a.priority, priority_badge_styles["medium"])
            pri_label = "高" if a.priority == "high" else "中"
            rows.append(
                '\n          <tr style="border-bottom:1px solid #1a1a1a">'
                f'\n            <td style="padding:8px 0;color:#ccc">{a.fund_name[:12]}</td>'
                f'\n            <td style="text-align:center"><span {badge_style}>{pri_label}</span></td>'
                f'\n            <td style="text-align:right;color:#aaa">{a.v2_score:.0f}</td>'
                f'\n            <td style="text-align:right;color:{profit_color}">{profit_str}（{rate_str}）</td>'
                f'\n            <td style="padding-left:12px;color:#888;font-size:12px">{a.reason}</td>'
                "\n          </tr>"
            )
        return "".join(rows)

    table_header = (
        '\n        <tr style="color:#666;font-size:11px;border-bottom:1px solid #333">'
        '\n          <td style="padding:6px 0">基金</td>'
        '\n          <td style="text-align:center">优先级</td>'
        '\n          <td style="text-align:right">评分</td>'
        '\n          <td style="text-align:right">持仓盈亏</td>'
        '\n          <td style="padding-left:12px">理由</td>'
        "\n        </tr>"
    )

    reduce_section = ""
    if rebalance.reduce:
        reduce_section = (
            '\n      <div style="font-size:12px;color:#ef5350;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">🔴 建议减仓</div>'
            '\n      <table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:16px">'
            + table_header + action_rows(rebalance.reduce) +
            "\n      </table>"
        )

    add_section = ""
    if rebalance.add:
        add_section = (
            '\n      <div style="font-size:12px;color:#4caf50;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">🟢 建议加仓</div>'
            '\n      <table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:16px">'
            + table_header + action_rows(rebalance.add) +
            "\n      </table>"
        )

    rebalance_html = (
        '\n    <div class="card" style="margin-top:24px">'
        "\n      <h2>⚖️ §4 调仓建议</h2>"
        + reduce_section
        + add_section +
        '\n      <div style="text-align:center;padding:12px;font-size:13px;color:#888">'
        f'\n        共分析 <strong style="color:#e8e8e8">{rebalance.total_analyzed}</strong> 只 ·'
        f'\n        建议减仓 <strong style="color:#ef5350">{len(rebalance.reduce)}</strong> 只 ·'
        f'\n        建议加仓 <strong style="color:#4caf50">{len(rebalance.add)}</strong> 只 ·'
        f'\n        持有观察 <strong style="color:#aaa">{len(rebalance.hold)}</strong> 只'
        "\n      </div>"
        "\n    </div>"
    )

    injection = risk_html + rebalance_html + "\n"

    # Primary injection point: before closing </div> + newline + <script>
    # The base HTML has: "    </div>\n\n    <script>"  (closing .container div then script)
    primary_marker = "    </div>\n\n    <script>"
    if primary_marker in html:
        return html.replace(primary_marker, injection + "\n    </div>\n\n    <script>", 1)

    # Fallback: inject before </body>
    return html.replace("</body>", injection + "\n</body>", 1)


def main():
    parser = argparse.ArgumentParser(description="深度持仓分析：非固收基金五维评分 + 风险诊断 + 调仓建议")
    parser.add_argument("--output-dir", help="报告输出目录")
    args = parser.parse_args()

    analyzer = DeepPortfolioAnalyzer()
    html_path, summary = analyzer.run(args.output_dir)

    print(summary)
    if html_path:
        print(f"\n📄 HTML报告: {html_path}")


if __name__ == "__main__":
    main()
